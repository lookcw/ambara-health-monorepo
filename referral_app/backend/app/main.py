import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
import json
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from app.database import engine, Base, get_db
from app.models.provider import Provider
from app.models.provider_institution import ProviderInstitution
from app.models.address import Address
from app.models.user import User
from app.models.patient import Patient
from app.models.referral import Referral, ReferralStatus
from app.models.user_provider_network import UserProviderNetwork
from app.auth import auth_backend, fastapi_users, current_active_user
from app.schemas import (
    UserCreate,
    UserRead,
    UserUpdate,
    PatientCreate,
    ReferralCreate,
    ReferralRead,
    NetworkEntryCreate,
    NetworkEntryRead,
    ProviderCreate,
    ProviderUpdate,
    ProviderRead,
    AddressCreate,
    MyInstitutionCreate,
    MyInstitutionUpdate,
    MyInstitutionRead,
)
from datetime import datetime
from app.gmail_service import send_referral_notification_email
from app.faxage_service import get_faxage_credentials, list_received_faxes, get_fax_pdf, delete_fax
from app.gcs_service import upload_blob, blob_exists
from googleapiclient.errors import HttpError

# Configure logging for Google Cloud
if os.getenv("ENVIRONMENT") != "local":
    import google.cloud.logging
    from google.cloud.logging_v2.handlers import CloudLoggingHandler

    # Initialize Google Cloud Logging
    client = google.cloud.logging.Client()
    handler = CloudLoggingHandler(client, name="referral-app")

    # Set up root logger
    logging.basicConfig(level=logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
else:
    # Local development logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Referral App API", version="1.0.0")


# Configure CORS
def get_allowed_origins():
    env = os.getenv("ENVIRONMENT", "local")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    if env == "local":
        return ["http://localhost:5173", "http://localhost:5174"]
    else:
        return [frontend_url]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for SQLAdmin authentication
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"))


# Global exception handler for Error Reporting
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and log them to Google Cloud Error Reporting.
    """
    # Log the exception with ERROR level - this will appear in Error Reporting
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,  # Include stack trace
        extra={
            "url": str(request.url),
            "method": request.method,
            "client_host": request.client.host if request.client else None,
        },
    )

    # Return a generic error response to the client
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})


# Include authentication routes under /api prefix
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)


# Create database tables on startup
@app.on_event("startup")
async def startup():
    logger.info("Application starting up")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


# API health check endpoints
@app.get("/api")
def read_root():
    return {"status": "ok", "message": "Hello World from FastAPI!"}


@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Try to execute a simple query
        await db.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except (SQLAlchemyError, OSError) as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# Frontend error reporting endpoint
@app.post("/api/log-error")
async def log_frontend_error(request: Request, user: User = Depends(current_active_user)):
    """
    Endpoint for frontend to report JavaScript errors to Cloud Error Reporting.
    """
    body = await request.json()
    error_message = body.get("message", "Unknown error")
    stack = body.get("stack", "")
    url = body.get("url", "")
    line = body.get("line", "")
    column = body.get("column", "")

    # Log frontend error with ERROR severity
    logger.error(
        f"Frontend Error: {error_message}",
        extra={
            "error_type": "frontend_error",
            "stack": stack,
            "url": url,
            "line": line,
            "column": column,
            "user_id": str(user.id),
            "user_email": user.email,
        },
    )

    return {"status": "logged"}


# Provider endpoints (FILTERED BY USER NETWORK)
@app.get("/api/providers")
async def get_providers(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    """
    Get providers in user's network.
    MODIFIED: Now requires authentication and filters by user's network.
    """
    # Get user's network provider IDs
    network_result = await db.execute(
        select(UserProviderNetwork.provider_id).filter(
            UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_id.isnot(None)
        )
    )
    network_provider_ids = [row[0] for row in network_result.all()]

    if not network_provider_ids:
        # Empty network returns empty list
        return []

    # Fetch providers in network with full details
    result = await db.execute(
        select(Provider)
        .options(
            selectinload(Provider.address), selectinload(Provider.institution).selectinload(ProviderInstitution.address)
        )
        .filter(Provider.id.in_(network_provider_ids))
    )
    providers = result.scalars().all()

    return [
        {
            "id": str(provider.id),
            "first_name": provider.first_name,
            "last_name": provider.last_name,
            "full_name": provider.full_name,
            "email": provider.email,
            "phone": provider.phone,
            "address": {
                "street_address_1": provider.address.street_address_1,
                "street_address_2": provider.address.street_address_2,
                "city": provider.address.city,
                "state": provider.address.state,
                "zip_code": provider.address.zip_code,
                "country": provider.address.country,
            }
            if provider.address
            else None,
            "institution": {
                "id": str(provider.institution.id),
                "name": provider.institution.name,
                "website": provider.institution.website,
                "address": {
                    "street_address_1": provider.institution.address.street_address_1,
                    "street_address_2": provider.institution.address.street_address_2,
                    "city": provider.institution.address.city,
                    "state": provider.institution.address.state,
                    "zip_code": provider.institution.address.zip_code,
                    "country": provider.institution.address.country,
                }
                if provider.institution.address
                else None,
            }
            if provider.institution
            else None,
            "created_at": provider.datetime_created.isoformat() if provider.datetime_created else None,
            "updated_at": provider.datetime_updated.isoformat() if provider.datetime_updated else None,
        }
        for provider in providers
    ]


@app.get("/api/providers/{provider_id}")
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific provider by ID."""
    result = await db.execute(
        select(Provider)
        .options(
            selectinload(Provider.address), selectinload(Provider.institution).selectinload(ProviderInstitution.address)
        )
        .filter(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        return {"error": "Provider not found"}

    return {
        "id": str(provider.id),
        "first_name": provider.first_name,
        "last_name": provider.last_name,
        "full_name": provider.full_name,
        "email": provider.email,
        "phone": provider.phone,
        "address": {
            "street_address_1": provider.address.street_address_1,
            "street_address_2": provider.address.street_address_2,
            "city": provider.address.city,
            "state": provider.address.state,
            "zip_code": provider.address.zip_code,
            "country": provider.address.country,
        }
        if provider.address
        else None,
        "institution": {
            "id": str(provider.institution.id),
            "name": provider.institution.name,
            "website": provider.institution.website,
            "address": {
                "street_address_1": provider.institution.address.street_address_1,
                "street_address_2": provider.institution.address.street_address_2,
                "city": provider.institution.address.city,
                "state": provider.institution.address.state,
                "zip_code": provider.institution.address.zip_code,
                "country": provider.institution.address.country,
            }
            if provider.institution.address
            else None,
        }
        if provider.institution
        else None,
        "created_at": provider.datetime_created.isoformat() if provider.datetime_created else None,
        "updated_at": provider.datetime_updated.isoformat() if provider.datetime_updated else None,
    }


@app.post("/api/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_custom_provider(
    provider_data: ProviderCreate, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Create a new custom provider.
    Automatically adds to user's network.
    """
    # Create address if provided
    address = None
    if provider_data.address:
        address = Address(**provider_data.address.dict())
        db.add(address)
        await db.flush()

    # Create custom provider
    provider = Provider(
        first_name=provider_data.first_name,
        last_name=provider_data.last_name,
        email=provider_data.email,
        phone=provider_data.phone,
        institution_id=provider_data.institution_id,
        address_id=address.id if address else None,
        global_provider=False,
        created_by_user_id=user.id,
    )
    db.add(provider)
    await db.flush()

    # Automatically add to user's network
    network_entry = UserProviderNetwork(user_id=user.id, provider_id=provider.id)
    db.add(network_entry)

    await db.commit()
    await db.refresh(provider)

    # Load relationships for response
    result = await db.execute(
        select(Provider)
        .options(selectinload(Provider.address), selectinload(Provider.institution))
        .filter(Provider.id == provider.id)
    )
    provider = result.scalar_one()

    return provider


@app.put("/api/providers/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: str,
    provider_data: ProviderUpdate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a provider.
    - If global: Create new custom copy, add to network, return new provider
    - If custom owned by user: Update directly
    - Otherwise: 403 Forbidden
    """
    # Fetch provider with relationships
    result = await db.execute(
        select(Provider).options(selectinload(Provider.address)).filter(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Authorization and copy-on-write logic
    if provider.global_provider:
        # GLOBAL PROVIDER: Create custom copy

        # Copy address if exists or create new one from update data
        new_address = None
        if provider_data.address:
            # Use updated address data
            new_address = Address(**provider_data.address.dict())
            db.add(new_address)
            await db.flush()
        elif provider.address:
            # Copy existing address
            new_address = Address(
                street_address_1=provider.address.street_address_1,
                street_address_2=provider.address.street_address_2,
                city=provider.address.city,
                state=provider.address.state,
                zip_code=provider.address.zip_code,
                country=provider.address.country,
            )
            db.add(new_address)
            await db.flush()

        # Create custom provider copy with updates
        new_provider = Provider(
            first_name=provider_data.first_name if provider_data.first_name is not None else provider.first_name,
            last_name=provider_data.last_name if provider_data.last_name is not None else provider.last_name,
            email=provider_data.email if provider_data.email is not None else provider.email,
            phone=provider_data.phone if provider_data.phone is not None else provider.phone,
            institution_id=provider_data.institution_id
            if provider_data.institution_id is not None
            else provider.institution_id,
            address_id=new_address.id if new_address else None,
            global_provider=False,
            created_by_user_id=user.id,
            copied_from_provider_id=provider.id,
        )
        db.add(new_provider)
        await db.flush()

        # Remove old provider from network, add new custom provider
        await db.execute(
            delete(UserProviderNetwork).filter(
                UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_id == provider_id
            )
        )

        network_entry = UserProviderNetwork(user_id=user.id, provider_id=new_provider.id)
        db.add(network_entry)

        await db.commit()

        # Load relationships for response
        result = await db.execute(
            select(Provider)
            .options(selectinload(Provider.address), selectinload(Provider.institution))
            .filter(Provider.id == new_provider.id)
        )
        new_provider = result.scalar_one()

        return new_provider

    else:
        # CUSTOM PROVIDER: Update directly
        if provider.created_by_user_id != user.id:
            raise HTTPException(status_code=403, detail="You can only edit providers you created")

        # Update address if provided
        if provider_data.address:
            if provider.address:
                # Update existing address
                provider.address.street_address_1 = provider_data.address.street_address_1
                provider.address.street_address_2 = provider_data.address.street_address_2
                provider.address.city = provider_data.address.city
                provider.address.state = provider_data.address.state
                provider.address.zip_code = provider_data.address.zip_code
                provider.address.country = provider_data.address.country
            else:
                # Create new address
                new_address = Address(**provider_data.address.dict())
                db.add(new_address)
                await db.flush()
                provider.address_id = new_address.id

        # Update provider fields
        if provider_data.first_name is not None:
            provider.first_name = provider_data.first_name
        if provider_data.last_name is not None:
            provider.last_name = provider_data.last_name
        if provider_data.email is not None:
            provider.email = provider_data.email
        if provider_data.phone is not None:
            provider.phone = provider_data.phone
        if provider_data.institution_id is not None:
            provider.institution_id = provider_data.institution_id

        await db.commit()

        # Load relationships for response
        result = await db.execute(
            select(Provider)
            .options(selectinload(Provider.address), selectinload(Provider.institution))
            .filter(Provider.id == provider.id)
        )
        provider = result.scalar_one()

        return provider


# Patient endpoints
@app.get("/api/patients")
async def get_patients(db: AsyncSession = Depends(get_db)):
    """Get all patients for dropdown."""
    result = await db.execute(select(Patient))
    patients = result.scalars().all()
    return [
        {
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat(),
            "phone": patient.phone,
            "email": patient.email,
        }
        for patient in patients
    ]


# Provider institution endpoints (FILTERED BY USER NETWORK)
@app.get("/api/provider-institutions")
async def get_provider_institutions(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    """
    Get provider institutions in user's network.
    MODIFIED: Now requires authentication and filters by user's network.
    """
    # Get user's network institution IDs
    network_result = await db.execute(
        select(UserProviderNetwork.provider_institution_id).filter(
            UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_institution_id.isnot(None)
        )
    )
    network_institution_ids = [row[0] for row in network_result.all()]

    if not network_institution_ids:
        # Empty network returns empty list
        return []

    # Fetch institutions in network
    result = await db.execute(select(ProviderInstitution).filter(ProviderInstitution.id.in_(network_institution_ids)))
    institutions = result.scalars().all()

    return [{"id": str(inst.id), "name": inst.name} for inst in institutions]


# My Institution endpoints (user's own institution)


@app.get("/api/my-institution", response_model=MyInstitutionRead)
async def get_my_institution(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    """
    Get current user's institution.
    Returns 404 if user hasn't created their institution yet.
    """
    result = await db.execute(
        select(ProviderInstitution)
        .options(selectinload(ProviderInstitution.address))
        .filter(ProviderInstitution.created_by_user_id == user.id)
    )
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution not found. Please create your institution profile.",
        )

    # Build response with nested address
    response_data = {
        "id": institution.id,
        "created_by_user_id": institution.created_by_user_id,
        "name": institution.name,
        "type": institution.type,
        "phone": institution.phone,
        "email": institution.email,
        "website": institution.website,
        "address_id": institution.address_id,
        "address": {
            "street_address_1": institution.address.street_address_1,
            "street_address_2": institution.address.street_address_2,
            "city": institution.address.city,
            "state": institution.address.state,
            "zip_code": institution.address.zip_code,
            "country": institution.address.country,
        }
        if institution.address
        else None,
        "datetime_created": institution.datetime_created,
        "datetime_updated": institution.datetime_updated,
    }

    return response_data


@app.post("/api/my-institution", response_model=MyInstitutionRead, status_code=status.HTTP_201_CREATED)
async def create_my_institution(
    institution_data: MyInstitutionCreate, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Create user's institution.
    Returns 409 Conflict if user already has an institution.
    """
    # Check if user already has an institution
    existing_result = await db.execute(
        select(ProviderInstitution).filter(ProviderInstitution.created_by_user_id == user.id)
    )
    existing_institution = existing_result.scalar_one_or_none()

    if existing_institution:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already have an institution. Use PUT to update it."
        )

    # Create address if provided
    address_id = None
    if institution_data.address:
        address = Address(**institution_data.address.dict())
        db.add(address)
        await db.flush()
        address_id = address.id

    # Create institution
    institution = ProviderInstitution(
        name=institution_data.name,
        type=institution_data.type,
        phone=institution_data.phone,
        email=institution_data.email,
        website=institution_data.website,
        address_id=address_id,
        created_by_user_id=user.id,
    )
    db.add(institution)
    await db.commit()
    await db.refresh(institution)

    # Load address relationship
    await db.refresh(institution, ["address"])

    # Build response
    response_data = {
        "id": institution.id,
        "created_by_user_id": institution.created_by_user_id,
        "name": institution.name,
        "type": institution.type,
        "phone": institution.phone,
        "email": institution.email,
        "website": institution.website,
        "address_id": institution.address_id,
        "address": {
            "street_address_1": institution.address.street_address_1,
            "street_address_2": institution.address.street_address_2,
            "city": institution.address.city,
            "state": institution.address.state,
            "zip_code": institution.address.zip_code,
            "country": institution.address.country,
        }
        if institution.address
        else None,
        "datetime_created": institution.datetime_created,
        "datetime_updated": institution.datetime_updated,
    }

    return response_data


@app.put("/api/my-institution", response_model=MyInstitutionRead)
async def update_my_institution(
    institution_data: MyInstitutionUpdate, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Update user's institution.
    Returns 404 if user hasn't created their institution yet.
    """
    # Get user's institution
    result = await db.execute(
        select(ProviderInstitution)
        .options(selectinload(ProviderInstitution.address))
        .filter(ProviderInstitution.created_by_user_id == user.id)
    )
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found. Use POST to create it first."
        )

    # Update basic fields
    if institution_data.name is not None:
        institution.name = institution_data.name
    if institution_data.type is not None:
        institution.type = institution_data.type
    if institution_data.phone is not None:
        institution.phone = institution_data.phone
    if institution_data.email is not None:
        institution.email = institution_data.email
    if institution_data.website is not None:
        institution.website = institution_data.website

    # Handle address update/create
    if institution_data.address:
        if institution.address:
            # Update existing address
            institution.address.street_address_1 = institution_data.address.street_address_1
            institution.address.street_address_2 = institution_data.address.street_address_2
            institution.address.city = institution_data.address.city
            institution.address.state = institution_data.address.state
            institution.address.zip_code = institution_data.address.zip_code
            institution.address.country = institution_data.address.country
        else:
            # Create new address
            address = Address(**institution_data.address.dict())
            db.add(address)
            await db.flush()
            institution.address_id = address.id

    await db.commit()
    await db.refresh(institution)
    await db.refresh(institution, ["address"])

    # Build response
    response_data = {
        "id": institution.id,
        "created_by_user_id": institution.created_by_user_id,
        "name": institution.name,
        "type": institution.type,
        "phone": institution.phone,
        "email": institution.email,
        "website": institution.website,
        "address_id": institution.address_id,
        "address": {
            "street_address_1": institution.address.street_address_1,
            "street_address_2": institution.address.street_address_2,
            "city": institution.address.city,
            "state": institution.address.state,
            "zip_code": institution.address.zip_code,
            "country": institution.address.country,
        }
        if institution.address
        else None,
        "datetime_created": institution.datetime_created,
        "datetime_updated": institution.datetime_updated,
    }

    return response_data


@app.delete("/api/my-institution", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_institution(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    """
    Delete user's institution.
    Returns 204 No Content on success, 404 if not found.
    """
    result = await db.execute(select(ProviderInstitution).filter(ProviderInstitution.created_by_user_id == user.id))
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    await db.delete(institution)
    await db.commit()
    return None


# Referral endpoints
@app.post("/api/referrals", response_model=ReferralRead)
async def create_referral(
    referral_data: ReferralCreate, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """Create a new referral (requires authentication)."""
    # Check if user has created their institution
    institution_result = await db.execute(
        select(ProviderInstitution).filter(ProviderInstitution.created_by_user_id == user.id)
    )
    user_institution = institution_result.scalar_one_or_none()

    if not user_institution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete your institution profile at /my-institution before creating referrals",
        )

    # Get or create patient
    if referral_data.patient_id:
        result = await db.execute(select(Patient).filter(Patient.id == referral_data.patient_id))
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    else:
        patient = Patient(**referral_data.patient_data.dict())
        db.add(patient)
        await db.flush()

    # Create referral
    referral_dict = {
        "user_id": user.id,
        "patient_id": patient.id,
        "status": ReferralStatus.PENDING,
        "notes": referral_data.notes,
        "appointment_timeframe": referral_data.appointment_timeframe,
    }

    if referral_data.referral_target_type == "provider":
        referral_dict["provider_id"] = referral_data.provider_id
    elif referral_data.referral_target_type == "provider_institution":
        referral_dict["provider_institution_id"] = referral_data.provider_institution_id
    # For "open" referrals, neither provider_id nor provider_institution_id is set

    referral = Referral(**referral_dict)
    db.add(referral)
    await db.commit()
    await db.refresh(referral)

    # Send email notification to help@grovehealth.us
    # Get referral target name
    if referral_data.referral_target_type == "open":
        referral_target_name = "Open Referral (No specific provider)"
    elif referral_data.referral_target_type == "provider":
        provider_result = await db.execute(select(Provider).filter(Provider.id == referral_data.provider_id))
        provider = provider_result.scalar_one_or_none()
        referral_target_name = provider.full_name if provider else "Unknown Provider"
    else:
        institution_result = await db.execute(
            select(ProviderInstitution).filter(ProviderInstitution.id == referral_data.provider_institution_id)
        )
        institution = institution_result.scalar_one_or_none()
        referral_target_name = institution.name if institution else "Unknown Institution"

    patient_name = f"{patient.first_name} {patient.last_name}"

    # Send email notification (will fail the entire request if email fails)
    await send_referral_notification_email(
        referral_id=str(referral.id),
        user_email=user.email,
        patient_name=patient_name,
        referral_target_name=referral_target_name,
        referral_target_type=referral_data.referral_target_type,
        notes=referral_data.notes,
    )

    return referral


# Faxage Polling Endpoints


@app.post("/api/fax/poll-incoming", status_code=status.HTTP_200_OK)
async def poll_incoming_faxes():
    """
    Poll Faxage for new inbound faxes.

    Calls Faxage listfax API, downloads any new fax PDFs not already in GCS,
    uploads them to GCS, and deletes them from the Faxage inbox.

    Returns:
        Summary of processed faxes.
    """
    logger.info("Faxage poll: Starting inbound fax poll")

    username, company, password = get_faxage_credentials()
    if not username or not company or not password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Faxage credentials not configured",
        )

    # List available faxes
    try:
        faxes = await list_received_faxes(username, company, password)
    except Exception as e:
        logger.exception(f"Faxage poll: Failed to list faxes: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list faxes from Faxage: {e}",
        )

    logger.info(f"Faxage poll: Found {len(faxes)} fax(es) in inbox")

    bucket_name = os.getenv("INBOUND_FAXES_BUCKET", "grove-health-inbound-faxes")
    now = datetime.utcnow()
    processed = []
    skipped = []
    errors = []

    for fax in faxes:
        recvid = fax.get("recvid", "")
        if not recvid:
            continue

        blob_path = f"inbound/{now.year}/{now.month:02d}/{now.day:02d}/{recvid}.pdf"

        # Check if already uploaded
        if blob_exists(bucket_name, blob_path):
            logger.info(f"Faxage poll: Fax {recvid} already in GCS, skipping")
            skipped.append(recvid)
            continue

        try:
            # Download PDF
            logger.info(f"Faxage poll: Downloading fax {recvid}...")
            pdf_data = await get_fax_pdf(username, company, password, recvid)
            logger.info(f"Faxage poll: Downloaded {len(pdf_data)} bytes for fax {recvid}")

            # Upload to GCS
            metadata = {
                "recvid": recvid,
                "caller_id": fax.get("cid", ""),
                "dnis": fax.get("dnis", ""),
                "pages": fax.get("pagecount", ""),
                "received_date": fax.get("revdate", ""),
                "start_time": fax.get("starttime", ""),
                "tsid": fax.get("tsid", ""),
                "direction": "inbound",
            }

            gcs_url = upload_blob(
                bucket_name=bucket_name,
                source_data=pdf_data,
                destination_blob_name=blob_path,
                content_type="application/pdf",
                metadata=metadata,
            )

            logger.info(f"Faxage poll: Uploaded fax {recvid} to {gcs_url}")

            # Delete from Faxage inbox after successful upload
            try:
                await delete_fax(username, company, password, recvid)
                logger.info(f"Faxage poll: Deleted fax {recvid} from Faxage inbox")
            except Exception as e:
                logger.warning(f"Faxage poll: Failed to delete fax {recvid} from Faxage: {e}")

            processed.append({
                "recvid": recvid,
                "gcs_url": gcs_url,
                "caller_id": fax.get("cid", ""),
                "dnis": fax.get("dnis", ""),
                "pages": fax.get("pagecount", ""),
            })

        except Exception as e:
            logger.exception(f"Faxage poll: Failed to process fax {recvid}: {e}")
            errors.append({"recvid": recvid, "error": str(e)})

    logger.info(
        f"Faxage poll: Done. Processed={len(processed)}, Skipped={len(skipped)}, Errors={len(errors)}"
    )

    return {
        "status": "success",
        "total_in_inbox": len(faxes),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }


# Network Management Endpoints


@app.get("/api/network")
async def get_user_network(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    """
    Get current user's provider network with full details.
    Returns both providers and institutions with all relevant information.
    """
    result = await db.execute(
        select(UserProviderNetwork)
        .options(
            selectinload(UserProviderNetwork.provider).selectinload(Provider.address),
            selectinload(UserProviderNetwork.provider)
            .selectinload(Provider.institution)
            .selectinload(ProviderInstitution.address),
            selectinload(UserProviderNetwork.provider_institution).selectinload(ProviderInstitution.address),
        )
        .filter(UserProviderNetwork.user_id == user.id)
        .order_by(UserProviderNetwork.datetime_created.desc())
    )
    network_entries = result.scalars().all()

    # Transform to response format
    network_items = []
    for entry in network_entries:
        if entry.provider:
            network_items.append(
                {
                    "id": str(entry.id),
                    "target_type": "provider",
                    "provider_id": str(entry.provider_id),
                    "first_name": entry.provider.first_name,
                    "last_name": entry.provider.last_name,
                    "full_name": entry.provider.full_name,
                    "email": entry.provider.email,
                    "phone": entry.provider.phone,
                    "global_provider": entry.provider.global_provider,
                    "created_by_user_id": str(entry.provider.created_by_user_id)
                    if entry.provider.created_by_user_id
                    else None,
                    "address": {
                        "street_address_1": entry.provider.address.street_address_1,
                        "street_address_2": entry.provider.address.street_address_2,
                        "city": entry.provider.address.city,
                        "state": entry.provider.address.state,
                        "zip_code": entry.provider.address.zip_code,
                        "country": entry.provider.address.country,
                    }
                    if entry.provider.address
                    else None,
                    "institution": {
                        "id": str(entry.provider.institution.id),
                        "name": entry.provider.institution.name,
                        "website": entry.provider.institution.website,
                    }
                    if entry.provider.institution
                    else None,
                    "datetime_added": entry.datetime_created.isoformat(),
                }
            )
        else:
            network_items.append(
                {
                    "id": str(entry.id),
                    "target_type": "provider_institution",
                    "provider_institution_id": str(entry.provider_institution_id),
                    "name": entry.provider_institution.name,
                    "website": entry.provider_institution.website,
                    "address": {
                        "street_address_1": entry.provider_institution.address.street_address_1,
                        "street_address_2": entry.provider_institution.address.street_address_2,
                        "city": entry.provider_institution.address.city,
                        "state": entry.provider_institution.address.state,
                        "zip_code": entry.provider_institution.address.zip_code,
                        "country": entry.provider_institution.address.country,
                    }
                    if entry.provider_institution.address
                    else None,
                    "datetime_added": entry.datetime_created.isoformat(),
                }
            )

    return network_items


@app.post("/api/network", status_code=status.HTTP_201_CREATED)
async def add_to_network(
    network_entry: NetworkEntryCreate, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Add a provider or institution to user's network.
    Returns 409 if already in network.
    """
    # Check if already in network
    if network_entry.target_type == "provider":
        existing = await db.execute(
            select(UserProviderNetwork).filter(
                UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_id == network_entry.provider_id
            )
        )
    else:
        existing = await db.execute(
            select(UserProviderNetwork).filter(
                UserProviderNetwork.user_id == user.id,
                UserProviderNetwork.provider_institution_id == network_entry.provider_institution_id,
            )
        )

    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider/institution already in network")

    # Verify provider/institution exists
    if network_entry.target_type == "provider":
        provider_check = await db.execute(select(Provider).filter(Provider.id == network_entry.provider_id))
        if not provider_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        new_entry = UserProviderNetwork(user_id=user.id, provider_id=network_entry.provider_id)
    else:
        institution_check = await db.execute(
            select(ProviderInstitution).filter(ProviderInstitution.id == network_entry.provider_institution_id)
        )
        if not institution_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

        new_entry = UserProviderNetwork(user_id=user.id, provider_institution_id=network_entry.provider_institution_id)

    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)

    return {"id": str(new_entry.id), "message": "Added to network successfully"}


@app.delete("/api/network/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_network(
    entry_id: str, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Remove a provider/institution from user's network.
    Only allows removing user's own network entries.
    """
    result = await db.execute(
        select(UserProviderNetwork).filter(
            UserProviderNetwork.id == entry_id,
            UserProviderNetwork.user_id == user.id,  # Security: only user's own entries
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network entry not found")

    await db.delete(entry)
    await db.commit()

    return None


# Browse Endpoints (for adding to network)


@app.get("/api/browse/providers")
async def browse_all_providers(
    search: Optional[str] = None, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Browse ALL global providers for adding to network.
    Only shows global (non-custom) providers.
    Supports optional search parameter.
    Marks which providers are already in user's network.
    """
    # Get user's network provider IDs
    network_result = await db.execute(
        select(UserProviderNetwork.provider_id).filter(
            UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_id.isnot(None)
        )
    )
    network_provider_ids = set([row[0] for row in network_result.all()])

    # Build query for all global providers only
    query = (
        select(Provider)
        .options(
            selectinload(Provider.address), selectinload(Provider.institution).selectinload(ProviderInstitution.address)
        )
        .filter(Provider.global_provider == True)
    )

    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Provider.first_name.ilike(search_term),
                Provider.last_name.ilike(search_term),
                Provider.email.ilike(search_term),
            )
        )

    result = await db.execute(query)
    providers = result.scalars().all()

    return [
        {
            "id": str(provider.id),
            "first_name": provider.first_name,
            "last_name": provider.last_name,
            "full_name": provider.full_name,
            "email": provider.email,
            "phone": provider.phone,
            "in_network": provider.id in network_provider_ids,  # NEW FIELD
            "address": {
                "street_address_1": provider.address.street_address_1,
                "street_address_2": provider.address.street_address_2,
                "city": provider.address.city,
                "state": provider.address.state,
                "zip_code": provider.address.zip_code,
                "country": provider.address.country,
            }
            if provider.address
            else None,
            "institution": {
                "id": str(provider.institution.id),
                "name": provider.institution.name,
                "website": provider.institution.website,
            }
            if provider.institution
            else None,
        }
        for provider in providers
    ]


@app.get("/api/browse/provider-institutions")
async def browse_all_institutions(
    search: Optional[str] = None, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)
):
    """
    Browse ALL provider institutions for adding to network.
    Supports optional search parameter.
    Marks which institutions are already in user's network.
    """
    # Get user's network institution IDs
    network_result = await db.execute(
        select(UserProviderNetwork.provider_institution_id).filter(
            UserProviderNetwork.user_id == user.id, UserProviderNetwork.provider_institution_id.isnot(None)
        )
    )
    network_institution_ids = set([row[0] for row in network_result.all()])

    # Build query for all institutions
    query = select(ProviderInstitution).options(selectinload(ProviderInstitution.address))

    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(ProviderInstitution.name.ilike(search_term))

    result = await db.execute(query)
    institutions = result.scalars().all()

    return [
        {
            "id": str(inst.id),
            "name": inst.name,
            "type": inst.type,
            "website": inst.website,
            "phone": inst.phone,
            "email": inst.email,
            "in_network": inst.id in network_institution_ids,  # NEW FIELD
            "address": {
                "street_address_1": inst.address.street_address_1,
                "street_address_2": inst.address.street_address_2,
                "city": inst.address.city,
                "state": inst.address.state,
                "zip_code": inst.address.zip_code,
                "country": inst.address.country,
            }
            if inst.address
            else None,
        }
        for inst in institutions
    ]


# SQLAdmin Authentication Backend
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        """Handle admin login."""
        form = await request.form()
        email = form.get("username")  # SQLAdmin uses "username" field
        password = form.get("password")

        # Verify credentials using the same password helper as fastapi-users
        from pwdlib import PasswordHash

        password_hash = PasswordHash.recommended()

        async for session in get_db():
            try:
                # Get user by email
                result = await session.execute(select(User).filter(User.email == email))
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Verify password
                verified, _ = password_hash.verify_and_update(password, user.hashed_password)
                if not verified:
                    return False

                # Check if user is admin
                if not user.is_admin:
                    return False

                # Store user ID in session
                request.session.update({"user_id": str(user.id)})
                return True
            finally:
                await session.close()

        return False

    async def logout(self, request: Request) -> bool:
        """Handle admin logout."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Check if user is authenticated and is admin."""
        user_id = request.session.get("user_id")

        if not user_id:
            return False

        async for session in get_db():
            try:
                result = await session.execute(select(User).filter(User.id == user_id))
                user = result.scalar_one_or_none()

                if not user or not user.is_admin:
                    return False

                return True
            finally:
                await session.close()

        return False


# SQLAdmin Model Views
class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        User.phone_number,
        User.npi,
        User.is_admin,
        User.is_active,
        User.is_verified,
        User.is_superuser,
    ]
    column_searchable_list = [User.email, User.first_name, User.last_name, User.npi]
    column_sortable_list = [User.email, User.first_name, User.last_name, User.is_admin, User.is_active]
    can_create = True
    can_edit = True
    can_delete = True


class ProviderAdmin(ModelView, model=Provider):
    column_list = [
        Provider.id,
        Provider.first_name,
        Provider.last_name,
        Provider.email,
        Provider.phone,
        Provider.address_id,
        Provider.institution_id,
        Provider.datetime_created,
        Provider.datetime_updated,
    ]
    column_searchable_list = [Provider.first_name, Provider.last_name, Provider.email]
    column_sortable_list = [Provider.first_name, Provider.last_name, Provider.email, Provider.datetime_created]
    can_create = True
    can_edit = True
    can_delete = True


class ProviderInstitutionAdmin(ModelView, model=ProviderInstitution):
    column_list = [
        ProviderInstitution.id,
        ProviderInstitution.name,
        ProviderInstitution.type,
        ProviderInstitution.phone,
        ProviderInstitution.email,
        ProviderInstitution.website,
        ProviderInstitution.address_id,
        ProviderInstitution.datetime_created,
        ProviderInstitution.datetime_updated,
    ]
    column_searchable_list = [ProviderInstitution.name, ProviderInstitution.email]
    column_sortable_list = [ProviderInstitution.name, ProviderInstitution.type, ProviderInstitution.datetime_created]
    can_create = True
    can_edit = True
    can_delete = True


class PatientAdmin(ModelView, model=Patient):
    column_list = [
        Patient.id,
        Patient.first_name,
        Patient.last_name,
        Patient.sex,
        Patient.phone,
        Patient.phone_home,
        Patient.phone_mobile,
        Patient.email,
        Patient.date_of_birth,
        Patient.patient_id,
        Patient.medical_record_number,
        Patient.address_id,
        Patient.datetime_created,
        Patient.datetime_updated,
    ]
    column_searchable_list = [Patient.first_name, Patient.last_name, Patient.email, Patient.medical_record_number]
    column_sortable_list = [Patient.first_name, Patient.last_name, Patient.date_of_birth, Patient.datetime_created]
    can_create = True
    can_edit = True
    can_delete = True


class ReferralAdmin(ModelView, model=Referral):
    column_list = [
        Referral.id,
        Referral.user_id,
        Referral.patient_id,
        Referral.provider_id,
        Referral.provider_institution_id,
        Referral.status,
        Referral.notes,
        Referral.referral_date,
        Referral.datetime_created,
        Referral.datetime_updated,
    ]
    column_searchable_list = [Referral.notes]
    column_sortable_list = [Referral.status, Referral.referral_date, Referral.datetime_created]
    can_create = False
    can_edit = True
    can_delete = True


class AddressAdmin(ModelView, model=Address):
    column_list = [
        Address.id,
        Address.street_address_1,
        Address.street_address_2,
        Address.city,
        Address.state,
        Address.zip_code,
        Address.country,
        Address.datetime_created,
        Address.datetime_updated,
    ]
    column_searchable_list = [Address.city, Address.state, Address.zip_code, Address.street_address_1]
    column_sortable_list = [Address.city, Address.state, Address.zip_code, Address.datetime_created]
    can_create = True
    can_edit = True
    can_delete = True


class UserProviderNetworkAdmin(ModelView, model=UserProviderNetwork):
    column_list = [
        UserProviderNetwork.id,
        UserProviderNetwork.user_id,
        UserProviderNetwork.provider_id,
        UserProviderNetwork.provider_institution_id,
        UserProviderNetwork.datetime_created,
        UserProviderNetwork.datetime_updated,
    ]
    column_sortable_list = [UserProviderNetwork.datetime_created]
    can_create = True
    can_edit = True
    can_delete = True


# Create admin interface with authentication
authentication_backend = AdminAuth(secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"))
admin = Admin(app, engine, authentication_backend=authentication_backend)

# Add model views
admin.add_view(UserAdmin)
admin.add_view(ProviderAdmin)
admin.add_view(ProviderInstitutionAdmin)
admin.add_view(PatientAdmin)
admin.add_view(ReferralAdmin)
admin.add_view(AddressAdmin)
admin.add_view(UserProviderNetworkAdmin)
