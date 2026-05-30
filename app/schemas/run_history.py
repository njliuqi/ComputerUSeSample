from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.artifacts import ArtifactRead
from app.schemas.events import EventRead


RunResult = Literal["running", "success", "failed"]


class RunHistoryRead(BaseModel):
    id: str
    session_id: str
    user_id: str | None = None
    message_id: str | None = None
    prompt: str
    started_at: datetime
    completed_at: datetime | None = None
    response_time_ms: int | None = None
    result: RunResult
    model: str = ""
    base_url: str = ""
    error: str = ""


class RunDetailRead(BaseModel):
    run: RunHistoryRead
    events: list[EventRead]
    artifacts: list[ArtifactRead]
