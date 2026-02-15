"""
Faxage fax API service for polling inbound faxes.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

FAXAGE_URL = "https://www.faxage.com/httpsfax.php"


def get_faxage_credentials() -> tuple[str, str, str]:
    """
    Get Faxage credentials based on environment.

    Returns:
        Tuple of (username, company, password)
    """
    env = os.getenv("ENVIRONMENT", "local")

    if env in ["staging", "production"]:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

        def _get_secret(name: str) -> str:
            secret_name = f"projects/{project_id}/secrets/{name}/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            return response.payload.data.decode("UTF-8")

        return (
            _get_secret("faxage-username"),
            _get_secret("faxage-company"),
            _get_secret("faxage-password"),
        )
    else:
        return (
            os.getenv("FAXAGE_USERNAME", ""),
            os.getenv("FAXAGE_COMPANY", ""),
            os.getenv("FAXAGE_PASSWORD", ""),
        )


async def list_received_faxes(username: str, company: str, password: str) -> list[dict[str, str]]:
    """
    List received faxes from Faxage inbox.

    POST to Faxage with operation=listfax. Response is tab-delimited with fields:
    recvid, revdate, starttime, cid, dnis, filename, pagecount, tsid

    Returns:
        List of dicts with fax metadata.
    """
    data = {
        "username": username,
        "company": company,
        "password": password,
        "operation": "listfax",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(FAXAGE_URL, data=data, timeout=30.0)
        response.raise_for_status()

    body = response.text.strip()

    # Faxage returns empty body or a single blank line if no faxes
    if not body:
        return []

    fields = ["recvid", "revdate", "starttime", "cid", "dnis", "filename", "pagecount", "tsid"]
    results: list[dict[str, str]] = []

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= len(fields):
            results.append(dict(zip(fields, parts, strict=False)))
        else:
            logger.warning(f"Faxage listfax: unexpected line format: {line!r}")

    return results


async def get_fax_pdf(username: str, company: str, password: str, recvid: str) -> bytes:
    """
    Download a received fax PDF from Faxage.

    Returns:
        Binary PDF content.
    """
    data = {
        "username": username,
        "company": company,
        "password": password,
        "operation": "getfax",
        "faxid": recvid,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(FAXAGE_URL, data=data, timeout=60.0)
        response.raise_for_status()

    return response.content


async def delete_fax(username: str, company: str, password: str, recvid: str) -> str:
    """
    Delete a received fax from Faxage inbox after processing.

    Returns:
        Response text from Faxage.
    """
    data = {
        "username": username,
        "company": company,
        "password": password,
        "operation": "delfax",
        "faxid": recvid,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(FAXAGE_URL, data=data, timeout=30.0)
        response.raise_for_status()

    return response.text
