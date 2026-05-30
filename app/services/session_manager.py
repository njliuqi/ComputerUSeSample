from datetime import timedelta, timezone
from threading import RLock

from uuid import uuid4

from sqlalchemy import delete, select

from app.db.models import ArtifactRecord, EventRecord, MessageRecord, SessionRecord, TaskRunRecord
from app.db.session import get_db_session
from app.schemas.artifacts import ArtifactRead
from app.schemas.events import EventRead, EventType, new_event
from app.schemas.messages import MessageRead, MessageRole
from app.schemas.run_history import RunDetailRead, RunHistoryRead
from app.schemas.sessions import SessionRead, SessionStatus, new_session, utc_now
from app.services.websocket_manager import get_websocket_manager


class SessionManager:
    def __init__(self) -> None:
        self._lock = RLock()

    def create_session(self, name: str | None = None, user_id: str | None = None) -> SessionRead:
        session = new_session(name=name, user_id=user_id)
        with self._lock:
            with get_db_session() as db:
                db.add(
                    SessionRecord(
                        id=session.id,
                        user_id=session.user_id,
                        name=session.name,
                        status=session.status.value,
                        error=session.error,
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                    )
                )
                db.commit()
        return session

    def list_sessions(self, user_id: str | None = None) -> list[SessionRead]:
        self.expire_stale_running_sessions()
        with self._lock:
            with get_db_session() as db:
                query = select(SessionRecord).order_by(SessionRecord.created_at)
                if user_id:
                    query = query.where(SessionRecord.user_id == user_id)
                records = db.scalars(query).all()
                return [self._session_from_record(record) for record in records]

    def get_session(self, session_id: str) -> SessionRead | None:
        self.expire_stale_running_sessions()
        with self._lock:
            with get_db_session() as db:
                record = db.get(SessionRecord, session_id)
                if record is None:
                    return None
                return self._session_from_record(record)

    def terminate_session(self, session_id: str) -> SessionRead | None:
        with self._lock:
            return self._update_session(session_id, status=SessionStatus.terminated)

    def start_session(self, session_id: str) -> SessionRead | None:
        with self._lock:
            return self._update_session(session_id, status=SessionStatus.running)

    def complete_session(self, session_id: str) -> SessionRead | None:
        with self._lock:
            return self._update_session(session_id, status=SessionStatus.completed)

    def fail_session(self, session_id: str, error: str, run_id: str | None = None) -> SessionRead | None:
        with self._lock:
            updated_session = self._update_session(session_id, status=SessionStatus.failed, error=error)
            if updated_session is None:
                return None
            payload = {"message": error}
            if run_id:
                payload["run_id"] = run_id
            self.add_event(new_event(session_id, EventType.error, payload))
            return updated_session

    def add_message(self, message: MessageRead) -> MessageRead:
        with self._lock:
            with get_db_session() as db:
                db.add(
                    MessageRecord(
                        id=message.id,
                        session_id=message.session_id,
                        role=message.role.value,
                        content=message.content,
                        created_at=message.created_at,
                    )
                )
                db.commit()
        return message

    def list_messages(self, session_id: str) -> list[MessageRead] | None:
        with self._lock:
            with get_db_session() as db:
                if db.get(SessionRecord, session_id) is None:
                    return None
                records = db.scalars(
                    select(MessageRecord)
                    .where(MessageRecord.session_id == session_id)
                    .order_by(MessageRecord.created_at)
                ).all()
                return [self._message_from_record(record) for record in records]

    def add_event(self, event: EventRead) -> EventRead:
        if event.run_id is None and event.payload.get("run_id"):
            event = EventRead(
                id=event.id,
                session_id=event.session_id,
                run_id=event.payload.get("run_id"),
                type=event.type,
                payload=event.payload,
                created_at=event.created_at,
            )
        event = self._attach_screenshot_artifact(event)
        with self._lock:
            with get_db_session() as db:
                db.add(
                    EventRecord(
                        id=event.id,
                        session_id=event.session_id,
                        run_id=event.run_id,
                        type=event.type.value,
                        payload=event.payload,
                        created_at=event.created_at,
                    )
                )
                db.commit()
        get_websocket_manager().broadcast_event_nowait(event)
        from app.services.desktop_log import get_desktop_log_service

        get_desktop_log_service().write_event(event)
        return event

    def list_events(self, session_id: str, run_id: str | None = None) -> list[EventRead] | None:
        with self._lock:
            with get_db_session() as db:
                if db.get(SessionRecord, session_id) is None:
                    return None
                query = (
                    select(EventRecord)
                    .where(EventRecord.session_id == session_id)
                    .order_by(EventRecord.created_at)
                )
                if run_id:
                    query = query.where(EventRecord.run_id == run_id)
                records = db.scalars(query).all()
                return [self._event_from_record(record) for record in records]

    def list_run_history(self, user_id: str | None = None) -> list[RunHistoryRead]:
        self.expire_stale_running_sessions()
        with self._lock:
            with get_db_session() as db:
                query = select(TaskRunRecord).order_by(TaskRunRecord.started_at.desc())
                if user_id:
                    query = query.where(TaskRunRecord.user_id == user_id)
                return [self._run_history_from_record(record) for record in db.scalars(query).all()]

    def get_run_history(self, run_id: str, user_id: str | None = None) -> RunHistoryRead | None:
        with self._lock:
            with get_db_session() as db:
                record = db.get(TaskRunRecord, run_id)
                if record is None or (user_id and record.user_id != user_id):
                    return None
                return self._run_history_from_record(record)

    def get_run_detail(
        self,
        run_id: str,
        artifacts: list[ArtifactRead],
        user_id: str | None = None,
    ) -> RunDetailRead | None:
        run = self.get_run_history(run_id, user_id=user_id)
        if run is None:
            return None
        events = self.list_events(run.session_id, run_id=run.id) or []
        return RunDetailRead(run=run, events=events, artifacts=artifacts)

    def create_task_run(
        self,
        session_id: str,
        user_id: str,
        message_id: str,
        prompt: str,
        model: str = "",
        base_url: str = "",
    ) -> RunHistoryRead:
        now = utc_now()
        record = TaskRunRecord(
            id=str(uuid4()),
            session_id=session_id,
            user_id=user_id,
            message_id=message_id,
            prompt=prompt,
            status="running",
            model=model,
            base_url=base_url,
            error="",
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            with get_db_session() as db:
                db.add(record)
                db.commit()
                db.refresh(record)
                return self._run_history_from_record(record)

    def finish_task_run(self, run_id: str, result: str, error: str = "") -> RunHistoryRead | None:
        now = utc_now()
        with self._lock:
            with get_db_session() as db:
                record = db.get(TaskRunRecord, run_id)
                if record is None:
                    return None
                record.status = result
                record.error = error
                record.completed_at = now
                record.updated_at = now
                db.commit()
                db.refresh(record)
                return self._run_history_from_record(record)

    def expire_stale_running_sessions(self) -> int:
        from app.core.config import get_settings

        expired = 0
        cutoff = utc_now() - timedelta(seconds=get_settings().session_timeout_seconds)
        with self._lock:
            with get_db_session() as db:
                records = db.scalars(
                    select(SessionRecord).where(SessionRecord.status == SessionStatus.running.value)
                ).all()
                for record in records:
                    updated_at = record.updated_at
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    if updated_at > cutoff:
                        continue
                    record.status = SessionStatus.failed.value
                    record.error = "Session timed out while running."
                    record.updated_at = utc_now()
                    run_records = db.scalars(
                        select(TaskRunRecord).where(
                            TaskRunRecord.session_id == record.id,
                            TaskRunRecord.status == "running",
                        )
                    ).all()
                    for run_record in run_records:
                        run_record.status = "failed"
                        run_record.error = "Session timed out while running."
                        run_record.completed_at = record.updated_at
                        run_record.updated_at = record.updated_at
                    expired += 1
                db.commit()
        return expired

    def clear(self) -> None:
        with self._lock:
            with get_db_session() as db:
                db.execute(delete(ArtifactRecord))
                db.execute(delete(EventRecord))
                db.execute(delete(MessageRecord))
                db.execute(delete(TaskRunRecord))
                db.execute(delete(SessionRecord))
                db.commit()

    def _update_session(
        self,
        session_id: str,
        status: SessionStatus,
        error: str | None = None,
    ) -> SessionRead | None:
        with get_db_session() as db:
            record = db.get(SessionRecord, session_id)
            if record is None:
                return None

            record.status = status.value
            record.updated_at = utc_now()
            record.error = error
            db.commit()
            db.refresh(record)
            return self._session_from_record(record)

    def _session_from_record(self, record: SessionRecord) -> SessionRead:
        return SessionRead(
            id=record.id,
            user_id=record.user_id,
            name=record.name,
            status=SessionStatus(record.status),
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _message_from_record(self, record: MessageRecord) -> MessageRead:
        return MessageRead(
            id=record.id,
            session_id=record.session_id,
            role=MessageRole(record.role),
            content=record.content,
            created_at=record.created_at,
        )

    def _event_from_record(self, record: EventRecord) -> EventRead:
        return EventRead(
            id=record.id,
            session_id=record.session_id,
            run_id=record.run_id,
            type=EventType(record.type),
            payload=record.payload,
            created_at=record.created_at,
        )

    def _run_history_from_record(self, record: TaskRunRecord) -> RunHistoryRead:
        response_time_ms = None
        if record.completed_at is not None:
            response_time_ms = max(0, int((record.completed_at - record.started_at).total_seconds() * 1000))
        return RunHistoryRead(
            id=record.id,
            session_id=record.session_id,
            user_id=record.user_id,
            message_id=record.message_id,
            prompt=record.prompt,
            started_at=record.started_at,
            completed_at=record.completed_at,
            response_time_ms=response_time_ms,
            result=record.status,
            model=record.model,
            base_url=record.base_url,
            error=record.error,
        )

    def _attach_screenshot_artifact(self, event: EventRead) -> EventRead:
        base64_image = event.payload.get("base64_image")
        if event.type != EventType.screenshot or not base64_image:
            return event

        from app.services.artifacts import get_artifact_service

        artifact = get_artifact_service().save_screenshot(
            session_id=event.session_id,
            event_id=event.id,
            base64_image=base64_image,
            media_type=event.payload.get("media_type", "image/png"),
            tool_use_id=event.payload.get("tool_use_id"),
            run_id=event.payload.get("run_id"),
        )
        payload = {
            **event.payload,
            "artifact_id": artifact.id,
            "artifact_url": artifact.url,
        }
        return EventRead(
            id=event.id,
            session_id=event.session_id,
            run_id=event.run_id,
            type=event.type,
            payload=payload,
            created_at=event.created_at,
        )


session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return session_manager
