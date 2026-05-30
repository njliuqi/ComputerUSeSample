from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.sessions import utc_now


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    user_id: str | None = Field(default=None, max_length=36)
    relay_config_id: str | None = Field(default=None, max_length=36)
    relay_api_url: str | None = Field(default=None, max_length=2048)
    relay_api_key: str | None = Field(default=None, max_length=4096)
    model: str | None = Field(default=None, max_length=120)


class MessageRead(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime


def new_message(session_id: str, role: MessageRole, content: str) -> MessageRead:
    return MessageRead(
        id=str(uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        created_at=utc_now(),
    )
