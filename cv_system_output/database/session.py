"""
database/session.py — Engine, session factory, and base declarative model.

Using SQLAlchemy 2.0 style. Swap DATABASE_URL in config to PostgreSQL for production.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from config import settings
from logger import get_logger

log = get_logger(__name__)

# SQLite needs check_same_thread=False; ignored by other dialects
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,        # Log SQL in debug mode
    pool_pre_ping=True,         # Detect stale connections
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Ensures the session is always closed, even on exception.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        log.error(f"Database session error: {exc}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables defined in ORM models. Called on application startup."""
    log.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    _ensure_runtime_schema()
    log.info("Database tables ready.")


def _ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if "candidates" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("candidates")}
    ddl_statements: list[str] = []

    if "subcategory" not in existing_columns:
        ddl_statements.append("ALTER TABLE candidates ADD COLUMN subcategory VARCHAR(150)")
    if "years_experience" not in existing_columns:
        ddl_statements.append("ALTER TABLE candidates ADD COLUMN years_experience FLOAT")
    if "seniority_level" not in existing_columns:
        ddl_statements.append(
            "ALTER TABLE candidates ADD COLUMN seniority_level VARCHAR(50)"
        )
    if "saved_upload_filename" not in existing_columns:
        ddl_statements.append(
            "ALTER TABLE candidates ADD COLUMN saved_upload_filename VARCHAR(255)"
        )

    if "upload_logs" in inspector.get_table_names():
        upload_log_columns = {
            column["name"] for column in inspector.get_columns("upload_logs")
        }
        if "saved_upload_filename" not in upload_log_columns:
            ddl_statements.append(
                "ALTER TABLE upload_logs ADD COLUMN saved_upload_filename VARCHAR(255)"
            )

    if "worker_users" in inspector.get_table_names():
        worker_user_columns = {
            column["name"] for column in inspector.get_columns("worker_users")
        }
        if "temporary_password" not in worker_user_columns:
            ddl_statements.append(
                "ALTER TABLE worker_users ADD COLUMN temporary_password VARCHAR(255)"
            )

    if not ddl_statements:
        return

    with engine.begin() as connection:
        for ddl in ddl_statements:
            connection.execute(text(ddl))
