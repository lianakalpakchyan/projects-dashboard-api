from collections.abc import Generator
from typing import Any

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session]:
    """Yields a SQLAlchemy Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_raw_db_conn() -> Generator[Any]:
    """Yields a raw psycopg2 database connection."""
    conn = psycopg2.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
    )
    try:
        yield conn
    finally:
        conn.close()
