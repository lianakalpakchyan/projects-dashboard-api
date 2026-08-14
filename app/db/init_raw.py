import logging

import psycopg2

from app.core import settings

logger = logging.getLogger(__name__)


def init_raw_tables() -> None:
    """Runs raw SQL DDL file statements against PostgreSQL direct connection."""
    logger.info("Initializing raw SQL relational schema schema.sql...")
    try:
        conn = psycopg2.connect(
            dbname=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
        )
        with conn:
            with conn.cursor() as cur:
                with open("schema.sql", encoding="utf-8") as f:
                    cur.execute(f.read())
        logger.info("Raw database DDL structures created successfully!")
    except Exception as exc:
        logger.error(f"Failed direct driver DDL execution: {exc}")
        raise exc
