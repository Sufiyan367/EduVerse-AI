from pathlib import Path

bootstrap_py = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/db/bootstrap.py")
content = bootstrap_py.read_text(encoding="utf-8")

old_init = """def init_database(config: Config | None = None) -> None:
    \"\"\"Idempotent full initialisation. Safe to call on every boot.\"\"\"
    cfg = config or get_config()
    cfg.ensure_dirs()
    init_engine(cfg)
    run_migrations()
    create_virtual_tables()

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

    log.info("database ready at %s", cfg.db_path)"""

new_init = """def init_database(config: Config | None = None) -> None:
    \"\"\"Idempotent full initialisation. Safe to call on every boot.\"\"\"
    cfg = config or get_config()
    cfg.ensure_dirs()
    init_engine(cfg)
    run_migrations()
    create_virtual_tables()

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

    log.info("database ready at %s", cfg.db_url)"""

content = content.replace(old_init.replace("\r\n", "\n"), new_init)
content = content.replace(old_init, new_init)
bootstrap_py.write_text(content, encoding="utf-8")
print("Patched db/bootstrap.py successfully.")
