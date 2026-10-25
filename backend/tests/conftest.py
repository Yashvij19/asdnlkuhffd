"""
Shared pytest fixtures for unit and integration tests.
"""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.db import build_engine, init_db


@pytest.fixture
def memory_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite database session for testing."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    yield session
    session.close()
