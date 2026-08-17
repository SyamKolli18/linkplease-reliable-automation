"""Production database migration helper script for restart-safe, idempotent Alembic executions."""

import logging
import sys
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.migrate")


def is_schema_002_complete(inspector) -> bool:
    """Verify whether all elements of migration 002 are present in database."""
    if not (inspector.has_table("events") and inspector.has_table("dm_jobs")):
        return False

    # 1. Check events columns
    event_cols = {c["name"]: c for c in inspector.get_columns("events")}
    if "event_type" not in event_cols:
        return False

    # Check nullability of post_id, user_id, text
    for col_name in ["post_id", "user_id", "text"]:
        if col_name not in event_cols or not event_cols[col_name]["nullable"]:
            return False

    # 2. Check dm_jobs columns
    dm_job_cols = {c["name"]: c for c in inspector.get_columns("dm_jobs")}
    if "dm_id" not in dm_job_cols:
        return False

    # 3. Check dm_jobs indexes
    dm_job_indexes = {idx["name"] for idx in inspector.get_indexes("dm_jobs")}
    if "ix_dm_jobs_dm_id" not in dm_job_indexes:
        return False

    return True


def run_migrations(db_url: str = None, force_run: bool = False):
    """Run restart-safe production Alembic migrations."""
    if db_url is None:
        db_url = settings.DATABASE_URL

    if not force_run and (not db_url or db_url.startswith("sqlite")):
        logger.info("Local SQLite / test database detected. Skipping production Alembic auto-sync.")
        return

    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Connected to database. Found existing tables: {tables}")

        alembic_cfg = Config("alembic.ini")
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # Check if alembic_version table exists and has a valid revision recorded
        current_rev = None
        if "alembic_version" in tables:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                if result and result[0][0]:
                    current_rev = result[0][0]
                    logger.info(f"Found recorded Alembic revision: '{current_rev}'.")

        schema_complete = is_schema_002_complete(inspector)

        # Detect false stamp: alembic_version claims 002 but physical schema is missing 002 columns
        if current_rev == "002_add_dm_id_and_event_type" and not schema_complete:
            logger.warning(
                "alembic_version claims 002_add_dm_id_and_event_type but physical schema is incomplete! "
                "Re-stamping 001_initial_tables so migration 002 executes DDL..."
            )
            command.stamp(alembic_cfg, "001_initial_tables")
            current_rev = "001_initial_tables"

        # Evaluate initial stamping ONLY if alembic_version has no recorded revision
        if not current_rev:
            if "rules" in tables:
                if schema_complete:
                    logger.info("Existing database matches complete 002 schema. Stamping 002_add_dm_id_and_event_type...")
                    command.stamp(alembic_cfg, "002_add_dm_id_and_event_type")
                else:
                    logger.info("Existing database matches baseline 001 schema or partial 002. Stamping 001_initial_tables...")
                    command.stamp(alembic_cfg, "001_initial_tables")
            else:
                logger.info("Database is empty. No pre-stamping required.")

        # Always run upgrade head (idempotent, upgrades any pending migration safely)
        logger.info("Executing Alembic upgrade head...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migration completed successfully.")

    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    run_migrations()
