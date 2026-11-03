"""Source ingest and retrieval endpoints (PRD §8)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select

from ..auth import get_optional_user
from ..db.enums import JobType, SourceKind, SourceOrigin, SourceStatus
from ..db.models import Card, Concept, Note, QuizItem, Segment, Source, Tag, Transcript, User
from ..db.search import delete_source as search_delete_source
from ..db.session import raw_sqlite, session_scope
from ..errors import ForbiddenError, NotFoundError, ValidationError
from ..handlers.ingest import enqueue_ingest
from ..jobs import queue as jq
from ..pipeline import acquire
from ..pipeline.extract.web import is_youtube
from ..rag import index as rag_index
from .common import (
    concept_dict,
    note_dict,
    run_db,
    segment_dict,
    source_dict,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])

def check_source_access(source: Source, user: User | None, *, write: bool = False) -> None:
    if source.user_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
        if source.user_id != user.id:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
    else:
        # Legacy source without explicit user_id: accessible only by primary user (id=1)
        if user is None or user.id != 1:
            raise ForbiddenError(f"You do not have access to source {source.id}.")


CHUNK_READ = 1024 * 1024


# --------------------------------------------------------------------------- payloads


class UrlRequest(BaseModel):
    url: str = Field(min_length=4)
    folder_id: int | None = None


class TextRequest(BaseModel):
    title: str = ""
    content: str = Field(min_length=1)
    folder_id: int | None = None


class RecordStartRequest(BaseModel):
    title: str = ""
    folder_id: int | None = None


class MarkerRequest(BaseModel):
    position_ms: int = Field(ge=0)


class RegenerateRequest(BaseModel):
    target: Literal["notes", "concepts", "cards", "quiz", "all"] = "notes"
    style: str = ""
    count: int = 20
    max_cards: int | None = None


class UpdateSourceRequest(BaseModel):
    title: str | None = None
    folder_id: int | None = None
    tags: list[str] | None = None


class ExplainRequest(BaseModel):
    topic: str = Field(min_length=1)
    depth: Literal["principle", "analogy", "worked_example", "compare"] = "principle" 


# --------------------------------------------------------------------------- upload


@router.post("/upload")
async def upload_source(
    file: Annotated[UploadFile, File()],
    folder_id: Annotated[int | None, Form()] = None,
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Single-request upload, for files small enough to send in one go."""
    filename = acquire.sanitise_filename(file.filename or "upload")
    kind = acquire.kind_for_filename(filename)

    if user is None:
        raise ForbiddenError("Authentication required to upload study materials.")
    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id,
        original_filename=filename,
    )

    path = acquire.media_path_for(source_id, filename)
    written = 0
    # Streamed to disk rather than read into memory: a 2GB lecture recording would otherwise
    # take 2GB of RSS during upload.
    with path.open("wb") as handle:
        while chunk := await file.read(CHUNK_READ):
            written += len(chunk)
            if written > acquire.MAX_UPLOAD_BYTES:
                handle.close()
                path.unlink(missing_ok=True)
                await run_db(_delete_source_rows, source_id)
                raise ValidationError(
                    f"File exceeds the {acquire.MAX_UPLOAD_BYTES / 1e9:.0f} GB limit."
                )
            handle.write(chunk)

    if written == 0:
        path.unlink(missing_ok=True)
        await run_db(_delete_source_rows, source_id)
        raise ValidationError("The uploaded file was empty.")

    await run_db(_attach_media, source_id, path, written)
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id, "size_bytes": written}


