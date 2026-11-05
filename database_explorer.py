"""
EduVerse AI - Database Explorer & Python Data Exporter
=====================================================
This script allows you to:
1. View all database tables & data directly in your Code Editor in Python format (database_data.py).
2. View Markdown tables in your Code Editor (DATABASE_VIEW.md).
3. Inspect and query tables interactively from the terminal.

Usage:
    python database_explorer.py             # View summary of all tables & row counts
    python database_explorer.py <table_name> # Inspect all records of a specific table
    python database_explorer.py --export    # Refresh database_data.py & DATABASE_VIEW.md
"""

import os
import sys
import json
import sqlite3
import datetime
from pathlib import Path

# Paths to databases
BASE_DIR = Path(__file__).resolve().parent
DB_PATHS = {
    "quicklearn": [
        BASE_DIR / "EduVerse-AI-Complete" / "apps" / "fullstack" / "data" / "quicklearn.db",
        Path(r"S:\SY\SEM 3\MP\EduVerse-AI-Complete\apps\fullstack\data\quicklearn.db"),
        Path(os.path.expanduser("~")) / "quicklearn" / "quicklearn.db",
    ],
    "eduverse": [
        BASE_DIR / "data" / "eduverse.db",
        BASE_DIR / "EduVerse-AI-Complete" / "apps" / "baseline" / "data" / "eduverse.db",
        Path(r"S:\SY\SEM 3\MP\EduVerse-AI-main\EduVerse-AI-main\data\eduverse.db"),
    ]
}

def get_db_connection(name: str):
    paths = DB_PATHS.get(name, [])
    for p in paths:
        if p.exists():
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            return conn, p
    return None, None

def export_to_python(quicklearn_conn, eduverse_conn, output_path: Path):
    """Exports entire database as human-readable Python code (dicts & lists)."""
    lines = [
        '"""',
        '========================================================================',
        'EduVerse AI - Live Database Records (Python Format)',
        f'Generated At: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        'This file lets you view and inspect all database tables directly in Python.',
        'To refresh this data anytime, run: python database_explorer.py --export',
        '========================================================================',
        '"""',
        '',
        'from typing import Any, Dict, List',
        '',
    ]

    # Tables to export from QuickLearn DB
    ql_tables = [
        "users", "sources", "notes", "note_blocks", "concepts", 
        "cards", "quiz_items", "quiz_sessions", "quiz_attempts", 
        "chats", "messages", "activity_logs", "revision_sessions", 
        "settings", "jobs", "podcasts"
    ]

    lines.append('# ========================================================================')
    lines.append('# 1. FULL-STACK PLATFORM DATABASE (quicklearn.db)')
    lines.append('# ========================================================================')
    lines.append('')

    if quicklearn_conn:
        for table in ql_tables:
            try:
                cursor = quicklearn_conn.cursor()
                rows = cursor.execute(f"SELECT * FROM {table}").fetchall()
                data = []
                for r in rows:
                    d = dict(r)
                    # Convert json strings if any
                    for k, v in d.items():
                        if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
                            try:
                                d[k] = json.loads(v)
                            except Exception:
                                pass
                    data.append(d)
                
                var_name = f"QL_{table.upper()}"
                lines.append(f'# --- Table: {table} ({len(data)} rows) ---')
                lines.append(f'{var_name}: List[Dict[str, Any]] = {json.dumps(data, indent=4, default=str)}')
                lines.append('')
            except Exception as e:
                lines.append(f'# Could not load table {table}: {e}')
                lines.append('')

    # Tables to export from Baseline EduVerse DB
    edu_tables = ["documents", "quizzes", "quiz_evaluations", "document_concepts"]

    lines.append('# ========================================================================')
    lines.append('# 2. 3D VIRTUAL TUTOR BASELINE DATABASE (eduverse.db)')
    lines.append('# ========================================================================')
    lines.append('')

    if eduverse_conn:
        for table in edu_tables:
            try:
                cursor = eduverse_conn.cursor()
                rows = cursor.execute(f"SELECT * FROM {table}").fetchall()
                data = []
                for r in rows:
                    d = dict(r)
                    for k, v in d.items():
                        if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
                            try:
                                d[k] = json.loads(v)
                            except Exception:
                                pass
                    data.append(d)
                
                var_name = f"EDU_{table.upper()}"
                lines.append(f'# --- Table: {table} ({len(data)} rows) ---')
                lines.append(f'{var_name}: List[Dict[str, Any]] = {json.dumps(data, indent=4, default=str)}')
                lines.append('')
            except Exception as e:
                lines.append(f'# Could not load table {table}: {e}')
                lines.append('')

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Exported Python Database View: {output_path}")

