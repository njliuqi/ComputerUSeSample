from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.db.models import RelayConfigRecord, UserRecord
from app.db.session import get_db_session
from app.schemas.relay_config import RelayConfigListRead, RelayConfigRead
from app.services.secret_crypto import decrypt_secret, encrypt_secret


def normalize_anthropic_base_url(api_url: str) -> str:
    base_url = api_url.strip().rstrip("/")
    if base_url.lower().endswith("/v1"):
        return base_url[:-3].rstrip("/")
    return base_url


class RelayConfigService:
    def list_configs(self, user_id: str) -> RelayConfigListRead:
        with get_db_session() as db:
            records = db.scalars(
                select(RelayConfigRecord)
                .where(RelayConfigRecord.user_id == user_id)
                .order_by(RelayConfigRecord.updated_at.desc())
            ).all()
            return RelayConfigListRead(
                user_id=user_id,
                configs=[self._config_from_record(record) for record in records],
            )

    def get_latest_success_config(self, user_id: str) -> RelayConfigRead | None:
        with get_db_session() as db:
            record = db.scalars(
                select(RelayConfigRecord)
                .where(
                    RelayConfigRecord.user_id == user_id,
                    RelayConfigRecord.connection_status == "success",
                )
                .order_by(RelayConfigRecord.updated_at.desc())
            ).first()
            if record is None:
                return None
            return self._config_from_record(record)

    def get_success_config(self, user_id: str, relay_config_id: str) -> RelayConfigRead | None:
        with get_db_session() as db:
            record = db.scalars(
                select(RelayConfigRecord).where(
                    RelayConfigRecord.id == relay_config_id,
                    RelayConfigRecord.user_id == user_id,
                    RelayConfigRecord.connection_status == "success",
                )
            ).first()
            if record is None:
                return None
            return self._config_from_record(record)

    def test_and_save(self, user_id: str, api_url: str, api_key: str, model: str) -> RelayConfigRead:
        raw_api_url_value = api_url.strip()
        api_url_value = normalize_anthropic_base_url(raw_api_url_value)
        api_key_value = api_key.strip()
        model_value = model.strip()
        available_models = self._test_connection(raw_api_url_value, api_key_value)
        if not self._is_valid_api_url(raw_api_url_value) or not api_key_value or not available_models:
            self._mark_config_failed(user_id, api_url_value)
            raise ValueError("Connection test failed")
        if not model_value:
            model_value = available_models[0]
        if model_value not in available_models:
            self._mark_config_failed(user_id, api_url_value)
            raise ValueError("Selected model is not available from this Relay API configuration")

        now = datetime.now(timezone.utc)
        encrypted_api_key = encrypt_secret(api_key_value)
        with get_db_session() as db:
            if db.get(UserRecord, user_id) is None:
                raise LookupError("User not found")

            record = db.scalars(
                select(RelayConfigRecord).where(
                    RelayConfigRecord.user_id == user_id,
                    RelayConfigRecord.api_url == api_url_value,
                )
            ).first()
            if record is None:
                record = RelayConfigRecord(
                    id=str(uuid4()),
                    user_id=user_id,
                    api_url=api_url_value,
                    api_key=encrypted_api_key,
                    model=model_value,
                    models=available_models,
                    connection_status="success",
                    last_tested_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(record)
            else:
                record.api_url = api_url_value
                record.api_key = encrypted_api_key
                record.model = model_value
                record.models = available_models
                record.connection_status = "success"
                record.last_tested_at = now
                record.updated_at = now
            db.commit()
            db.refresh(record)
            return self._config_from_record(record)

    def clear(self) -> None:
        with get_db_session() as db:
            db.query(RelayConfigRecord).delete()
            db.commit()

    def _mark_config_failed(self, user_id: str, api_url: str) -> None:
        now = datetime.now(timezone.utc)
        with get_db_session() as db:
            record = db.scalars(
                select(RelayConfigRecord).where(
                    RelayConfigRecord.user_id == user_id,
                    RelayConfigRecord.api_url == api_url,
                )
            ).first()
            if record is None:
                return
            record.connection_status = "failed"
            record.last_tested_at = now
            record.updated_at = now
            db.commit()

    def _is_valid_api_url(self, api_url: str) -> bool:
        parsed = urlparse(api_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _test_connection(self, api_url: str, api_key: str) -> list[str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        for models_url in self._models_urls(api_url):
            try:
                response = httpx.get(models_url, headers=headers, timeout=8)
            except httpx.HTTPError:
                continue
            if not 200 <= response.status_code < 300:
                continue

            try:
                body = response.json()
            except ValueError:
                continue

            data = body.get("data", []) if isinstance(body, dict) else []
            models = []
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    models.append(str(item["id"]))
                elif isinstance(item, str):
                    models.append(item)
            if models:
                return models
        return []

    def _models_urls(self, api_url: str) -> list[str]:
        raw_base_url = api_url.strip().rstrip("/")
        normalized_base_url = normalize_anthropic_base_url(api_url)
        candidates = []
        if raw_base_url.lower().endswith("/v1"):
            candidates.append(f"{raw_base_url}/models")
        candidates.extend(
            [
                f"{normalized_base_url}/v1/models",
                f"{normalized_base_url}/models",
            ]
        )
        return list(dict.fromkeys(candidates))

    def _config_from_record(self, record: RelayConfigRecord) -> RelayConfigRead:
        return RelayConfigRead(
            id=record.id,
            user_id=record.user_id,
            api_url=record.api_url,
            api_key=decrypt_secret(record.api_key),
            model=record.model,
            models=record.models or ([record.model] if record.model else []),
            connection_status=record.connection_status,
            last_tested_at=record.last_tested_at,
        )


relay_config_service = RelayConfigService()


def get_relay_config_service() -> RelayConfigService:
    return relay_config_service
