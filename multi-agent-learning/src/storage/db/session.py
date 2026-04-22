from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_engine_from_url(database_url: str):
    cleaned = database_url.strip()
    if not cleaned:
        raise ValueError("database_url cannot be empty.")

    return create_engine(cleaned, pool_pre_ping=True, future=True)


def create_session_factory(database_url: str):
    engine = create_engine_from_url(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
