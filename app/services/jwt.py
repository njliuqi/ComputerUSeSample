import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import get_settings


class TokenError(ValueError):
    pass


def create_access_token(user_id: str, username: str) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + settings.jwt_expires_seconds,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Invalid token")

    signing_input = f"{parts[0]}.{parts[1]}"
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(parts[2], expected_signature):
        raise TokenError("Invalid token signature")

    payload = _b64_decode_json(parts[1])
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise TokenError("Token expired")
    if not payload.get("sub"):
        raise TokenError("Invalid token subject")
    return payload


def _sign(value: str) -> str:
    secret = get_settings().jwt_secret_key.get_secret_value().encode("utf-8")
    digest = hmac.new(secret, value.encode("utf-8"), hashlib.sha256).digest()
    return _b64_encode(digest)


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_encode(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Invalid token payload") from exc
    if not isinstance(payload, dict):
        raise TokenError("Invalid token payload")
    return payload
