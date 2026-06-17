"""Synchronous SQLAlchemy session for use inside Celery workers."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from osymandias.runtime.config import settings

# Convert asyncpg URL to psycopg2-compatible URL for sync engine
_sync_url = settings.postgres_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

_engine = create_engine(_sync_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

SyncSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=True)


def get_sync_session() -> Session:
    return SyncSessionLocal()
