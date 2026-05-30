from datetime import datetime

from pydantic import BaseModel


class ArtifactRead(BaseModel):
    id: str
    session_id: str
    run_id: str | None = None
    event_id: str | None = None
    kind: str
    media_type: str
    url: str
    tool_use_id: str | None = None
    created_at: datetime
