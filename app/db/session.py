from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_relay_configs_schema()
    _migrate_sessions_schema()
    _migrate_task_runs_schema()
    _migrate_events_schema()
    _migrate_artifacts_schema()


def _migrate_relay_configs_schema() -> None:
    inspector = inspect(engine)
    if "relay_configs" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        dialect = connection.dialect.name
        for constraint in inspector.get_unique_constraints("relay_configs"):
            if constraint.get("column_names") == ["user_id"] and constraint.get("name"):
                if dialect == "postgresql":
                    connection.execute(
                        text(f'ALTER TABLE relay_configs DROP CONSTRAINT IF EXISTS "{constraint["name"]}"')
                    )

        for index in inspector.get_indexes("relay_configs"):
            if index.get("unique") and index.get("column_names") == ["user_id"] and index.get("name"):
                connection.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_relay_configs_user_id ON relay_configs (user_id)"))

        columns = {column["name"] for column in inspector.get_columns("relay_configs")}
        if "models" not in columns:
            if dialect == "postgresql":
                connection.execute(text("ALTER TABLE relay_configs ADD COLUMN models JSON NOT NULL DEFAULT '[]'"))
            else:
                connection.execute(text("ALTER TABLE relay_configs ADD COLUMN models JSON NOT NULL DEFAULT '[]'"))
        if dialect == "postgresql":
            connection.execute(
                text("UPDATE relay_configs SET models = json_build_array(model) WHERE models::text = '[]' OR models IS NULL")
            )
        else:
            connection.execute(text("UPDATE relay_configs SET models = json_array(model) WHERE models = '[]' OR models IS NULL"))

        from app.services.secret_crypto import encrypt_secret, is_encrypted_secret

        rows = connection.execute(text("SELECT id, api_key FROM relay_configs")).mappings().all()
        for row in rows:
            api_key = row["api_key"]
            if not api_key or is_encrypted_secret(api_key):
                continue
            connection.execute(
                text("UPDATE relay_configs SET api_key = :api_key WHERE id = :id"),
                {"id": row["id"], "api_key": encrypt_secret(api_key)},
            )


def _migrate_sessions_schema() -> None:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "user_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR(36) NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"))


def _migrate_task_runs_schema() -> None:
    inspector = inspect(engine)
    if "task_runs" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine)
        return

    with engine.begin() as connection:
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_task_runs_session_id ON task_runs (session_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_task_runs_user_id ON task_runs (user_id)"))


def _migrate_artifacts_schema() -> None:
    inspector = inspect(engine)
    if "artifacts" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("artifacts")}
    with engine.begin() as connection:
        if "run_id" not in columns:
            connection.execute(text("ALTER TABLE artifacts ADD COLUMN run_id VARCHAR(36) NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_artifacts_run_id ON artifacts (run_id)"))


def _migrate_events_schema() -> None:
    inspector = inspect(engine)
    if "events" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("events")}
    with engine.begin() as connection:
        dialect = connection.dialect.name
        if "run_id" not in columns:
            connection.execute(text("ALTER TABLE events ADD COLUMN run_id VARCHAR(36) NULL"))
        if dialect == "postgresql":
            connection.execute(
                text(
                    "UPDATE events SET run_id = payload->>'run_id' "
                    "WHERE run_id IS NULL AND payload::jsonb ? 'run_id'"
                )
            )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_events_run_id ON events (run_id)"))


def get_db_session() -> Session:
    return SessionLocal()
