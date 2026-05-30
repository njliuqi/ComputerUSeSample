from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_current_user
from app.schemas.auth import UserRead
from app.schemas.relay_config import RelayConfigListRead, RelayConfigRead, RelayConfigSave
from app.services.relay_config import RelayConfigService, get_relay_config_service

router = APIRouter(prefix="/api/relay-config", tags=["relay-config"])


@router.get("", response_model=RelayConfigListRead)
async def list_relay_configs(
    current_user: UserRead = Depends(get_current_user),
    service: RelayConfigService = Depends(get_relay_config_service),
) -> RelayConfigListRead:
    return service.list_configs(current_user.id)


@router.post("/test-and-save", response_model=RelayConfigRead)
async def test_and_save_relay_config(
    payload: RelayConfigSave,
    current_user: UserRead = Depends(get_current_user),
    service: RelayConfigService = Depends(get_relay_config_service),
) -> RelayConfigRead:
    try:
        return service.test_and_save(
            user_id=current_user.id,
            api_url=payload.api_url,
            api_key=payload.api_key,
            model=payload.model,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
