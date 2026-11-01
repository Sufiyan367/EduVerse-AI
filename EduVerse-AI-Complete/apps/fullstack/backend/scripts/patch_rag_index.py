"""
Update NumpyIndex in backend/quicklearn/rag/index.py to seamlessly support PostgreSQL BYTEA and SQLite BLOB.
"""

from pathlib import Path

index_py = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/rag/index.py")
content = index_py.read_text(encoding="utf-8")

old_numpy_class = """class NumpyIndex:
    \"\"\"Fallback backend: vectors in a normal table, cosine computed in numpy.\"\"\"

    name = "numpy"

    def ensure(self, dimensions: int) -> None:
        with raw_sqlite() as conn:
            conn.execute(
                \"\"\"
                CREATE TABLE IF NOT EXISTS segment_vectors_blob (
                    segment_id INTEGER PRIMARY KEY,
                    source_id  INTEGER,
                    embedding  BLOB NOT NULL
                )
                \"\"\"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_segvec_source ON segment_vectors_blob(source_id)"
            )

    def upsert(self, rows: Sequence[tuple[int, int, Sequence[float]]]) -> None:
        if not rows:
            return
        with raw_sqlite() as conn:
            conn.executemany(
                \"\"\"
                INSERT INTO segment_vectors_blob(segment_id, source_id, embedding)
                VALUES (?, ?, ?)
                ON CONFLICT(segment_id) DO UPDATE SET
                    source_id = excluded.source_id, embedding = excluded.embedding
                \"\"\",
                [(sid, src, _serialise(vec)) for sid, src, vec in rows],
            )

    def search(
        self, vector: Sequence[float], *, k: int, source_ids: Sequence[int] | None = None
    ) -> list[VectorHit]:
        import numpy as np

        sql = "SELECT segment_id, embedding FROM segment_vectors_blob"
        params: list[object] = []
        if source_ids:
            sql += f" WHERE source_id IN ({','.join('?' * len(source_ids))})"
            params.extend(source_ids)

        with raw_sqlite() as conn:
            rows = conn.execute(sql, params).fetchall()
        if not rows:
            return []

        ids = np.array([r[0] for r in rows], dtype=np.int64)
        width = len(vector)
        matrix = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32)
        if matrix.size % width != 0:
            log.error("stored vectors do not match the expected width; reindex required")
            return []
        matrix = matrix.reshape(-1, width)

        query = np.asarray(vector, dtype=np.float32)
        # Normalise rather than assuming unit vectors — not every provider returns them.
        denominator = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
        denominator[denominator == 0] = 1.0
        scores = (matrix @ query) / denominator

        top = np.argsort(-scores)[:k]
        return [VectorHit(segment_id=int(ids[i]), score=float(scores[i])) for i in top]

    def delete_source(self, source_id: int) -> None:
        with raw_sqlite() as conn, contextlib.suppress(sqlite3.OperationalError):
            conn.execute("DELETE FROM segment_vectors_blob WHERE source_id = ?", (source_id,))

    def clear(self) -> None:
        with raw_sqlite() as conn:
            conn.execute("DROP TABLE IF EXISTS segment_vectors_blob")

    def count(self) -> int:
        with raw_sqlite() as conn:
            try:
                return int(conn.execute("SELECT count(*) FROM segment_vectors_blob").fetchone()[0])
            except Exception:
                return 0"""

