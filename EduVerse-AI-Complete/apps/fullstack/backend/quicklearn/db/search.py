"""Full-text search index supporting both PostgreSQL (native tsvector + GIN) and SQLite (FTS5).

One index covers everything searchable — note text, transcript segments, card faces, concept
definitions and source titles — so ``Cmd+K`` is a single query rather than a union of five.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

log = logging.getLogger(__name__)

SearchKind = Literal["note", "segment", "card", "concept", "source"]

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_docs (
    id         INTEGER PRIMARY KEY,
    kind       TEXT    NOT NULL,
    entity_id  INTEGER NOT NULL,
    source_id  INTEGER,
    title      TEXT    NOT NULL DEFAULT '',
    body       TEXT    NOT NULL DEFAULT '',
    UNIQUE(kind, entity_id)
);

CREATE INDEX IF NOT EXISTS ix_search_docs_source ON search_docs(source_id);

CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    title,
    body,
    content='search_docs',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS search_docs_ai AFTER INSERT ON search_docs BEGIN
    INSERT INTO search_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS search_docs_ad AFTER DELETE ON search_docs BEGIN
    INSERT INTO search_fts(search_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS search_docs_au AFTER UPDATE ON search_docs BEGIN
    INSERT INTO search_fts(search_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO search_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
"""

_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_docs (
    id         SERIAL PRIMARY KEY,
    kind       VARCHAR(32)  NOT NULL,
    entity_id  INTEGER      NOT NULL,
    source_id  INTEGER,
    title      TEXT         NOT NULL DEFAULT '',
    body       TEXT         NOT NULL DEFAULT '',
    tsv        tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(body, '')), 'B')
    ) STORED,
    UNIQUE(kind, entity_id)
);

CREATE INDEX IF NOT EXISTS ix_search_docs_source ON search_docs(source_id);
CREATE INDEX IF NOT EXISTS ix_search_docs_tsv ON search_docs USING GIN(tsv);
"""


def _is_pg(conn: Any) -> bool:
    mod = getattr(conn, "__module__", "").lower()
    return "psycopg" in mod or "postgres" in mod or hasattr(conn, "pgconn")


def create_schema(conn: Any) -> None:
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(_POSTGRES_SCHEMA)
        cur.close()
    else:
        conn.executescript(_SQLITE_SCHEMA)


@dataclass(slots=True)
class SearchHit:
    kind: SearchKind
    entity_id: int
    source_id: int | None
    title: str
    snippet: str
    #: FTS5 BM25 or inverted ts_rank. Negative, and more negative means a better match.
    score: float


def upsert(
    conn: Any,
    kind: SearchKind,
    entity_id: int,
    *,
    title: str = "",
    body: str = "",
    source_id: int | None = None,
) -> None:
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO search_docs (kind, entity_id, source_id, title, body)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(kind, entity_id) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                title     = EXCLUDED.title,
                body      = EXCLUDED.body
            """,
            (kind, entity_id, source_id, title, body),
        )
        cur.close()
    else:
        conn.execute(
            """
            INSERT INTO search_docs (kind, entity_id, source_id, title, body)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, entity_id) DO UPDATE SET
                source_id = excluded.source_id,
                title     = excluded.title,
                body      = excluded.body
            """,
            (kind, entity_id, source_id, title, body),
        )