def export_to_markdown(quicklearn_conn, eduverse_conn, output_path: Path):
    """Exports database as a clean, styled Markdown document viewable in Code Editor."""
    md = [
        "# 🗄️ EduVerse AI - Database Inspector",
        f"> *Last Synced: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "This file displays all your database tables and live data inside your code editor.",
        "To update this file, run: `python database_explorer.py --export`",
        "",
        "---",
        "## 1. QuickLearn Full-Stack Database (`quicklearn.db`)",
        "",
    ]

    ql_tables = [
        "users", "sources", "notes", "concepts", "cards", 
        "quiz_sessions", "quiz_attempts", "chats", "activity_logs", 
        "revision_sessions", "settings"
    ]

    if quicklearn_conn:
        for table in ql_tables:
            try:
                cursor = quicklearn_conn.cursor()
                rows = cursor.execute(f"SELECT * FROM {table} LIMIT 10").fetchall()
                md.append(f"### 📋 Table: `{table}` ({len(rows)} records shown)")
                if not rows:
                    md.append("*No records found in this table.*")
                    md.append("")
                    continue
                
                cols = rows[0].keys()
                # Pick up to 6 key columns to keep markdown readable
                display_cols = cols[:7]
                header = "| " + " | ".join(display_cols) + " |"
                sep = "| " + " | ".join(["---"] * len(display_cols)) + " |"
                md.append(header)
                md.append(sep)
                for r in rows:
                    vals = []
                    for c in display_cols:
                        v = str(r[c]) if r[c] is not None else "*null*"
                        v = v.replace("\n", " ").replace("|", "\\|")
                        if len(v) > 50:
                            v = v[:47] + "..."
                        vals.append(v)
                    md.append("| " + " | ".join(vals) + " |")
                md.append("")
            except Exception as e:
                md.append(f"*Could not query `{table}`: {e}*")
                md.append("")

    md.append("---")
    md.append("## 2. EduVerse Baseline Database (`eduverse.db`)")
    md.append("")

    if eduverse_conn:
        for table in ["documents", "quizzes", "quiz_evaluations", "document_concepts"]:
            try:
                cursor = eduverse_conn.cursor()
                rows = cursor.execute(f"SELECT * FROM {table} LIMIT 10").fetchall()
                md.append(f"### 📋 Table: `{table}` ({len(rows)} records shown)")
                if not rows:
                    md.append("*No records found in this table.*")
                    md.append("")
                    continue
                cols = rows[0].keys()
                display_cols = cols[:6]
                header = "| " + " | ".join(display_cols) + " |"
                sep = "| " + " | ".join(["---"] * len(display_cols)) + " |"
                md.append(header)
                md.append(sep)
                for r in rows:
                    vals = []
                    for c in display_cols:
                        v = str(r[c]) if r[c] is not None else "*null*"
                        v = v.replace("\n", " ").replace("|", "\\|")
                        if len(v) > 50:
                            v = v[:47] + "..."
                        vals.append(v)
                    md.append("| " + " | ".join(vals) + " |")
                md.append("")
            except Exception as e:
                md.append(f"*Could not query `{table}`: {e}*")
                md.append("")

    output_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] Exported Markdown Database View: {output_path}")

def print_summary(quicklearn_conn, eduverse_conn):
    print("=" * 70)
    print("           EduVerse AI - Database Tables Summary")
    print("=" * 70)
    
    if quicklearn_conn:
        print("\n[DATABASE 1: QuickLearn Full-Stack DB]")
        cursor = quicklearn_conn.cursor()
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'segment_vectors%' AND name NOT LIKE 'search_%'").fetchall()]
        print(f"{'Table Name':<28} | {'Rows':<8} | {'Status'}")
        print("-" * 55)
        for t in sorted(tables):
            try:
                cnt = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                status = "Has Data" if cnt > 0 else "Empty"
                print(f"{t:<28} | {cnt:<8} | {status}")
            except Exception:
                pass

    if eduverse_conn:
        print("\n[DATABASE 2: Baseline 3D Virtual Tutor DB]")
        cursor = eduverse_conn.cursor()
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"{'Table Name':<28} | {'Rows':<8} | {'Status'}")
        print("-" * 55)
        for t in sorted(tables):
            try:
                cnt = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                status = "Has Data" if cnt > 0 else "Empty"
                print(f"{t:<28} | {cnt:<8} | {status}")
            except Exception:
                pass
    print("=" * 70)
    print("To view data in Code Editor, open: 'database_data.py' or 'DATABASE_VIEW.md'")
    print("=" * 70)

def main():
    ql_conn, ql_path = get_db_connection("quicklearn")
    edu_conn, edu_path = get_db_connection("eduverse")

    if "--export" in sys.argv or "-e" in sys.argv or len(sys.argv) == 1:
        # Default export so files are always ready to open in editor
        export_to_python(ql_conn, edu_conn, BASE_DIR / "database_data.py")
        export_to_markdown(ql_conn, edu_conn, BASE_DIR / "DATABASE_VIEW.md")

    if len(sys.argv) > 1 and sys.argv[1] not in ["--export", "-e"]:
        table_name = sys.argv[1].lower()
        # Query specific table
        found = False
        for name, conn in [("quicklearn", ql_conn), ("eduverse", edu_conn)]:
            if conn:
                try:
                    rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 25").fetchall()
                    if rows:
                        found = True
                        print(f"\n--- Records in '{table_name}' ({name} database) ---")
                        for idx, r in enumerate(rows, 1):
                            print(f"\n[Row {idx}]")
                            for k in r.keys():
                                val = str(r[k])
                                if len(val) > 120:
                                    val = val[:117] + "..."
                                print(f"  {k:<22}: {val}")
                        break
                except Exception:
                    pass
        if not found:
            print(f"[!] Table '{table_name}' not found or has no records.")
    else:
        print_summary(ql_conn, edu_conn)

if __name__ == "__main__":
    main()
