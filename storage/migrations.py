"""Idempotent ALTER TABLE migrations for columns added after the initial
schema. Base.metadata.create_all() only creates missing tables, never adds
columns to existing ones — this covers that gap without touching the
existing 3+ MB production jobs.db.
"""
from sqlalchemy import text
from utils.logger import get_logger

logger = get_logger(__name__)

# table -> [(column_name, ddl_type_and_default), ...]
_COLUMN_MIGRATIONS = {
    "jobs": [("is_favorite", "BOOLEAN NOT NULL DEFAULT 0")],
    "search_runs": [
        ("mode", "VARCHAR(20) DEFAULT 'daily'"),
        ("trigger", "VARCHAR(20) DEFAULT 'cli'"),
        ("status", "VARCHAR(20) DEFAULT 'ok'"),
        ("log_path", "TEXT"),
    ],
}


def run_migrations(engine) -> None:
    with engine.connect() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for col_name, ddl in columns:
                if col_name in existing:
                    continue
                logger.info(f"Migrating: adding column {table}.{col_name}")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {ddl}"))
        conn.commit()
