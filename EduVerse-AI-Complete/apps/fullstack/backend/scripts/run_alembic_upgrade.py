import os
import sys

backend_dir = "EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend"
sys.path.insert(0, backend_dir)

os.environ["QUICKLEARN_DATABASE_URL"] = "postgresql+psycopg://eduverse_app:EduVerse_App_2026_SecureKey!@127.0.0.1:5432/eduverse_db"

from quicklearn.db.bootstrap import run_migrations, get_engine
from sqlalchemy import text

print("Upgrading Alembic to head on PostgreSQL...")
run_migrations()
print("Alembic upgrade completed successfully!")

with get_engine().connect() as conn:
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"))
    tables = [r[0] for r in res.fetchall()]
    print(f"Total tables in eduverse_db now: {len(tables)}")
    for t in tables:
        print(f"  + {t}")
