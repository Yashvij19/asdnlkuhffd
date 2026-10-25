"""
Database engine, session management, and table bootstrap using SQLAlchemy 2.0.
Supports SQLite (local & serverless read-only mode) and PostgreSQL.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.logging import get_logger

logger = get_logger("app.db")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


def get_engine_args(database_url: str) -> dict[str, Any]:
    """Configure engine arguments based on database backend."""
    engine_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        engine_args["connect_args"] = {"check_same_thread": False}
    return engine_args


def build_engine(database_url: str | None = None) -> Engine:
    """Build and return a SQLAlchemy engine configured for the target environment."""
    settings = get_settings()
    url = database_url or settings.database_url

    # Ensure parent directory exists for file-based SQLite
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_path_str = url.replace("sqlite:///", "")
        if "?" in db_path_str:
            db_path_str = db_path_str.split("?")[0]
        db_path = Path(db_path_str).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine_args = get_engine_args(url)
    engine = create_engine(url, **engine_args)

    # SQLite performance optimizations: enable foreign keys & WAL mode
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                # In read-only or in-memory mode, pragma journal_mode may be ignored
                pass
            finally:
                cursor.close()

    return engine


# Default application engine and session factory
engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine | None = None) -> None:
    """Idempotently create all tables defined on Base."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    logger.info("database_tables_initialized", url=str(eng.url))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request with clean close."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
