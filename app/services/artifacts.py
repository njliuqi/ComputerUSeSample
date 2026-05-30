import base64
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import ArtifactRecord
from app.db.session import get_db_session
from app.schemas.artifacts import ArtifactRead
from app.schemas.sessions import utc_now


class ArtifactService:
    def save_screenshot(
        self,
        session_id: str,
        event_id: str,
        base64_image: str,
        media_type: str = "image/png",
        tool_use_id: str | None = None,
        run_id: str | None = None,
    ) -> ArtifactRead:
        artifact_id = str(uuid4())
        suffix = ".png" if media_type == "image/png" else ".bin"
        session_dir = Path(get_settings().artifact_dir) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / f"{artifact_id}{suffix}"
        file_path.write_bytes(base64.b64decode(base64_image))

        now = utc_now()
        with get_db_session() as db:
            record = ArtifactRecord(
                id=artifact_id,
                session_id=session_id,
                run_id=run_id,
                event_id=event_id,
                kind="screenshot",
                media_type=media_type,
                file_path=str(file_path),
                tool_use_id=tool_use_id,
                created_at=now,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._artifact_from_record(record)

    def list_session_artifacts(self, session_id: str, run_id: str | None = None) -> list[ArtifactRead]:
        with get_db_session() as db:
            query = (
                select(ArtifactRecord)
                .where(ArtifactRecord.session_id == session_id)
                .order_by(ArtifactRecord.created_at)
            )
            if run_id:
                query = query.where(ArtifactRecord.run_id == run_id)
            records = db.scalars(query).all()
            return [self._artifact_from_record(record) for record in records]

    def get_artifact_path(self, artifact_id: str) -> Path | None:
        with get_db_session() as db:
            record = db.get(ArtifactRecord, artifact_id)
            if record is None:
                return None
            return Path(record.file_path)

    def get_artifact(self, artifact_id: str) -> ArtifactRead | None:
        with get_db_session() as db:
            record = db.get(ArtifactRecord, artifact_id)
            if record is None:
                return None
            return self._artifact_from_record(record)

    def clear(self) -> None:
        with get_db_session() as db:
            db.query(ArtifactRecord).delete()
            db.commit()

    def _artifact_from_record(self, record: ArtifactRecord) -> ArtifactRead:
        return ArtifactRead(
            id=record.id,
            session_id=record.session_id,
            run_id=record.run_id,
            event_id=record.event_id,
            kind=record.kind,
            media_type=record.media_type,
            url=f"/api/artifacts/{record.id}/file",
            tool_use_id=record.tool_use_id,
            created_at=record.created_at,
        )


artifact_service = ArtifactService()


def get_artifact_service() -> ArtifactService:
    return artifact_service
