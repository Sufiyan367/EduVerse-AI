"""
Patch database portability across:
- backend/quicklearn/db/session.py
- backend/quicklearn/db/migrations/env.py
- backend/quicklearn/db/search.py
- backend/quicklearn/rag/index.py
- backend/quicklearn/db/bootstrap.py
"""

from pathlib import Path

base_dir = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend/quicklearn")

# 1. Patch session.py
session_py = base_dir / "db" / "session.py"
session_content = session_py.read_text(encoding="utf-8")

if "def is_postgres" not in session_content:
    old_engine = """def create_db_engine(config: Config | None = None, *, echo: bool = False) -> Engine:
    cfg = config or get_config()
    engine = create_engine(
        cfg.db_url,
        echo=echo,
        future=True,
        # Connections cross threads because DB work runs in the threadpool.
        connect_args={"check_same_thread": False, "timeout": 15.0},
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _configure_connection)
    return engine"""

    new_engine = """def is_postgres(engine: Engine | None = None) -> bool:
    eng = engine or get_engine()
    return eng.dialect.name in ("postgresql", "postgres")


def create_db_engine(config: Config | None = None, *, echo: bool = False) -> Engine:
    cfg = config or get_config()
    db_url = cfg.db_url
    if db_url.startswith("postgresql") or db_url.startswith("postgres"):
        engine = create_engine(
            db_url,
            echo=echo,
            future=True,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    else:
        engine = create_engine(
            db_url,
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False, "timeout": 15.0},
            pool_pre_ping=True,
        )
        event.listen(engine, "connect", _configure_connection)
    return engine"""

    session_content = session_content.replace(old_engine.replace("\r\n", "\n"), new_engine)
    session_content = session_content.replace(old_engine, new_engine)

    # Add raw_connection alias if not present
    if "raw_connection = raw_sqlite" not in session_content:
        session_content += "\nraw_connection = raw_sqlite\n"

    session_py.write_text(session_content, encoding="utf-8")
    print("Patched db/session.py successfully.")
else:
    print("db/session.py already patched.")

# 2. Patch env.py
env_py = base_dir / "db" / "migrations" / "env.py"
env_content = env_py.read_text(encoding="utf-8")

old_run = """def _run(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things in place; batch mode recreates-and-copies instead.
        render_as_batch=True,
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()"""

new_run = """def _run(connection: object) -> None:
    is_sqlite = False
    if hasattr(connection, "dialect"):
        is_sqlite = (connection.dialect.name == "sqlite")
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things in place; batch mode recreates-and-copies instead.
        render_as_batch=is_sqlite,
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()"""

old_offline = """def run_migrations_offline() -> None:
    context.configure(
        url=get_config().db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()"""

new_offline = """def run_migrations_offline() -> None:
    url = get_config().db_url
    is_sqlite = "sqlite" in str(url).lower()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()"""

env_content = env_content.replace(old_run.replace("\r\n", "\n"), new_run)
env_content = env_content.replace(old_run, new_run)
env_content = env_content.replace(old_offline.replace("\r\n", "\n"), new_offline)
env_content = env_content.replace(old_offline, new_offline)
env_py.write_text(env_content, encoding="utf-8")
print("Patched db/migrations/env.py successfully.")
