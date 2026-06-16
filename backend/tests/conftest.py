"""
Shared fixtures for all test levels.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from aios.main import app
from aios.api.deps import get_db


# ── Fake DB session ────────────────────────────────────────────────────────────

def make_mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_session():
    return make_mock_session()


@pytest.fixture
def app_with_mock_db(mock_session):
    """FastAPI app with DB dependency replaced by a mock session."""
    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    yield app, mock_session
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(app_with_mock_db):
    app_instance, session = app_with_mock_db
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        yield client, session


# ── Common fake objects ────────────────────────────────────────────────────────

def fake_job(**kwargs):
    now = datetime.now(timezone.utc)
    return MagicMock(
        id=kwargs.get("id", uuid.uuid4()),
        title=kwargs.get("title", "Test Job"),
        description=kwargs.get("description", "desc"),
        status=kwargs.get("status", "PENDING"),
        priority=kwargs.get("priority", "NORMAL"),
        input_payload=kwargs.get("input_payload", {}),
        output_payload=None,
        retry_policy={"max_attempts": 3, "backoff": "exponential", "backoff_seconds": 5},
        total_tokens=0,
        estimated_cost=0.0,
        created_at=now,
        started_at=None,
        completed_at=None,
    )


def fake_tool(**kwargs):
    return MagicMock(
        name=kwargs.get("name", "test_tool"),
        description=kwargs.get("description", "A test tool"),
        input_schema=kwargs.get("input_schema", {}),
        output_schema=kwargs.get("output_schema", {}),
        rate_limit_per_minute=None,
        requires_external_api=True,
        webhook_url=kwargs.get("webhook_url", None),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
