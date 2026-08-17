"""Unit tests for production database migration helper app.migrate."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from app.migrate import is_schema_002_complete, run_migrations


def test_is_schema_002_complete_empty_db(tmp_path):
    db_file = tmp_path / "test_empty.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is False


def test_scenario_a_fresh_database(tmp_path):
    """Scenario A: Fresh database -> runs upgrade head directly."""
    db_file = tmp_path / "test_scenario_a.db"
    db_url = f"sqlite:///{db_file}"
    
    run_migrations(db_url=db_url, force_run=True)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert inspector.has_table("rules")
    assert inspector.has_table("events")
    assert inspector.has_table("dm_jobs")
    assert is_schema_002_complete(inspector) is True


def test_scenario_b_existing_001_schema_no_alembic_ver(tmp_path):
    """Scenario B: Existing 001 schema with no alembic_version -> stamps 001 and upgrades to 002."""
    db_file = tmp_path / "test_scenario_b.db"
    db_url = f"sqlite:///{db_file}"
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "001_initial_tables")

    # Drop alembic_version table to simulate unversioned 001 DB
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.commit()

    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is False

    # Run migration helper
    run_migrations(db_url=db_url, force_run=True)

    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is True


def test_scenario_c_existing_partial_002_schema_no_alembic_ver(tmp_path):
    """Scenario C: Existing partial 002 schema with no alembic_version -> stamps 001 and upgrades safely."""
    db_file = tmp_path / "test_scenario_c.db"
    db_url = f"sqlite:///{db_file}"
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "001_initial_tables")

    # Manually add event_type column only (partial 002) and drop alembic_version
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE events ADD COLUMN event_type VARCHAR(50) DEFAULT 'comment.created'"))
        conn.execute(text("DROP TABLE alembic_version"))
        conn.commit()

    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is False

    # Run migration helper
    run_migrations(db_url=db_url, force_run=True)

    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is True


def test_scenario_d_existing_complete_002_schema_no_alembic_ver(tmp_path):
    """Scenario D: Existing complete 002 schema with no alembic_version -> stamps 002 directly."""
    db_file = tmp_path / "test_scenario_d.db"
    db_url = f"sqlite:///{db_file}"
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    # Drop alembic_version table to simulate complete 002 DB missing alembic_version
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.commit()

    inspector = inspect(engine)
    assert is_schema_002_complete(inspector) is True

    # Run migration helper
    run_migrations(db_url=db_url, force_run=True)

    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver == "002_add_dm_id_and_event_type"


def test_scenario_e_existing_db_with_alembic_ver_001(tmp_path):
    """Scenario E: Database with alembic_version=001 -> upgrades head without re-stamping."""
    db_file = tmp_path / "test_scenario_e.db"
    db_url = f"sqlite:///{db_file}"
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "001_initial_tables")

    run_migrations(db_url=db_url, force_run=True)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver == "002_add_dm_id_and_event_type"


def test_scenario_f_and_g_existing_db_at_002_restart(tmp_path):
    """Scenario F & G: Database already at 002 -> restart is idempotent and safe."""
    db_file = tmp_path / "test_scenario_fg.db"
    db_url = f"sqlite:///{db_file}"
    
    run_migrations(db_url=db_url, force_run=True)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        ver1 = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver1 == "002_add_dm_id_and_event_type"

    # Simulate container restart
    run_migrations(db_url=db_url, force_run=True)

    with engine.connect() as conn:
        ver2 = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver2 == "002_add_dm_id_and_event_type"