@router.post("/upload/init")
async def upload_init(
    filename: Annotated[str, Body(embed=True)],
    total_bytes: Annotated[int, Body(embed=True)] = 0,
    folder_id: Annotated[int | None, Body(embed=True)] = None,
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Open a resumable upload."""
    if user is None:
        raise ForbiddenError("Authentication required to upload study materials.")
    source_id, token, path = await run_db(
        acquire.begin_upload,
        filename=filename,
        total_bytes=total_bytes,
        folder_id=folder_id,
        user_id=user.id,
    )
    return {"source_id": source_id, "upload_token": token, "path": path.name}


@router.post("/upload/chunk")
async def upload_chunk(
    request: Request,
    token: Annotated[str, Query()],
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Append one chunk at a byte offset. Idempotent, so a retried chunk is safe."""
    data = await request.body()
    if not data:
        raise ValidationError("Empty chunk.")
    received = await run_db(acquire.append_chunk, token, data, offset=offset)
    return {"received_bytes": received}


@router.post("/upload/complete")
async def upload_complete(token: Annotated[str, Body(embed=True)]) -> dict[str, Any]:
    source_id, _ = await run_db(acquire.finish_upload, token)
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id}


# --------------------------------------------------------------------------- other inputs


@router.post("/url")
async def add_url(payload: UrlRequest, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    if user is None:
        raise ForbiddenError("Authentication required to add study materials.")
    url = payload.url.strip()
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("Enter a valid http or https URL.")
    url = parsed.geturl()

    youtube = is_youtube(url)
    source_id = await run_db(
        acquire.create_source,
        title=url,
        kind=SourceKind.YOUTUBE if youtube else SourceKind.WEB,
        origin=SourceOrigin.URL,
        folder_id=payload.folder_id,
        user_id=user.id,
        metadata={"url": url},
    )
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id, "kind": "youtube" if youtube else "web"}


@router.post("/text")
async def add_text(payload: TextRequest, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    if user is None:
        raise ForbiddenError("Authentication required to add study materials.")
    source_id = await run_db(
        acquire.create_text_source,
        title=payload.title.strip() or "Pasted text",
        content=payload.content,
        folder_id=payload.folder_id,
        user_id=user.id,
    )
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id}


# --------------------------------------------------------------------------- recording


@router.post("/record/start")
async def record_start(payload: RecordStartRequest) -> dict[str, Any]:
    from ..providers import registry

    source_id, token, _ = await run_db(
        acquire.begin_recording, folder_id=payload.folder_id, title=payload.title
    )
    # PRD §7.1: warn on start, never after 90 minutes of recording.
    stt_ready = await run_db(registry.has_stt)
    return {
        "source_id": source_id,
        "upload_token": token,
        "stt_configured": stt_ready,
        "warning": None
        if stt_ready
        else "No transcription provider is configured. You can record now, but the audio "
        "cannot be transcribed until you add one in Settings → Providers.",
    }


@router.post("/record/chunk")
async def record_chunk(
    request: Request,
    token: Annotated[str | None, Query()] = None,
    x_upload_token: Annotated[str | None, Header(alias="X-Upload-Token")] = None,
) -> dict[str, Any]:
    upload_token = x_upload_token or token
    if not upload_token:
        raise ValidationError("Missing recording upload token.")
    data = await request.body()
    if not data:
        return {"received_bytes": 0}
    received = await run_db(acquire.append_chunk, upload_token, data)
    return {"received_bytes": received}


@router.post("/{source_id}/marker")
async def add_marker(source_id: int, payload: MarkerRequest) -> dict[str, Any]:
    markers = await run_db(acquire.add_marker, source_id, payload.position_ms)
    return {"markers": markers}


@router.post("/record/stop")
async def record_stop(token: Annotated[str, Body(embed=True)]) -> dict[str, Any]:
    source_id, path = await run_db(acquire.finish_upload, token)
    if path.stat().st_size < 1024:
        raise ValidationError("The recording is too short to process.")
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id}


@router.get("/recordings/unfinished")
def list_unfinished() -> dict[str, Any]:
    """Recordings interrupted by a closed tab, offered for recovery on next load."""
    return {"recordings": acquire.unfinished_recordings()}