def upsert_many(
    conn: Any,
    kind: SearchKind,
    rows: Iterable[tuple[int, str, str, int | None]],
) -> None:
    """Bulk variant. ``rows`` is ``(entity_id, title, body, source_id)``."""
    data = [(kind, eid, title, body, sid) for eid, title, body, sid in rows]
    if not data:
        return

    if _is_pg(conn):
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO search_docs (kind, entity_id, title, body, source_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(kind, entity_id) DO UPDATE SET
                title = EXCLUDED.title, body = EXCLUDED.body, source_id = EXCLUDED.source_id
            """,
            data,
        )
        cur.close()
    else:
        conn.executemany(
            """
            INSERT INTO search_docs (kind, entity_id, title, body, source_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, entity_id) DO UPDATE SET
                title = excluded.title, body = excluded.body, source_id = excluded.source_id
            """,
            data,
        )


def delete(conn: Any, kind: SearchKind, entity_id: int) -> None:
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM search_docs WHERE kind = %s AND entity_id = %s", (kind, entity_id))
        cur.close()
    else:
        conn.execute("DELETE FROM search_docs WHERE kind = ? AND entity_id = ?", (kind, entity_id))


def delete_kind_for_source(conn: Any, kind: SearchKind, source_id: int) -> None:
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM search_docs WHERE kind = %s AND source_id = %s", (kind, source_id))
        cur.close()
    else:
        conn.execute("DELETE FROM search_docs WHERE kind = ? AND source_id = ?", (kind, source_id))


def delete_source(conn: Any, source_id: int) -> None:
    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM search_docs WHERE source_id = %s", (source_id,))
        cur.close()
    else:
        conn.execute("DELETE FROM search_docs WHERE source_id = ?", (source_id,))


_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "should", "shouldn't", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "won't", "would", "wouldn't", "you", "your",
    "yours", "yourself", "yourselves"
}


def escape_query(raw: str) -> str:
    """Turn user input into a safe FTS5 MATCH expression for SQLite."""
    tokens = []
    current: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in {"_", "'"}:
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))

    if not tokens:
        return ""

    meaningful = [t for t in tokens if t.lower() not in _STOPWORDS]
    target_tokens = meaningful if meaningful else tokens

    quoted = [f'"{t}"' for t in target_tokens[:-1]]
    last = target_tokens[-1]
    quoted.append(f'"{last}"*' if len(last) >= 3 and last.isalpha() else f'"{last}"')
    return " OR ".join(quoted)


def search(
    conn: Any,
    query: str,
    *,
    kinds: Sequence[SearchKind] | None = None,
    source_ids: Sequence[int] | None = None,
    limit: int = 50,
) -> list[SearchHit]:
    from ..security import principal
    user_filter_id = principal.get()

    if _is_pg(conn):
        clean_words = [w for w in query.split() if w.isalnum()]
        if not clean_words:
            return []
        clean_q = " ".join(clean_words)

        sql = [
            """
            SELECT d.kind, d.entity_id, d.source_id, d.title,
                   ts_headline('english', coalesce(d.body, ''), plainto_tsquery('english', %s), 'StartSel=<mark>, StopSel=</mark>, MaxWords=24, MinWords=10') AS snip,
                   ts_rank(d.tsv, plainto_tsquery('english', %s)) AS score
            FROM search_docs d
            WHERE d.tsv @@ plainto_tsquery('english', %s)
            """
        ]
        params: list[object] = [clean_q, clean_q, clean_q]

        if user_filter_id is not None:
            sql.append("AND (d.source_id IS NULL OR d.source_id IN (SELECT id FROM sources WHERE user_id = %s))")
            params.append(user_filter_id)

        if kinds:
            sql.append(f"AND d.kind IN ({','.join(['%s'] * len(kinds))})")
            params.extend(kinds)
        if source_ids:
            sql.append(f"AND d.source_id IN ({','.join(['%s'] * len(source_ids))})")
            params.extend(source_ids)

        sql.append("ORDER BY score DESC LIMIT %s")
        params.append(limit)

        cur = conn.cursor()
        try:
            cur.execute(" ".join(sql), params)
            rows = cur.fetchall()
        except Exception as exc:
            log.warning("Postgres search error: %s", exc)
            rows = []
        finally:
            cur.close()

        return [
            SearchHit(
                kind=row[0],
                entity_id=row[1],
                source_id=row[2],
                title=row[3] or "",
                snippet=row[4] or "",
                # Flip sign so that sorting ascending by score matches BM25 (more negative = better match)
                score=-float(row[5] or 0.0),
            )
            for row in rows
        ]

    # SQLite FTS5 fallback path
    match_expr = escape_query(query)
    if not match_expr:
        return []

    sql = [
        """
        SELECT d.kind, d.entity_id, d.source_id, d.title,
               snippet(search_fts, 1, '<mark>', '</mark>', '…', 24) AS snip,
               bm25(search_fts, 4.0, 1.0) AS score
        FROM search_fts
        JOIN search_docs d ON d.id = search_fts.rowid
        WHERE search_fts MATCH ?
        """
    ]
    sqlite_params: list[object] = [match_expr]
    if user_filter_id is not None:
        sql.append("AND (d.source_id IS NULL OR d.source_id IN (SELECT id FROM sources WHERE user_id = ?))")
        sqlite_params.append(user_filter_id)

    if kinds:
        sql.append(f"AND d.kind IN ({','.join('?' * len(kinds))})")
        sqlite_params.extend(kinds)
    if source_ids:
        sql.append(f"AND d.source_id IN ({','.join('?' * len(source_ids))})")
        sqlite_params.extend(source_ids)

    sql.append("ORDER BY score LIMIT ?")
    sqlite_params.append(limit)

    try:
        rows = conn.execute(" ".join(sql), sqlite_params).fetchall()
    except sqlite3.OperationalError:
        return []

    return [
        SearchHit(
            kind=row[0],
            entity_id=row[1],
            source_id=row[2],
            title=row[3] or "",
            snippet=row[4] or "",
            score=float(row[5]),
        )
        for row in rows
    ]
