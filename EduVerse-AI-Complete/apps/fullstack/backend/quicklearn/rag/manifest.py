"""Knowledge base and source inventory manifest for EduVerse AI.

Provides deterministic facts about the current authenticated user's uploaded sources.
Retrieval alone cannot answer inventory or set questions ("how many documents do I have?",
"is file X uploaded?", "list all files in my library"). This module computes the exact,
isolated inventory directly from the database and renders an authoritative system note.

Cross-user isolation:
Sources are queried strictly for the authenticated user (or unauthenticated demo user if
user_id is None). Other users' sources, deleted records, and out-of-scope files are
never visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.enums import SourceStatus
from ..db.models import Segment, Source
from ..db.session import session_scope

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceManifestItem:
    """One document or media source in the user's inventory."""

    id: int
    title: str
    kind: str
    status: str
    page_count: int | None
    segment_count: int
    size_bytes: int | None
    error: str | None


@dataclass(frozen=True, slots=True)
class UserSourceManifest:
    """Deterministic inventory of sources accessible to a specific user and scope."""

    user_id: int | None
    scope_type: str
    scope_id: int | None
    total_sources: int
    ready_sources: int
    pending_sources: int
    failed_sources: int
    total_pages: int
    total_segments: int
    items: tuple[SourceManifestItem, ...] = field(default_factory=tuple)


def get_user_source_manifest(
    user_id: int | None,
    scope_type: str = "global",
    scope_id: int | None = None,
    session: Session | None = None,
) -> UserSourceManifest:
    """Query the database to build a deterministic manifest of accessible sources."""
    if session is not None:
        return _query_manifest(session, user_id, scope_type, scope_id)
    with session_scope() as sess:
        return _query_manifest(sess, user_id, scope_type, scope_id)


def _query_manifest(
    session: Session,
    user_id: int | None,
    scope_type: str,
    scope_id: int | None,
) -> UserSourceManifest:
    # 1. Base query strictly scoped by tenant user_id
    stmt = select(Source)
    if user_id is not None:
        stmt = stmt.where(Source.user_id == user_id)
    else:
        stmt = stmt.where(Source.user_id.is_(None))

    # 2. Scope filtering
    if scope_type == "source" and scope_id is not None:
        stmt = stmt.where(Source.id == scope_id)
    elif scope_type == "folder" and scope_id is not None:
        stmt = stmt.where(Source.folder_id == scope_id)

    # Deterministic order
    stmt = stmt.order_by(Source.title.asc(), Source.id.asc())
    sources = list(session.execute(stmt).scalars())

    if not sources:
        return UserSourceManifest(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            total_sources=0,
            ready_sources=0,
            pending_sources=0,
            failed_sources=0,
            total_pages=0,
            total_segments=0,
            items=(),
        )

    source_ids = [s.id for s in sources]

    # 3. Aggregate segment counts per source
    seg_counts = dict(
        session.execute(
            select(Segment.source_id, func.count(Segment.id))
            .where(Segment.source_id.in_(source_ids))
            .group_by(Segment.source_id)
        ).all()
    )

    items: list[SourceManifestItem] = []
    ready_count = 0
    pending_count = 0
    failed_count = 0
    total_pages = 0
    total_segments = 0

    for s in sources:
        status_val = str(s.status.value) if hasattr(s.status, "value") else str(s.status)
        is_ready = s.status == SourceStatus.READY or status_val == "ready"
        is_failed = s.status == SourceStatus.FAILED or status_val == "failed"
        is_pending = not is_ready and not is_failed

        if is_ready:
            ready_count += 1
        elif is_failed:
            failed_count += 1
        else:
            pending_count += 1

        pages = s.page_count or 0
        total_pages += pages

        segs = int(seg_counts.get(s.id, 0))
        total_segments += segs

        items.append(
            SourceManifestItem(
                id=s.id,
                title=s.title or f"Source #{s.id}",
                kind=str(s.kind.value) if hasattr(s.kind, "value") else str(s.kind),
                status=status_val,
                page_count=s.page_count,
                segment_count=segs,
                size_bytes=s.size_bytes,
                error=s.error,
            )
        )

    return UserSourceManifest(
        user_id=user_id,
        scope_type=scope_type,
        scope_id=scope_id,
        total_sources=len(sources),
        ready_sources=ready_count,
        pending_sources=pending_count,
        failed_sources=failed_count,
        total_pages=total_pages,
        total_segments=total_segments,
        items=tuple(items),
    )


def render_manifest_note(manifest: UserSourceManifest) -> str:
    """Format the manifest as an authoritative system prompt context block."""
    if manifest.total_sources == 0:
        return (
            "Document inventory: The user's active library currently contains 0 uploaded sources. "
            "If the user asks what documents are available or asks to analyze uploaded material, "
            "inform them that no documents are uploaded yet."
        )

    # Detect title duplicates to disambiguate for the assistant
    title_counts: dict[str, int] = {}
    for item in manifest.items:
        title_counts[item.title] = title_counts.get(item.title, 0) + 1

    lines = [
        f"Document inventory: {manifest.total_sources} total source(s) "
        f"({manifest.ready_sources} ready, {manifest.pending_sources} pending, {manifest.failed_sources} failed). "
        f"Total indexed pages: {manifest.total_pages}, segments: {manifest.total_segments}."
    ]

    for item in manifest.items:
        display_title = item.title
        if title_counts[item.title] > 1:
            display_title = f"{item.title} (Source ID: {item.id})"

        if item.status == "ready":
            page_info = f"{item.page_count} pages" if item.page_count else "page count n/a"
            lines.append(f'- "{display_title}": Ready ({page_info}, {item.segment_count} segments)')
        elif item.status == "failed":
            err_msg = f": {item.error}" if item.error else ""
            lines.append(f'- "{display_title}": Ingestion Failed{err_msg}')
        else:
            lines.append(f'- "{display_title}": Ingestion Pending ({item.status})')

    lines.append(
        "Inventory rule: Use these verified inventory facts when answering questions about what documents, "
        "chapters, or files exist in the user's library. Do not hallucinate files not listed here."
    )

    return "\n".join(lines)
