from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.auth import get_current_user, get_user_from_token
from app.schemas.auth import UserRead
from app.schemas.artifacts import ArtifactRead
from app.services.auth import AuthService, get_auth_service
from app.services.artifacts import ArtifactService, get_artifact_service
from app.services.session_manager import SessionManager, get_session_manager

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/file")
async def get_artifact_file(
    artifact_id: str,
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    service: ArtifactService = Depends(get_artifact_service),
    manager: SessionManager = Depends(get_session_manager),
) -> FileResponse:
    current_user = get_artifact_request_user(authorization, token, auth_service)
    artifact = service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    session = manager.get_session(artifact.session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    path = service.get_artifact_path(artifact_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return FileResponse(path)


@router.get("/sessions/{session_id}", response_model=list[ArtifactRead])
async def list_session_artifacts(
    session_id: str,
    run_id: str | None = Query(default=None),
    current_user: UserRead = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
    manager: SessionManager = Depends(get_session_manager),
) -> list[ArtifactRead]:
    session = manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return service.list_session_artifacts(session_id, run_id=run_id)


def get_artifact_request_user(
    authorization: str | None,
    token: str | None,
    auth_service: AuthService,
) -> UserRead:
    if authorization and authorization.startswith("Bearer "):
        return get_user_from_token(authorization.removeprefix("Bearer ").strip(), auth_service)
    if token:
        return get_user_from_token(token, auth_service)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
