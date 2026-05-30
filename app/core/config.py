from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Computer Use Agent Backend"
    environment: str = "development"
    agent_mode: str = "mock"
    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    anthropic_tool_version: str = "computer_use_20250124"
    anthropic_max_tokens: int = Field(default=4096, ge=1)
    anthropic_only_n_most_recent_images: int | None = 3
    anthropic_system_prompt_suffix: str = ""
    anthropic_token_efficient_tools_beta: bool = False
    database_url: str = "sqlite:///./dev.db"
    max_concurrent_sessions: int = Field(default=5, ge=1)
    session_timeout_seconds: int = Field(default=1800, ge=1)
    agent_run_timeout_seconds: int = Field(default=300, ge=1)
    relay_request_timeout_seconds: int = Field(default=90, ge=1)
    bash_tool_timeout_seconds: int = Field(default=45, ge=1)
    vnc_base_url: str = "http://localhost:6080"
    vnc_path: str = "vnc.html"
    artifact_dir: str = "./artifacts"
    jwt_secret_key: SecretStr = SecretStr("development-only-change-me")
    jwt_expires_seconds: int = Field(default=86400, ge=60)
    api_key_encryption_secret: SecretStr = SecretStr("development-only-change-me")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
