import sqlite3
from pathlib import Path

db_file = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/data/quicklearn.db")
if not db_file.exists():
    print(f"File not found: {db_file}")
    exit(1)

conn = sqlite3.connect(db_file)
cursor = conn.cursor()
tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Tables in SQLite ({len(tables)}):")
for t in sorted(tables):
    try:
        cnt = cursor.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
        print(f"  {t}: {cnt}")
    except Exception as e:
        print(f"  {t}: {e}")
conn.close()
