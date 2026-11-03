"""First-boot and every-boot database initialisation.

PRD §3.5: "The DB must self-initialize on first run with no user action." So migrations run
automatically at startup rather than being a documented step someone has to remember.

Responsibility is split deliberately:

* **Alembic** owns the declarative tables in :mod:`quicklearn.db.models`.
* **This module** owns the virtual tables and triggers — FTS5 and sqlite-vec — because Alembic
  autogenerate cannot see them and would otherwise propose dropping them on every revision.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from ..config import Config, get_config
from . import search
from .session import get_engine, init_engine, raw_sqlite

log = logging.getLogger(__name__)


def _alembic_config() -> AlembicConfig:
    root = Path(__file__).resolve().parent.parent.parent
    ini = root / "alembic.ini"
    cfg = AlembicConfig(str(ini)) if ini.exists() else AlembicConfig()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    return cfg


def run_migrations() -> None:
    """Bring the schema to head, sharing the application engine's connection."""
    engine = get_engine()
    cfg = _alembic_config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def create_virtual_tables() -> None:
    with raw_sqlite() as conn:
        search.create_schema(conn)


def init_database(config: Config | None = None) -> None:
    """Idempotent full initialisation. Safe to call on every boot."""
    cfg = config or get_config()
    cfg.ensure_dirs()
    init_engine(cfg)
    run_migrations()
    create_virtual_tables()

    try:
        from sqlalchemy import text
        from .session import session_scope
        with session_scope() as session:
            session.execute(text("ALTER TABLE student_topic_mastery ADD COLUMN status VARCHAR(32) DEFAULT 'not_started'"))
            session.commit()
    except Exception:
        pass

    try:
        from sqlalchemy import text
        from .session import session_scope
        with session_scope() as session:
            res = session.execute(text("PRAGMA table_info(student_topic_mastery)")).fetchall()
            col_map = {row[1]: row for row in res}
            if col_map.get("last_evaluated_at") and col_map["last_evaluated_at"][3] == 1:
                session.execute(text("""
                    CREATE TABLE student_topic_mastery_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        topic_id INTEGER NOT NULL REFERENCES syllabus_topics(id) ON DELETE CASCADE,
                        mastery_score FLOAT DEFAULT 0.0,
                        confidence_level VARCHAR(32) DEFAULT 'low',
                        status VARCHAR(32) DEFAULT 'not_started',
                        last_evaluated_at DATETIME,
                        CONSTRAINT uq_user_topic_mastery UNIQUE (user_id, topic_id)
                    )
                """))
                session.execute(text("""
                    INSERT INTO student_topic_mastery_new (id, user_id, topic_id, mastery_score, confidence_level, status, last_evaluated_at)
                    SELECT id, user_id, topic_id, mastery_score, confidence_level, status, last_evaluated_at FROM student_topic_mastery
                """))
                session.execute(text("DROP TABLE student_topic_mastery"))
                session.execute(text("ALTER TABLE student_topic_mastery_new RENAME TO student_topic_mastery"))
                session.commit()
    except Exception as exc:
        log.warning("Could not migrate student_topic_mastery nullability: %s", exc)

    try:
        from ..rag.index import get_index
        get_index().ensure(384)
    except Exception as exc:
        log.warning("Could not ensure vector index table: %s", exc)

    # Seed default EduVerse demo student if enabled
    if cfg.seed_demo:
        try:
            from ..auth import seed_default_demo_user
            from .session import session_scope

            with session_scope() as session:
                seed_default_demo_user(session)
        except Exception as exc:
            log.warning("Could not seed default demo user: %s", exc)
    else:
        log.info("Demo account seeding suppressed (production or EDUVERSE_SEED_DEMO=false).")

    log.info("database ready at %s", cfg.db_url)
