from pydantic import BaseModel


class PublicConfigRead(BaseModel):
    environment: str
    agent_mode: str
    anthropic_model: str
    anthropic_base_url_configured: bool
    vnc_base_url: str
