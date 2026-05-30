from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    terminated = "terminated"
    failed = "failed"


class SessionCreate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    user_id: str | None = Field(default=None, max_length=36)


class SessionRead(BaseModel):
    id: str
    user_id: str | None = None
    status: SessionStatus
    name: str | None = None
    created_at: datetime
    updated_at: datetime
    error: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_session(name: str | None = None, user_id: str | None = None) -> SessionRead:
    now = utc_now()
    return SessionRead(
        id=str(uuid4()),
        user_id=user_id,
        status=SessionStatus.created,
        name=name,
        created_at=now,
        updated_at=now,
    )