new_numpy_class = """def _is_pg(conn: Any) -> bool:
    mod = getattr(conn, "__module__", "").lower()
    return "psycopg" in mod or "postgres" in mod or hasattr(conn, "pgconn")


class NumpyIndex:
    \"\"\"Vector backend: vectors in segment_vectors_blob (BYTEA on PostgreSQL, BLOB on SQLite), cosine computed in numpy.\"\"\"

    name = "numpy"

    def ensure(self, dimensions: int) -> None:
        with raw_sqlite() as conn:
            if _is_pg(conn):
                cur = conn.cursor()
                cur.execute(
                    \"\"\"
                    CREATE TABLE IF NOT EXISTS segment_vectors_blob (
                        segment_id INTEGER PRIMARY KEY,
                        source_id  INTEGER,
                        embedding  BYTEA NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS ix_segvec_source ON segment_vectors_blob(source_id);
                    \"\"\"
                )
                cur.close()
            else:
                conn.execute(
                    \"\"\"
                    CREATE TABLE IF NOT EXISTS segment_vectors_blob (
                        segment_id INTEGER PRIMARY KEY,
                        source_id  INTEGER,
                        embedding  BLOB NOT NULL
                    )
                    \"\"\"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_segvec_source ON segment_vectors_blob(source_id)"
                )

    def upsert(self, rows: Sequence[tuple[int, int, Sequence[float]]]) -> None:
        if not rows:
            return
        with raw_sqlite() as conn:
            if _is_pg(conn):
                cur = conn.cursor()
                cur.executemany(
                    \"\"\"
                    INSERT INTO segment_vectors_blob(segment_id, source_id, embedding)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(segment_id) DO UPDATE SET
                        source_id = EXCLUDED.source_id, embedding = EXCLUDED.embedding
                    \"\"\",
                    [(sid, src, bytes(_serialise(vec))) for sid, src, vec in rows],
                )
                cur.close()
            else:
                conn.executemany(
                    \"\"\"
                    INSERT INTO segment_vectors_blob(segment_id, source_id, embedding)
                    VALUES (?, ?, ?)
                    ON CONFLICT(segment_id) DO UPDATE SET
                        source_id = excluded.source_id, embedding = excluded.embedding
                    \"\"\",
                    [(sid, src, _serialise(vec)) for sid, src, vec in rows],
                )

    def search(
        self, vector: Sequence[float], *, k: int, source_ids: Sequence[int] | None = None
    ) -> list[VectorHit]:
        import numpy as np

        with raw_sqlite() as conn:
            if _is_pg(conn):
                sql = "SELECT segment_id, embedding FROM segment_vectors_blob"
                params: list[object] = []
                if source_ids:
                    sql += f" WHERE source_id IN ({','.join(['%s'] * len(source_ids))})"
                    params.extend(source_ids)
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
                cur.close()
            else:
                sql = "SELECT segment_id, embedding FROM segment_vectors_blob"
                params = []
                if source_ids:
                    sql += f" WHERE source_id IN ({','.join('?' * len(source_ids))})"
                    params.extend(source_ids)
                rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        ids = np.array([r[0] for r in rows], dtype=np.int64)
        width = len(vector)
        raw_blobs = []
        for r in rows:
            b = r[1]
            if hasattr(b, "tobytes"):
                raw_blobs.append(b.tobytes())
            elif isinstance(b, memoryview):
                raw_blobs.append(b.tobytes())
            elif isinstance(b, bytes):
                raw_blobs.append(b)
            else:
                raw_blobs.append(bytes(b))

        matrix = np.frombuffer(b"".join(raw_blobs), dtype=np.float32)
        if matrix.size % width != 0:
            log.error("stored vectors do not match the expected width; reindex required")
            return []
        matrix = matrix.reshape(-1, width)

        query = np.asarray(vector, dtype=np.float32)
        denominator = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
        denominator[denominator == 0] = 1.0
        scores = (matrix @ query) / denominator

        top = np.argsort(-scores)[:k]
        return [VectorHit(segment_id=int(ids[i]), score=float(scores[i])) for i in top]

    def delete_source(self, source_id: int) -> None:
        with raw_sqlite() as conn:
            if _is_pg(conn):
                cur = conn.cursor()
                cur.execute("DELETE FROM segment_vectors_blob WHERE source_id = %s", (source_id,))
                cur.close()
            else:
                with contextlib.suppress(sqlite3.OperationalError):
                    conn.execute("DELETE FROM segment_vectors_blob WHERE source_id = ?", (source_id,))

    def clear(self) -> None:
        with raw_sqlite() as conn:
            if _is_pg(conn):
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS segment_vectors_blob")
                cur.close()
            else:
                conn.execute("DROP TABLE IF EXISTS segment_vectors_blob")

    def count(self) -> int:
        with raw_sqlite() as conn:
            try:
                if _is_pg(conn):
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM segment_vectors_blob")
                    cnt = int(cur.fetchone()[0])
                    cur.close()
                    return cnt
                return int(conn.execute("SELECT count(*) FROM segment_vectors_blob").fetchone()[0])
            except Exception:
                return 0"""

# Also update get_index to prefer NumpyIndex on PostgreSQL
old_get_index = """def get_index() -> VectorIndex:
    global _index
    if _index is None:
        try:
            with get_engine().connect():
                pass
        except Exception:
            pass
        _index = Vec0Index() if vec_available() else NumpyIndex()
        log.info("vector index backend: %s", _index.name)
    return _index"""

new_get_index = """def get_index() -> VectorIndex:
    global _index
    if _index is None:
        from ..db.session import is_postgres
        if is_postgres():
            _index = NumpyIndex()
        else:
            _index = Vec0Index() if vec_available() else NumpyIndex()
        log.info("vector index backend: %s", _index.name)
    return _index"""

content = content.replace(old_numpy_class.replace("\r\n", "\n"), new_numpy_class)
content = content.replace(old_numpy_class, new_numpy_class)
content = content.replace(old_get_index.replace("\r\n", "\n"), new_get_index)
content = content.replace(old_get_index, new_get_index)

# Ensure Any is imported from typing
if "from typing import " in content:
    content = content.replace("from typing import Protocol", "from typing import Any, Protocol")

index_py.write_text(content, encoding="utf-8")
print("Patched rag/index.py successfully.")