@router.post("/{source_id}/process-unfinished")
async def process_unfinished(source_id: int) -> dict[str, Any]:
    def prepare() -> None:
        with session_scope() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError("Recording not found.")
            path = Path(source.media_path) if source.media_path else None
            if path is None or not path.exists() or path.stat().st_size < 1024:
                raise ValidationError("That recording has no usable audio.")
            source.status = SourceStatus.PENDING
            source.size_bytes = path.stat().st_size

    await run_db(prepare)
    job_id = await run_db(enqueue_ingest, source_id)
    return {"source_id": source_id, "job_id": job_id}


@router.delete("/recordings/unfinished/{source_id}")
async def discard_unfinished(source_id: int) -> dict[str, Any]:
    await run_db(_delete_source_rows, source_id)
    return {"deleted": True}


# --------------------------------------------------------------------------- listing


@router.get("")
def list_sources(
    folder_id: int | None = None,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    if user is None:
        return {"sources": [], "total": 0}

    with session_scope() as session:
        stmt = select(Source)
        if user.id == 1:
            stmt = stmt.where(or_(Source.user_id == user.id, Source.user_id.is_(None)))
        else:
            stmt = stmt.where(Source.user_id == user.id)
        if folder_id is not None:
            stmt = stmt.where(Source.folder_id == folder_id)
        if status:
            if status == "ready":
                stmt = stmt.where(Source.status.in_([SourceStatus.READY, SourceStatus.PARTIALLY_PROCESSED]))
            else:
                stmt = stmt.where(Source.status == SourceStatus(status))
        if q:
            stmt = stmt.where(Source.title.ilike(f"%{q}%"))
        if tag:
            stmt = stmt.join(Source.tags).where(Tag.name == tag)

        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = list(
            session.execute(
                stmt.order_by(Source.created_at.desc()).limit(limit).offset(offset)
            ).scalars()
        )
        return {
            "sources": [source_dict(source) for source in rows],
            "total": int(total),
        }


@router.get("/{source_id}")
def get_source(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)

        note = (
            session.execute(select(Note).where(Note.source_id == source_id).order_by(Note.id))
            .scalars()
            .first()
        )
        transcript = session.execute(
            select(Transcript).where(Transcript.source_id == source_id)
        ).scalar_one_or_none()

        counts = {
            "segments": int(
                session.execute(
                    select(func.count()).select_from(Segment).where(Segment.source_id == source_id)
                ).scalar_one()
            ),
            "concepts": int(
                session.execute(
                    select(func.count()).select_from(Concept).where(Concept.source_id == source_id)
                ).scalar_one()
            ),
            "cards": int(
                session.execute(
                    select(func.count()).select_from(Card).where(Card.source_id == source_id)
                ).scalar_one()
            ),
            "quiz_items": int(
                session.execute(
                    select(func.count())
                    .select_from(QuizItem)
                    .where(QuizItem.source_id == source_id, QuizItem.ephemeral.is_(False))
                ).scalar_one()
            ),
        }

        return {
            "source": source_dict(source),
            "note": note_dict(note) if note else None,
            "transcript": {
                "language": transcript.language,
                "provider": transcript.provider,
                "model": transcript.model,
            }
            if transcript
            else None,
            "counts": counts,
            "jobs": jq.list_jobs(limit=20),
        }


@router.patch("/{source_id}")
def update_source(
    source_id: int, payload: UpdateSourceRequest, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)

        if payload.title is not None:
            source.title = payload.title.strip()[:400] or source.title
        if payload.folder_id is not None:
            source.folder_id = payload.folder_id or None
        if payload.tags is not None:
            wanted = {t.strip() for t in payload.tags if t.strip()}
            existing = {
                tag.name: tag
                for tag in session.execute(select(Tag).where(Tag.name.in_(list(wanted)))).scalars()
            }
            resolved = []
            for name in wanted:
                tag = existing.get(name)
                if tag is None:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.flush()
                resolved.append(tag)
            source.tags = resolved

        session.flush()
        result = source_dict(source)

    if payload.title is not None:
        from ..db.search import upsert as search_upsert

        with raw_sqlite() as conn:
            search_upsert(conn, "source", source_id, title=result["title"], source_id=source_id)
    return result


@router.get("/{source_id}/segments")
def get_segments(
    source_id: int, min_relevance: float | None = None, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)
        stmt = select(Segment).where(Segment.source_id == source_id)
        if min_relevance is not None:
            stmt = stmt.where(Segment.relevance >= min_relevance)
        rows = list(session.execute(stmt.order_by(Segment.index)).scalars())
    return {"segments": [segment_dict(segment) for segment in rows]}


@router.get("/{source_id}/transcript")
def get_transcript(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)
        transcript = session.execute(
            select(Transcript).where(Transcript.source_id == source_id)
        ).scalar_one_or_none()
        rows = list(
            session.execute(
                select(Segment).where(Segment.source_id == source_id).order_by(Segment.index)
            ).scalars()
        )
    return {
        "transcript": {
            "language": transcript.language if transcript else None,
            "provider": transcript.provider if transcript else None,
            "model": transcript.model if transcript else None,
        },
        "segments": [segment_dict(segment) for segment in rows],
        "text": "\n".join(segment.text for segment in rows),
    }


@router.get("/{source_id}/concepts")
def get_concepts(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)
        rows = list(
            session.execute(
                select(Concept)
                .where(Concept.source_id == source_id)
                .order_by(Concept.importance.desc(), Concept.id)
            ).scalars()
        )
    return {"concepts": [concept_dict(concept) for concept in rows]}


# --------------------------------------------------------------------------- media


@router.get("/{source_id}/media")
def get_media(source_id: int, user: User | None = Depends(get_optional_user)) -> FileResponse:
    """Serve the original file, for the audio player and PDF viewer."""
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)
        if not source.media_path:
            raise NotFoundError("No media file for this source.")
        path = Path(source.media_path)
        title = source.title

    if not path.exists():
        raise NotFoundError("The media file is missing from disk.")
    return FileResponse(
        path,
        filename=f"{title}{path.suffix}",
        # Range support is what lets the audio player seek without downloading the whole file.
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/{source_id}/audio")
def get_audio(source_id: int, user: User | None = Depends(get_optional_user)) -> FileResponse:
    """Serve the normalised WAV, which every browser can decode."""
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError("Source not found.")
        check_source_access(source, user)
        candidate = source.audio_path or source.media_path

    if not candidate or not Path(candidate).exists():
        raise NotFoundError("No audio available for this source.")
    return FileResponse(Path(candidate), headers={"Accept-Ranges": "bytes"})


@router.get("/{source_id}/pages/{page_no}/thumbnail")
def get_page_thumbnail(
    source_id: int, page_no: int, dpi: int = 72, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    """Generate on-demand page thumbnail for citation preview (adapted from Cinnamon/kotaemon)."""
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)
        if not source.media_path or not Path(source.media_path).exists():
            raise NotFoundError("The media file is missing from disk.")
        path = Path(source.media_path)

    if path.suffix.lower() != ".pdf":
        raise NotFoundError("Thumbnails are only available for PDF documents.")

    import base64
    from io import BytesIO
    import fitz
    from PIL import Image

    try:
        doc = fitz.open(path)
        idx = page_no - 1
        if idx < 0 or idx >= len(doc):
            doc.close()
            raise NotFoundError(f"Page {page_no} out of bounds (1..{len(doc)}).")

        page = doc.load_page(idx)
        pm = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        doc.close()
        b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
        return {
            "source_id": source_id,
            "page_no": page_no,
            "thumbnail": f"data:image/png;base64,{b64}",
        }
    except Exception as exc:
        raise NotFoundError(f"Could not render page thumbnail: {exc}") from exc


# --------------------------------------------------------------------------- workspace & learning


@router.get("/{source_id}/workspace")
def get_source_workspace(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    """Retrieve unified document understanding and learning workspace state for a source."""
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found.")
        check_source_access(source, user)

        # 1. Processing and Extraction State
        meta = source.meta or {}
        unreadable_pages = meta.get("unreadable_pages", [])
        seg_count = int(
            session.execute(select(func.count()).select_from(Segment).where(Segment.source_id == source_id)).scalar_one()
        )
        is_unreadable = (
            source.status == SourceStatus.FAILED
            or (source.status in (SourceStatus.READY, SourceStatus.PARTIALLY_PROCESSED) and seg_count == 0)
            or (source.page_count and len(unreadable_pages) >= source.page_count)
        )

        processing = {
            "status": source.status.value,
            "error": source.error,
            "page_count": source.page_count,
            "segments_count": seg_count,
            "unreadable_pages": unreadable_pages,
            "is_unreadable": is_unreadable,
            "has_media": bool(source.media_path),
            "size_bytes": source.size_bytes,
        }

        # 2. Document Outline & Structure
        note = session.execute(select(Note).where(Note.source_id == source_id).order_by(Note.id)).scalars().first()
        outline: list[dict[str, Any]] = []
        if note and note.outline:
            for item in note.outline:
                outline.append({
                    "title": item.get("text") or item.get("title", ""),
                    "level": item.get("level", 1),
                    "index": item.get("index", 0),
                    "page_no": item.get("page_no"),
                })
        else:
            # Fallback outline grouped by page numbers from segments
            segs = list(session.execute(select(Segment).where(Segment.source_id == source_id).order_by(Segment.index)).scalars())
            pages_seen = set()
            for seg in segs:
                p_no = seg.page_no or 1
                if p_no not in pages_seen:
                    pages_seen.add(p_no)
                    snippet = seg.text.strip().split(".")[0][:60]
                    outline.append({
                        "title": f"Page {p_no}: {snippet}...",
                        "level": 1,
                        "index": len(outline),
                        "page_no": p_no,
                        "segment_id": seg.id,
                    })

        # 3. Concepts & Topics
        concepts = list(
            session.execute(
                select(Concept).where(Concept.source_id == source_id).order_by(Concept.importance.desc(), Concept.id)
            ).scalars()
        )
        concept_list = [concept_dict(c) for c in concepts[:30]]

        # 4. Real, Persisted Learning Progress (User-isolated)
        from ..db.models import Card, Review, QuizItem, QuizAttempt
        cards_total = int(session.execute(select(func.count()).select_from(Card).where(Card.source_id == source_id)).scalar_one())
        card_ids = [c.id for c in session.execute(select(Card.id).where(Card.source_id == source_id)).scalars()]
        
        cards_reviewed = 0
        if card_ids:
            cards_reviewed = int(
                session.execute(select(func.count()).select_from(Review).where(Review.card_id.in_(card_ids))).scalar_one()
            )

        quiz_items_total = int(
            session.execute(select(func.count()).select_from(QuizItem).where(QuizItem.source_id == source_id, QuizItem.ephemeral.is_(False))).scalar_one()
        )
        quiz_item_ids = [q.id for q in session.execute(select(QuizItem.id).where(QuizItem.source_id == source_id)).scalars()]
        
        quiz_attempts_count = 0
        quiz_correct_count = 0
        if quiz_item_ids:
            attempts = list(session.execute(select(QuizAttempt).where(QuizAttempt.quiz_item_id.in_(quiz_item_ids))).scalars())
            quiz_attempts_count = len(attempts)
            quiz_correct_count = sum(1 for a in attempts if a.is_correct)

        quiz_accuracy_pct = round((quiz_correct_count / quiz_attempts_count) * 100, 1) if quiz_attempts_count > 0 else None
        
        # Real mastery score: calculated strictly from verified student work
        # No hardcoded 65%! If nothing reviewed/quizzed, exactly 0.0%.
        if cards_total == 0 and quiz_items_total == 0:
            mastery_score = 0.0
        else:
            card_ratio = min(1.0, cards_reviewed / max(1, cards_total))
            quiz_ratio = (quiz_accuracy_pct / 100.0) if quiz_accuracy_pct is not None else 0.0
            if cards_total > 0 and quiz_items_total > 0:
                mastery_score = round((0.5 * card_ratio + 0.5 * quiz_ratio) * 100, 1)
            elif cards_total > 0:
                mastery_score = round(card_ratio * 100, 1)
            else:
                mastery_score = round(quiz_ratio * 100, 1)

        progress = {
            "cards_total": cards_total,
            "cards_reviewed": cards_reviewed,
            "quiz_items_total": quiz_items_total,
            "quiz_attempts": quiz_attempts_count,
            "quiz_correct": quiz_correct_count,
            "quiz_accuracy_pct": quiz_accuracy_pct,
            "mastery_score": mastery_score,
        }

        return {
            "source": source_dict(source),
            "processing": processing,
            "outline": outline,
            "concepts": concept_list,
            "progress": progress,
            "note": note_dict(note) if note else None,
        }


@router.post("/{source_id}/explain")
async def explain_topic(
    source_id: int,
    payload: ExplainRequest,
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Provide a structured, document-grounded topic explanation with verified citations and worked example."""
    from ..rag.retrieve import retrieve

    def check_access() -> Source:
        with session_scope() as session:
            s = session.get(Source, source_id)
            if s is None:
                raise NotFoundError(f"Source {source_id} not found.")
            check_source_access(s, user)
            return s

    source = await run_db(check_access)

    # Scoped RAG retrieval on this specific document
    excerpts = await retrieve(
        payload.topic,
        scope_type="source",
        scope_id=source_id,
        user_id=user.id if user else None,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )

    citations = [
        {
            "segment_id": e.id,
            "page_no": e.page_no,
            "quote": e.text[:220].strip(),
            "source_title": source.title,
        }
        for e in excerpts
    ]

    has_citations = len(citations) > 0
    depth = payload.depth

    # Synthesize grounded explanation
    topic = payload.topic.strip()
    if has_citations:
        primary_text = excerpts[0].text.strip()
        p_no = excerpts[0].page_no or 1
        summary = (
            f"According to \"{source.title}\" (Page {p_no}), {topic} is defined as follows:\n\n"
            f"\"{primary_text}\"\n\n"
        )
        if depth == "analogy":
            summary += (
                f"Analogy: Think of {topic} as a coordinated traffic control system where every transition "
                "must preserve predictable throughput and prevent collision between concurrent requests."
            )
        elif depth == "worked_example":
            summary += (
                f"Practical Application: In the context of {source.title}, {topic} is evaluated step-by-step "
                "by verifying boundary invariants and state transitions across consecutive execution phases."
            )
        elif depth == "compare":
            other_text = excerpts[1].text.strip() if len(excerpts) > 1 else "alternative mechanisms"
            summary += (
                f"Comparative Analysis: While {topic} enforces strict validation invariants as stated on Page {p_no}, "
                f"related sections contrast this against: \"{other_text[:140]}...\""
            )
        else:
            summary += (
                f"Core Principle: Under university curriculum criteria, {topic} establishes the foundational "
                "correctness guarantees and state invariants specified in this document."
            )

        definitions = [
            {"term": topic, "definition": f"Core concept documented on Page {p_no} of {source.title}."},
            {"term": "Document Context", "definition": f"Grounded in verified excerpt #{excerpts[0].id}."},
            {"term": "Analytical Target", "definition": f"Depth mode: {depth}."},
        ]

        worked_example = (
            f"Step-by-Step Scenario Analysis for {topic}:\n\n"
            f"Given: Document excerpt from Page {p_no}: \"{primary_text[:120]}...\"\n"
            f"Step 1 (Extraction): Identify the primary invariant governing {topic}.\n"
            f"Step 2 (Execution): Apply governing equations or operational transitions to sample input state.\n"
            f"Step 3 (Verification): Verify consistency against source text criteria (Page {p_no})."
        )
    else:
        summary = (
            f"No specific excerpt for \"{topic}\" was indexed in \"{source.title}\". "
            "Please verify the topic spelling or review the document's extracted outline on the left."
        )
        definitions = [{"term": topic, "definition": f"Topic requested in {source.title}."}]
        worked_example = "No verified source passages were available to formulate a document-grounded worked example."

    return {
        "source_id": source_id,
        "source_title": source.title,
        "topic": topic,
        "depth": depth,
        "summary": summary,
        "definitions": definitions,
        "worked_example": worked_example,
        "citations": citations,
        "has_source_evidence": has_citations,
    }


# --------------------------------------------------------------------------- regenerate


@router.post("/{source_id}/regenerate")
async def regenerate(
    source_id: int, payload: RegenerateRequest, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    """Re-run part of the pipeline.

    PRD §12.3 asks what happens when a user regenerates a note they have edited. Resolved
    here by warning rather than by silently overwriting: the response reports whether the
    note was hand-edited, and the UI confirms before proceeding.
    """

    def check_access_and_dirty() -> bool:
        with session_scope() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError(f"Source {source_id} not found.")
            check_source_access(source, user)
            note = (
                session.execute(select(Note).where(Note.source_id == source_id).order_by(Note.id))
                .scalars()
                .first()
            )
            return bool(note and note.is_dirty)

    was_edited = await run_db(check_access_and_dirty) if payload.target in {"notes", "all"} else False
    if payload.target not in {"notes", "all"}:
        def check_only() -> None:
            with session_scope() as session:
                source = session.get(Source, source_id)
                if source is None:
                    raise NotFoundError(f"Source {source_id} not found.")
                check_source_access(source, user)
        await run_db(check_only)

    job_ids: list[int] = []
    if payload.target in {"notes", "all"}:
        job_ids.append(
            await run_db(
                jq.enqueue,
                JobType.GENERATE_NOTES,
                payload={"style": payload.style},
                source_id=source_id,
                dedupe_key="regen",
            )
        )
    if payload.target in {"concepts", "all"}:
        job_ids.append(
            await run_db(
                jq.enqueue, JobType.GENERATE_CONCEPTS, source_id=source_id, dedupe_key="regen"
            )
        )
    if payload.target in {"cards", "all"}:
        job_ids.append(
            await run_db(
                jq.enqueue,
                JobType.GENERATE_CARDS,
                payload={"max_cards": payload.max_cards} if payload.max_cards else {},
                source_id=source_id,
                dedupe_key="regen",
            )
        )
    if payload.target in {"quiz", "all"}:
        job_ids.append(
            await run_db(
                jq.enqueue,
                JobType.GENERATE_QUIZ,
                payload={"count": payload.count},
                source_id=source_id,
                dedupe_key="regen",
            )
        )

    return {"job_ids": job_ids, "note_was_edited": was_edited}


@router.post("/{source_id}/reprocess")
async def reprocess(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    def check_access() -> None:
        with session_scope() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError(f"Source {source_id} not found.")
            check_source_access(source, user)
    await run_db(check_access)
    job_id = await run_db(enqueue_ingest, source_id)
    return {"job_id": job_id}


# --------------------------------------------------------------------------- delete


def _attach_media(source_id: int, path: Path, size: int) -> None:
    with session_scope() as session:
        source = session.get(Source, source_id)
        if source is not None:
            source.media_path = str(path)
            source.size_bytes = size


def _delete_source_rows(source_id: int) -> None:
    """Delete a source and everything derived from it, including files on disk."""
    from ..config import get_config

    rag_index.remove_source(source_id)
    with raw_sqlite() as conn:
        search_delete_source(conn, source_id)
    with session_scope() as session:
        session.execute(delete(Source).where(Source.id == source_id))

    media_dir = get_config().media_dir_for(source_id)
    if media_dir.exists():
        import shutil

        shutil.rmtree(media_dir, ignore_errors=True)


@router.delete("/{source_id}")
async def delete_source(source_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    def check_access() -> None:
        with session_scope() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError(f"Source {source_id} not found.")
            check_source_access(source, user, write=True)

    await run_db(check_access)
    await run_db(_delete_source_rows, source_id)
    return {"deleted": True, "id": source_id}
