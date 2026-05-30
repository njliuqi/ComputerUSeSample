from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas.auth import AuthRead, UserLogin, UserRead, UserRegister
from app.services.auth import AuthService, get_auth_service
from app.services.jwt import TokenError, create_access_token, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def build_auth_response(user: UserRead) -> AuthRead:
    return AuthRead(token=create_access_token(user.id, user.username), user=user)


def get_user_from_token(token: str, service: AuthService) -> UserRead:
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = service.get_user(str(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token user not found")
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
) -> UserRead:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_from_token(token, service)


@router.post("/register", response_model=AuthRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    service: AuthService = Depends(get_auth_service),
) -> AuthRead:
    try:
        user = service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return build_auth_response(user)


@router.post("/login", response_model=AuthRead)
async def login(
    payload: UserLogin,
    service: AuthService = Depends(get_auth_service),
) -> AuthRead:
    user = service.authenticate(username=payload.username, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return build_auth_response(user)
