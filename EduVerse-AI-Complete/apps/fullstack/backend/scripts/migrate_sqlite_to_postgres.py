"""
Data migration script: SQLite (quicklearn.db) -> PostgreSQL (eduverse_db).
Preserves all existing data, records, settings, and recalculates/syncs search docs and vector embeddings.
Resets PostgreSQL auto-increment sequences.
"""

import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import psycopg
from psycopg import sql
from psycopg.types.json import Json, Jsonb

SQLITE_PATH = backend_dir.parent / "data" / "quicklearn.db"
PG_RAW_URL = "postgresql://eduverse_app:EduVerse_App_2026_SecureKey!@127.0.0.1:5432/eduverse_db"
PG_SA_URL = "postgresql+psycopg://eduverse_app:EduVerse_App_2026_SecureKey!@127.0.0.1:5432/eduverse_db"

TABLES_IN_ORDER = [
    "users",
    "tags",
    "folders",
    "sources",
    "source_tags",
    "transcripts",
    "segments",
    "notes",
    "note_blocks",
    "concepts",
    "cards",
    "reviews",
    "chats",
    "messages",
    "quiz_sessions",
    "quiz_items",
    "quiz_attempts",
    "podcasts",
    "upload_sessions",
    "revision_sessions",
    "jobs",
    "llm_calls",
    "activity_logs",
    "revoked_tokens",
    "password_reset_tokens",
    "grading_failures",
    "settings",
]

def migrate():
    print(f"Reading SQLite database: {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    s_cur = sqlite_conn.cursor()

    print("Connecting to PostgreSQL database...")
    pg_conn = psycopg.connect(PG_RAW_URL, autocommit=False)
    p_cur = pg_conn.cursor()

    print("Clearing target tables before migration...")
    for tbl in reversed(TABLES_IN_ORDER):
        try:
            p_cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE;").format(sql.Identifier(tbl)))
        except Exception as e:
            pg_conn.rollback()
            print(f"Warning truncating {tbl}: {e}")
    pg_conn.commit()

    total_migrated = 0

    for tbl in TABLES_IN_ORDER:
        # Check if table exists in SQLite
        s_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
        if not s_cur.fetchone():
            continue

        s_cur.execute(f'SELECT * FROM "{tbl}"')
        rows = s_cur.fetchall()
        if not rows:
            print(f"  {tbl}: 0 rows")
            continue

        # Get target column data types from postgres
        p_cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name = %s",
            (tbl,)
        )
        col_types = {r[0]: r[1].lower() for r in p_cur.fetchall()}

        cols = [description[0] for description in s_cur.description]
        col_identifiers = [sql.Identifier(c) for c in cols]
        placeholders = sql.SQL(", ").join([sql.Placeholder() for _ in cols])
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(tbl),
            sql.SQL(", ").join(col_identifiers),
            placeholders,
        )

        batch_data = []
        for row in rows:
            row_dict = dict(row)
            values = []
            for col in cols:
                val = row_dict[col]
                target_type = col_types.get(col, "")

                if val is not None:
                    # Boolean conversion (SQLite 0/1 -> Python bool)
                    if target_type == "boolean":
                        val = bool(val)
                    # JSON conversion
                    elif "json" in target_type:
                        if isinstance(val, str):
                            try:
                                parsed = json.loads(val)
                                val = Json(parsed)
                            except Exception:
                                val = Json(val)
                        else:
                            val = Json(val)
                    # Timestamp conversion
                    elif "timestamp" in target_type and isinstance(val, str):
                        try:
                            # Handle ISO strings with Z or timezone offset
                            clean_val = val.replace("Z", "+00:00")
                            val = dt.datetime.fromisoformat(clean_val)
                        except Exception:
                            pass

                values.append(val)
            batch_data.append(values)

        p_cur.executemany(insert_query, batch_data)
        pg_conn.commit()
        print(f"  {tbl}: {len(rows)} rows migrated.")
        total_migrated += len(rows)

        # Reset serial sequence if table has 'id' column
        if "id" in cols:
            try:
                seq_sql = f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), coalesce(max(id), 1)) FROM {tbl};"
                p_cur.execute(seq_sql)
                pg_conn.commit()
            except Exception as e:
                pg_conn.rollback()

    # Migrate search_docs
    s_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_docs'")
    if s_cur.fetchone():
        s_cur.execute("SELECT kind, entity_id, source_id, title, body FROM search_docs")
        s_rows = s_cur.fetchall()
        if s_rows:
            p_cur.execute("TRUNCATE TABLE search_docs CASCADE;")
            p_cur.executemany(
                """
                INSERT INTO search_docs (kind, entity_id, source_id, title, body)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(kind, entity_id) DO UPDATE SET
                    source_id = EXCLUDED.source_id,
                    title = EXCLUDED.title,
                    body = EXCLUDED.body
                """,
                [tuple(r) for r in s_rows],
            )
            pg_conn.commit()
            print(f"  search_docs: {len(s_rows)} rows migrated and indexed with PostgreSQL tsvector.")

    sqlite_conn.close()
    pg_conn.close()

    print(f"\nMigration complete! Total rows migrated: {total_migrated}")

    # Now re-index vector embeddings into PostgreSQL segment_vectors_blob using the fastembed model
    print("\nEnsuring vector embeddings in PostgreSQL segment_vectors_blob...")
    os.environ["QUICKLEARN_DATABASE_URL"] = PG_SA_URL
    from quicklearn.db.session import session_scope
    from quicklearn.db.models import Segment
    from quicklearn.rag.index import get_index
    from fastembed import TextEmbedding

    idx = get_index()
    idx.ensure(384)

    with session_scope() as session:
        segments = session.query(Segment).all()
        seg_data = [(s.id, s.source_id, s.text) for s in segments if s.text]

    print(f"Found {len(seg_data)} segments to verify in vector index.")
    existing_count = idx.count()
    print(f"Current vector index count: {existing_count}")

    if existing_count < len(seg_data):
        print("Generating embeddings using FastEmbed (BAAI/bge-small-en-v1.5)...")
        embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        texts = [s[2] for s in seg_data]
        embeddings = list(embed_model.embed(texts))
        rows = [
            (seg_data[i][0], seg_data[i][1], [float(x) for x in embeddings[i]])
            for i in range(len(seg_data))
        ]
        idx.upsert(rows)
        print(f"Successfully stored {len(rows)} vector embeddings into PostgreSQL segment_vectors_blob!")
        print(f"Final vector count: {idx.count()}")
    else:
        print("Vector index is already fully populated.")

if __name__ == "__main__":
    migrate()
