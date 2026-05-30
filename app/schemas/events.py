from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.sessions import utc_now


class EventType(str, Enum):
    user_message = "user_message"
    agent_message = "agent_message"
    tool_started = "tool_started"
    tool_result = "tool_result"
    screenshot = "screenshot"
    completed = "completed"
    error = "error"


class EventRead(BaseModel):
    id: str
    session_id: str
    run_id: str | None = None
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


def new_event(
    session_id: str,
    event_type: EventType,
    payload: dict[str, Any] | None = None,
) -> EventRead:
    payload = payload or {}
    return EventRead(
        id=str(uuid4()),
        session_id=session_id,
        run_id=payload.get("run_id"),
        type=event_type,
        payload=payload,
        created_at=utc_now(),
    )
