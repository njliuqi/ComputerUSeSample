from enum import Enum

from pydantic import BaseModel


class VncStatus(str, Enum):
    ready = "ready"
    unavailable = "unavailable"


class VncConnectionRead(BaseModel):
    session_id: str
    status: VncStatus
    url: str | None
    view_only_url: str | None = None
