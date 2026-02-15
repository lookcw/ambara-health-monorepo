"""
Pydantic schemas for Faxage fax records.
"""

from pydantic import BaseModel


class FaxageReceivedFax(BaseModel):
    """A single fax record from Faxage listfax response."""

    recvid: str
    revdate: str
    starttime: str
    cid: str
    dnis: str
    filename: str
    pagecount: str
    tsid: str
