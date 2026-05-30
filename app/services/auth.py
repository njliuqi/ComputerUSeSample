import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import RelayConfigRecord, UserRecord
from app.db.session import get_db_session
from app.schemas.auth import UserRead


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    password_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt.encode("utf-8"),
        120_000,
    )
    return digest.hex(), password_salt


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    digest, _ = hash_password(password, password_salt)
    return secrets.compare_digest(digest, password_hash)


class AuthService:
    def register(self, username: str, password: str, email: str | None = None) -> UserRead:
        now = datetime.now(timezone.utc)
        password_hash, password_salt = hash_password(password)
        username_value = username.strip()
        email_value = email.strip() if email else None

        with get_db_session() as db:
            user = UserRecord(
                id=str(uuid4()),
                username=username_value,
                email=email_value,
                password_hash=password_hash,
                password_salt=password_salt,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise ValueError("Username already exists") from exc
            db.refresh(user)
            return self._user_from_record(user)

    def authenticate(self, username: str, password: str) -> UserRead | None:
        with get_db_session() as db:
            user = db.scalars(select(UserRecord).where(UserRecord.username == username.strip())).first()
            if user is None:
                return None
            if not verify_password(password, user.password_hash, user.password_salt):
                return None
            return self._user_from_record(user)

    def get_user(self, user_id: str) -> UserRead | None:
        with get_db_session() as db:
            user = db.get(UserRecord, user_id)
            if user is None:
                return None
            return self._user_from_record(user)

    def clear(self) -> None:
        with get_db_session() as db:
            db.query(RelayConfigRecord).delete()
            db.query(UserRecord).delete()
            db.commit()

    def _user_from_record(self, record: UserRecord) -> UserRead:
        return UserRead(
            id=record.id,
            username=record.username,
            email=record.email,
            created_at=record.created_at,
        )


auth_service = AuthService()


def get_auth_service() -> AuthService:
    return auth_service
