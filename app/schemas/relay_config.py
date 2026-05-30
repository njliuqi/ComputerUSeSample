from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ConnectionStatus = Literal["idle", "success", "failed"]


class RelayConfigRead(BaseModel):
    id: str | None = None
    user_id: str
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    models: list[str] = []
    connection_status: ConnectionStatus = "idle"
    last_tested_at: datetime | None = None


class RelayConfigListRead(BaseModel):
    user_id: str
    configs: list[RelayConfigRead] = []


class RelayConfigSave(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)
    api_url: str = Field(min_length=1, max_length=2048)
    api_key: str = Field(min_length=1, max_length=4096)
    model: str = Field(default="", max_length=120)
