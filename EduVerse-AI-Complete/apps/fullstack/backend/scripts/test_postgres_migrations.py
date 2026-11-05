import os
import sys

# Ensure backend root is on sys.path
backend_path = "EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend"
sys.path.insert(0, backend_path)

os.environ["QUICKLEARN_DATABASE_URL"] = "postgresql+psycopg://eduverse_app:EduVerse_App_2026_SecureKey!@127.0.0.1:5432/eduverse_db"

print("Testing init_database on PostgreSQL...")
from quicklearn.db.bootstrap import init_database
from quicklearn.db.session import get_engine, raw_sqlite

init_database()
print("init_database succeeded!")

with get_engine().connect() as conn:
    from sqlalchemy import text
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"))
    tables = [r[0] for r in result.fetchall()]
    print(f"Tables in eduverse_db ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
