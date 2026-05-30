from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.artifacts import router as artifacts_router
from app.api.auth import router as auth_router
from app.api.relay_config import router as relay_config_router
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router
from app.core.config import get_settings
from app.db.session import init_db
from app.schemas.config import PublicConfigRead
from app.schemas.health import HealthRead


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthRead, tags=["health"])
    async def health() -> HealthRead:
        return HealthRead(status="ok", environment=settings.environment)

    @app.get("/api/config", response_model=PublicConfigRead, tags=["config"])
    async def public_config() -> PublicConfigRead:
        return PublicConfigRead(
            environment=settings.environment,
            agent_mode=settings.agent_mode,
            anthropic_model=settings.anthropic_model,
            anthropic_base_url_configured=bool(settings.anthropic_base_url),
            vnc_base_url=settings.vnc_base_url,
        )

    app.include_router(auth_router)
    app.include_router(artifacts_router)
    app.include_router(relay_config_router)
    app.include_router(sessions_router)
    app.include_router(websocket_router)
    return app


app = create_app()
