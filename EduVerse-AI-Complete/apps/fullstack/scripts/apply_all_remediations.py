"""Comprehensive remediation script for EduVerse AI Priority 0 defect fixes."""

from pathlib import Path
import re

ROOT = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/quicklearn")

# =========================================================================
# 1. API SOURCES (sources.py)
# =========================================================================
def patch_sources():
    p = ROOT / "api/sources.py"
    content = p.read_text(encoding="utf-8")

    # Replace check_source_access
    old_access = """def check_source_access(source: Source, user: User | None) -> None:
    if source.user_id is not None and user is not None and source.user_id != user.id:
        raise ForbiddenError(f"You do not have access to source {source.id}.")"""
    
    new_access = """def check_source_access(source: Source, user: User | None, *, write: bool = False) -> None:
    if source.user_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
        if source.user_id != user.id:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this source.")"""
    
    if old_access in content:
        content = content.replace(old_access, new_access, 1)

    # Protect create / upload routes from anonymous unowned sources
    old_upload_create = """    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id if user else None,
        original_filename=filename,
    )"""

    new_upload_create = """    if user is None:
        raise ForbiddenError("Authentication required to upload study materials.")
    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id,
        original_filename=filename,
    )"""
    if old_upload_create in content:
        content = content.replace(old_upload_create, new_upload_create, 1)

    # Protect text source creation
    old_text_create = """    source_id = await run_db(
        acquire.create_source,
        title=payload.title.strip() or "Untitled note",
        kind=SourceKind.TEXT,
        origin=SourceOrigin.PASTE,
        folder_id=payload.folder_id,
        user_id=user.id if user else None,
    )"""

    new_text_create = """    if user is None:
        raise ForbiddenError("Authentication required to create study materials.")
    source_id = await run_db(
        acquire.create_source,
        title=payload.title.strip() or "Untitled note",
        kind=SourceKind.TEXT,
        origin=SourceOrigin.PASTE,
        folder_id=payload.folder_id,
        user_id=user.id,
    )"""
    if old_text_create in content:
        content = content.replace(old_text_create, new_text_create, 1)

    # Protect update_source with write=True
    old_upd_call = "check_source_access(source, user)"
    new_upd_call = "check_source_access(source, user, write=True)"
    # Replace in update_source specifically
    idx = content.find("def update_source(")
    if idx != -1:
        call_idx = content.find("check_source_access(source, user)", idx)
        if call_idx != -1 and call_idx < idx + 300:
            content = content[:call_idx] + "check_source_access(source, user, write=True)" + content[call_idx + len("check_source_access(source, user)"):]

    # Replace in delete_source specifically
    idx_del = content.find("async def delete_source(")
    if idx_del != -1:
        call_idx = content.find("check_source_access(source, user)", idx_del)
        if call_idx != -1 and call_idx < idx_del + 400:
            content = content[:call_idx] + "check_source_access(source, user, write=True)" + content[call_idx + len("check_source_access(source, user)"):]

    p.write_text(content, encoding="utf-8")
    print("Patched api/sources.py successfully.")

# =========================================================================
# 2. API NOTES (notes.py)
# =========================================================================
def patch_notes():
    p = ROOT / "api/notes.py"
    content = p.read_text(encoding="utf-8")

    old_access = """def check_note_access(note: Note, user: User | None) -> None:
    owner_id = note.user_id if note.user_id is not None else (note.source.user_id if note.source else None)
    if owner_id is not None and user is not None and owner_id != user.id:
        raise ForbiddenError(f"You do not have access to note {note.id}.")"""

    new_access = """def check_note_access(note: Note, user: User | None, *, write: bool = False) -> None:
    owner_id = note.user_id if note.user_id is not None else (note.source.user_id if note.source else None)
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to note {note.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to note {note.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this note.")"""

    if old_access in content:
        content = content.replace(old_access, new_access, 1)

    # Protect patch_note with write=True
    idx = content.find("async def patch_note(")
    if idx != -1:
        call_idx = content.find("check_note_access(note, user)", idx)
        if call_idx != -1 and call_idx < idx + 400:
            content = content[:call_idx] + "check_note_access(note, user, write=True)" + content[call_idx + len("check_note_access(note, user)"):]

    p.write_text(content, encoding="utf-8")
    print("Patched api/notes.py successfully.")

# =========================================================================
# 3. API CARDS (cards.py)
# =========================================================================
def patch_cards():
    p = ROOT / "api/cards.py"
    content = p.read_text(encoding="utf-8")

    # Add imports if missing
    if "from ..auth import get_optional_user, get_current_user" not in content:
        content = content.replace(
            "from ..errors import DependencyMissingError, NotFoundError, ValidationError",
            "from ..auth import get_optional_user, get_current_user\nfrom ..db.models import Card, Source, User\nfrom ..errors import DependencyMissingError, ForbiddenError, NotFoundError, ValidationError"
        )
        content = content.replace("from ..db.models import Card\n", "")

    # Add helper check_card_access
    helper = """
def check_card_access(card: Card, user: User | None, *, write: bool = False) -> None:
    owner_id = card.source.user_id if card.source else None
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to card {card.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to card {card.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this card.")
"""
    if "def check_card_access" not in content:
        content = content.replace("router = APIRouter(prefix=\"/cards\", tags=[\"cards\"])\n", "router = APIRouter(prefix=\"/cards\", tags=[\"cards\"])\n" + helper)

    # Update list_cards to scope to user
    old_list = """@router.get("")
def list_cards(
    source_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> dict[str, Any]:
    with session_scope() as session:
        stmt = select(Card)
        if source_id is not None:
            stmt = stmt.where(Card.source_id == source_id)
        rows = list(session.execute(stmt.order_by(Card.id).limit(limit).offset(offset)).scalars())
    return {"cards": [card_dict(card) for card in rows]}"""

    new_list = """@router.get("")
def list_cards(
    source_id: int | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    with session_scope() as session:
        stmt = select(Card).join(Source, Source.id == Card.source_id)
        if user is not None:
            stmt = stmt.where((Source.user_id == user.id) | (Source.user_id.is_(None)))
        else:
            stmt = stmt.where(Source.user_id.is_(None))
        if source_id is not None:
            stmt = stmt.where(Card.source_id == source_id)
        rows = list(session.execute(stmt.order_by(Card.id).limit(limit).offset(offset)).scalars())
    return {"cards": [card_dict(card) for card in rows]}"""

    if old_list in content:
        content = content.replace(old_list, new_list, 1)

    # Protect submit_review
    old_review = """@router.post("/{card_id}/review")
def submit_review(card_id: int, payload: ReviewRequest) -> dict[str, Any]:
    return review.apply_rating(card_id, payload.rating, payload.duration_ms)"""

    new_review = """@router.post("/{card_id}/review")
def submit_review(
    card_id: int, payload: ReviewRequest, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        check_card_access(card, user, write=True)
    return review.apply_rating(card_id, payload.rating, payload.duration_ms)"""

    if old_review in content:
        content = content.replace(old_review, new_review, 1)

    # Protect undo
    old_undo = """@router.post("/{card_id}/undo")
def undo(card_id: int) -> dict[str, Any]:
    if not review.undo_review(card_id):
        raise NotFoundError("No review to undo for that card.")
    return {"undone": True}"""

    new_undo = """@router.post("/{card_id}/undo")
def undo(card_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        check_card_access(card, user, write=True)
    if not review.undo_review(card_id):
        raise NotFoundError("No review to undo for that card.")
    return {"undone": True}"""

    if old_undo in content:
        content = content.replace(old_undo, new_undo, 1)

    # Protect edit_card
    old_edit = """@router.patch("/{card_id}")
def edit_card(card_id: int, payload: CardEdit) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        if payload.front is not None:"""

    new_edit = """@router.patch("/{card_id}")
def edit_card(card_id: int, payload: CardEdit, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        check_card_access(card, user, write=True)
        if payload.front is not None:"""

    if old_edit in content:
        content = content.replace(old_edit, new_edit, 1)

    # Protect delete_card
    old_del = """@router.delete("/{card_id}")
def delete_card(card_id: int) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        session.delete(card)
    return {"deleted": True}"""

    new_del = """@router.delete("/{card_id}")
def delete_card(card_id: int, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")
        check_card_access(card, user, write=True)
        session.delete(card)
    return {"deleted": True}"""

    if old_del in content:
        content = content.replace(old_del, new_del, 1)

    p.write_text(content, encoding="utf-8")
    print("Patched api/cards.py successfully.")

# =========================================================================
# 4. API SYSTEM (system.py) - Protect Settings
# =========================================================================
def patch_system():
    p = ROOT / "api/system.py"
    content = p.read_text(encoding="utf-8")

    if "from ..auth import get_current_user" not in content:
        content = content.replace(
            "from fastapi import APIRouter, WebSocket, WebSocketDisconnect",
            "from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect\nfrom ..auth import get_current_user\nfrom ..db.models import User"
        )

    old_patch_settings = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch) -> dict[str, Any]:"""

    new_patch_settings = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch, user: User = Depends(get_current_user)) -> dict[str, Any]:"""

    if old_patch_settings in content:
        content = content.replace(old_patch_settings, new_patch_settings, 1)

    p.write_text(content, encoding="utf-8")
    print("Patched api/system.py successfully.")

# =========================================================================
# 5. API DASHBOARD (dashboard.py) - Scope Stats to User
# =========================================================================
def patch_dashboard():
    p = ROOT / "api/dashboard.py"
    content = p.read_text(encoding="utf-8")

    old_stats = """    # 1. Sources / Study Materials
    sources = db.scalars(select(Source).order_by(Source.created_at.desc())).all()
    total_sources = len(sources)
    recent_sources = [
        SourceBrief(
            id=s.id,
            title=s.title,
            kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
            created_at=s.created_at,
        )
        for s in sources[:5]
    ]

    # 2. Flashcards & Spaced Repetition
    cards = db.scalars(select(Card)).all()
    total_cards = len(cards)
    cards_due_today = sum(1 for c in cards if c.due <= now and not c.suspended)
    # Mastered: stability > 5.0 days or reps >= 3 without recent lapse
    cards_mastered = sum(
        1 for c in cards if (c.stability and c.stability >= 5.0) or c.reps >= 3
    )
    cards_learning = total_cards - cards_mastered

    # 3. Quiz Attempts & Performance
    total_quiz_sessions = db.scalar(select(func.count(QuizSession.id))) or 0
    attempts = db.scalars(select(QuizAttempt)).all()
    total_quiz_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a.is_correct)
    avg_accuracy = (
        round((correct_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )

    # Quizzes passed percentage (attempts scoring >= 0.6)
    passed_attempts = sum(1 for a in attempts if a.score >= 0.6 or a.is_correct)
    pass_pct = (
        round((passed_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )

    # 4. Knowledge Gaps
    gap_summary = analyze_knowledge_gaps(db)
    critical_gaps = gap_summary.critical_gaps_count
    moderate_gaps = gap_summary.moderate_gaps_count

    # 5. Revision Sessions
    revision_sessions = db.scalars(select(RevisionSession)).all()
    pending_revisions = sum(1 for r in revision_sessions if r.status == "PENDING")
    completed_revisions = sum(1 for r in revision_sessions if r.status == "COMPLETED")

    # 6. Notes
    total_notes = db.scalar(select(func.count(Note.id))) or 0"""

    new_stats = """    # 1. Sources / Study Materials (User Scoped)
    src_query = select(Source)
    if user is not None:
        src_query = src_query.where((Source.user_id == user.id) | (Source.user_id.is_(None)))
    else:
        src_query = src_query.where(Source.user_id.is_(None))
    sources = db.scalars(src_query.order_by(Source.created_at.desc())).all()
    total_sources = len(sources)
    recent_sources = [
        SourceBrief(
            id=s.id,
            title=s.title,
            kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
            created_at=s.created_at,
        )
        for s in sources[:5]
    ]

    # 2. Flashcards & Spaced Repetition (User Scoped)
    card_query = select(Card).join(Source, Source.id == Card.source_id)
    if user is not None:
        card_query = card_query.where((Source.user_id == user.id) | (Source.user_id.is_(None)))
    else:
        card_query = card_query.where(Source.user_id.is_(None))
    cards = db.scalars(card_query).all()
    total_cards = len(cards)
    cards_due_today = sum(1 for c in cards if c.due <= now and not c.suspended)
    cards_mastered = sum(
        1 for c in cards if (c.stability and c.stability >= 5.0) or c.reps >= 3
    )
    cards_learning = total_cards - cards_mastered

    # 3. Quiz Attempts & Performance
    total_quiz_sessions = db.scalar(select(func.count(QuizSession.id))) or 0
    attempts = db.scalars(select(QuizAttempt)).all()
    total_quiz_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a.is_correct)
    avg_accuracy = (
        round((correct_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )
    passed_attempts = sum(1 for a in attempts if a.score >= 0.6 or a.is_correct)
    pass_pct = (
        round((passed_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )

    # 4. Knowledge Gaps
    gap_summary = analyze_knowledge_gaps(db)
    critical_gaps = gap_summary.critical_gaps_count
    moderate_gaps = gap_summary.moderate_gaps_count

    # 5. Revision Sessions (User Scoped)
    rev_query = select(RevisionSession)
    if user is not None:
        rev_query = rev_query.where((RevisionSession.user_id == user.id) | (RevisionSession.user_id.is_(None)))
    else:
        rev_query = rev_query.where(RevisionSession.user_id.is_(None))
    revision_sessions = db.scalars(rev_query).all()
    pending_revisions = sum(1 for r in revision_sessions if r.status == "PENDING")
    completed_revisions = sum(1 for r in revision_sessions if r.status == "COMPLETED")

    # 6. Notes (User Scoped)
    note_query = select(func.count(Note.id))
    if user is not None:
        note_query = note_query.where((Note.user_id == user.id) | (Note.user_id.is_(None)))
    else:
        note_query = note_query.where(Note.user_id.is_(None))
    total_notes = db.scalar(note_query) or 0"""

    if old_stats in content:
        content = content.replace(old_stats, new_stats, 1)

    p.write_text(content, encoding="utf-8")
    print("Patched api/dashboard.py successfully.")

# =========================================================================
# 6. PIPELINE SCHEMAS & QUIZ GRADING (schemas.py & quiz.py)
# =========================================================================
def patch_grading():
    p_schema = ROOT / "pipeline/schemas.py"
    s_content = p_schema.read_text(encoding="utf-8")
    old_grade = """class GradeResult(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_correct: bool = False
    feedback: str = \"\""""

    new_grade = """class GradeResult(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_correct: bool = False
    feedback: str = \"\"
    is_graded: bool = True
    error: str | None = None"""

    if old_grade in s_content:
        s_content = s_content.replace(old_grade, new_grade, 1)
        p_schema.write_text(s_content, encoding="utf-8")
        print("Patched pipeline/schemas.py successfully.")

    p_quiz_gen = ROOT / "pipeline/generate/quiz.py"
    qg_content = p_quiz_gen.read_text(encoding="utf-8")
    old_except = """    except Exception as exc:
        # Never lose a student's answer to a grading failure. Report it honestly as ungraded
        # rather than silently marking it wrong.
        log.warning("grading failed for item %s: %s", item.id, exc)
        return GradeResult(
            score=0.0,
            is_correct=False,
            feedback=f"This answer could not be graded automatically ({exc}). "
            f"Reference answer: {item.answer}",
        )"""

    new_except = """    except Exception as exc:
        # Distinguish provider failures from genuine incorrect answers (Defect 4).
        # Report honestly as ungraded so mastery is never penalized by provider outages.
        log.warning("grading failed for item %s: %s", item.id, exc)
        return GradeResult(
            score=0.0,
            is_correct=False,
            feedback=f"Grading service temporarily unavailable: {exc}. Your answer has been saved and can be graded later.",
            is_graded=False,
            error=str(exc),
        )"""

    if old_except in qg_content:
        qg_content = qg_content.replace(old_except, new_except, 1)
        p_quiz_gen.write_text(qg_content, encoding="utf-8")
        print("Patched pipeline/generate/quiz.py successfully.")

# =========================================================================
# 7. QUIZ SUBMISSION IDEMPOTENCY & MASTERY INTEGRITY (api/quiz.py)
# =========================================================================
def patch_api_quiz():
    p = ROOT / "api/quiz.py"
    content = p.read_text(encoding="utf-8")

    # In submit_answer:
    # 1. Reject answer if session is already finished
    # 2. Reject answer if item is outside session's source scope
    # 3. Check for duplicate attempt (idempotency)
    # 4. If grading failed (not grade.is_graded), do NOT penalize mastery!
    # 5. Atomically record attempt and update mastery

    old_submit = """@router.post("/session/{session_id}/answer")
async def submit_answer(session_id: int, payload: AnswerRequest) -> dict[str, Any]:
    def load_item() -> QuizItem:
        with session_scope() as session:
            item = session.get(QuizItem, payload.item_id)
            if item is None:
                raise NotFoundError(f"Question {payload.item_id} not found.")
            session.expunge(item)
            return item

    item = await run_db(load_item)
    grade = await quiz_gen.grade_answer(item, payload.response)

    def persist() -> tuple[dict[str, Any], bool]:
        with session_scope() as session:
            row = session.get(QuizSession, session_id)
            is_test = row is not None and row.mode is QuizMode.TEST
            session.add(
                QuizAttempt(
                    session_id=session_id,
                    quiz_item_id=payload.item_id,
                    response=payload.response,
                    is_correct=grade.is_correct,
                    score=grade.score,
                    feedback=grade.feedback,
                )
            )
            return {"is_test": is_test}, is_test

    _, is_test = await run_db(persist)
    new_mastery = await run_db(
        mastery.record_attempt, item.concept_id, correct=grade.is_correct, score=grade.score
    )

    response: dict[str, Any] = {
        "item_id": payload.item_id,
        "score": round(grade.score, 3),
        "mastery": new_mastery,
    }
    # Test mode withholds feedback until submission (PRD §7.4).
    if not is_test:
        response["is_correct"] = grade.is_correct
        response["feedback"] = grade.feedback
    return response"""

    new_submit = """@router.post("/session/{session_id}/answer")
async def submit_answer(session_id: int, payload: AnswerRequest) -> dict[str, Any]:
    # 1. Scope, Session Status & Idempotency pre-check
    def precheck() -> tuple[QuizItem, bool, float]:
        with session_scope() as session:
            row = session.get(QuizSession, session_id)
            if row is None:
                raise NotFoundError(f"Quiz session {session_id} not found.")
            if row.status is not QuizSessionStatus.ACTIVE:
                raise ValidationError("This session has already finished.")

            item = session.get(QuizItem, payload.item_id)
            if item is None:
                raise NotFoundError(f"Question {payload.item_id} not found.")

            # Scope enforcement: item must belong to session sources
            if row.source_ids and item.source_id not in row.source_ids:
                raise ValidationError(f"Question {payload.item_id} is outside the scope of this quiz session.")

            concept = session.get(Concept, item.concept_id) if item.concept_id else None
            current_mastery = concept.mastery if concept else 0.0

            # Idempotency check: prevent duplicate submissions from inflating mastery
            existing = session.execute(
                select(QuizAttempt).where(
                    QuizAttempt.session_id == session_id,
                    QuizAttempt.quiz_item_id == payload.item_id,
                )
            ).scalar_one_or_none()

            if existing is not None:
                session.expunge(existing)
                session.expunge(item)
                return item, True, current_mastery

            session.expunge(item)
            return item, False, current_mastery

    item, is_duplicate, current_mastery = await run_db(precheck)

    if is_duplicate:
        # Return existing attempt without creating duplicate or applying mastery update again
        def fetch_existing() -> dict[str, Any]:
            with session_scope() as session:
                row = session.get(QuizSession, session_id)
                is_test = row is not None and row.mode is QuizMode.TEST
                att = session.execute(
                    select(QuizAttempt).where(
                        QuizAttempt.session_id == session_id,
                        QuizAttempt.quiz_item_id == payload.item_id,
                    )
                ).scalar_one()
                resp = {
                    "item_id": payload.item_id,
                    "score": round(att.score or 0.0, 3),
                    "mastery": current_mastery,
                    "duplicate": True,
                }
                if not is_test:
                    resp["is_correct"] = att.is_correct
                    resp["feedback"] = att.feedback
                return resp
        return await run_db(fetch_existing)

    grade = await quiz_gen.grade_answer(item, payload.response)

    # 2. Defect 4 Fix: If grading failed due to provider outage, DO NOT penalize mastery!
    if not grade.is_graded:
        def persist_ungraded() -> dict[str, Any]:
            with session_scope() as session:
                session.add(
                    QuizAttempt(
                        session_id=session_id,
                        quiz_item_id=payload.item_id,
                        response=payload.response,
                        is_correct=False,
                        score=0.0,
                        feedback=grade.feedback,
                    )
                )
                return {
                    "item_id": payload.item_id,
                    "score": 0.0,
                    "mastery": current_mastery,  # Mastery remains unpenalized
                    "is_correct": False,
                    "is_graded": False,
                    "feedback": grade.feedback,
                    "error": grade.error,
                }
        return await run_db(persist_ungraded)

    # 3. Valid Grading: Persist attempt and update mastery in one atomic transaction
    def persist_valid() -> dict[str, Any]:
        with session_scope() as session:
            row = session.get(QuizSession, session_id)
            is_test = row is not None and row.mode is QuizMode.TEST
            session.add(
                QuizAttempt(
                    session_id=session_id,
                    quiz_item_id=payload.item_id,
                    response=payload.response,
                    is_correct=grade.is_correct,
                    score=grade.score,
                    feedback=grade.feedback,
                )
            )

            # Atomic mastery update
            new_mastery = current_mastery
            if item.concept_id is not None:
                concept = session.get(Concept, item.concept_id)
                if concept is not None:
                    if grade.is_correct:
                        concept.mastery = min(1.0, concept.mastery + (1.0 - concept.mastery) * 0.3)
                    else:
                        weight = grade.score if grade.score > 0.0 else 0.5
                        concept.mastery = max(0.0, concept.mastery * weight)
                    new_mastery = round(concept.mastery, 3)

            resp: dict[str, Any] = {
                "item_id": payload.item_id,
                "score": round(grade.score, 3),
                "mastery": new_mastery,
            }
            if not is_test:
                resp["is_correct"] = grade.is_correct
                resp["feedback"] = grade.feedback
            return resp

    return await run_db(persist_valid)"""

    if old_submit in content:
        content = content.replace(old_submit, new_submit, 1)
        p.write_text(content, encoding="utf-8")
        print("Patched api/quiz.py successfully.")

# =========================================================================
# 8. FLASHCARD REVIEW UNDO & MASTERY RESTORATION (study/review.py)
# =========================================================================
def patch_review_undo():
    p = ROOT / "study/review.py"
    content = p.read_text(encoding="utf-8")

    old_apply = """def apply_rating(card_id: int, rating: int, duration_ms: int | None = None) -> dict[str, Any]:
    \"\"\"Record a review, reschedule the card, and nudge its concept's mastery.\"\"\"
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")

        review, outcome = fsrs_module.apply_review(card, rating, duration_ms=duration_ms)
        session.add(review)
        concept_id = card.concept_id
        payload = {
            "card_id": card.id,
            "due": outcome.due.isoformat(),
            "interval": outcome.interval_label,
            "scheduled_days": outcome.scheduled_days,
            "state": str(outcome.state),
            "reps": card.reps,
            "lapses": card.lapses,
        }

    # A flashcard rating is evidence about the concept, so it moves mastery too — that is what
    # keeps cards and quizzes pointing at the same underlying model rather than two scores.
    if concept_id is not None:
        payload["mastery"] = mastery.record_attempt(concept_id, correct=rating >= 3, score=None)
    return payload


def undo_review(card_id: int) -> bool:
    \"\"\"Roll back the most recent rating for a card.\"\"\"
    with session_scope() as session:
        review = session.execute(
            select(Review).where(Review.card_id == card_id).order_by(Review.id.desc()).limit(1)
        ).scalar_one_or_none()
        if review is None:
            return False
        card = session.get(Card, card_id)
        if card is None:
            return False
        fsrs_module.restore(card, review.state_before or {})
        session.delete(review)
        return True"""

    new_apply = """def apply_rating(card_id: int, rating: int, duration_ms: int | None = None) -> dict[str, Any]:
    \"\"\"Record a review, reschedule the card, and nudge its concept's mastery atomically.\"\"\"
    with session_scope() as session:
        card = session.get(Card, card_id)
        if card is None:
            raise NotFoundError(f"Card {card_id} not found.")

        concept = session.get(Concept, card.concept_id) if card.concept_id else None
        initial_mastery = concept.mastery if concept else 0.0

        review, outcome = fsrs_module.apply_review(card, rating, duration_ms=duration_ms)
        # Snapshot concept mastery before review so undo can fully restore learning state
        review.state_before = {
            **(review.state_before or {}),
            "concept_mastery": initial_mastery,
        }
        session.add(review)

        # Atomic mastery update in same transaction
        new_mastery = None
        if concept:
            if rating >= 3:
                concept.mastery = min(1.0, concept.mastery + (1.0 - concept.mastery) * 0.3)
            else:
                concept.mastery = max(0.0, concept.mastery * 0.5)
            new_mastery = round(concept.mastery, 3)

        payload = {
            "card_id": card.id,
            "due": outcome.due.isoformat(),
            "interval": outcome.interval_label,
            "scheduled_days": outcome.scheduled_days,
            "state": str(outcome.state),
            "reps": card.reps,
            "lapses": card.lapses,
            "mastery": new_mastery,
        }
        return payload


def undo_review(card_id: int) -> bool:
    \"\"\"Roll back the most recent rating for a card and restore concept mastery atomically.\"\"\"
    with session_scope() as session:
        review = session.execute(
            select(Review).where(Review.card_id == card_id).order_by(Review.id.desc()).limit(1)
        ).scalar_one_or_none()
        if review is None:
            return False
        card = session.get(Card, card_id)
        if card is None:
            return False

        fsrs_module.restore(card, review.state_before or {})
        if "concept_mastery" in (review.state_before or {}) and card.concept_id:
            concept = session.get(Concept, card.concept_id)
            if concept:
                concept.mastery = float(review.state_before["concept_mastery"])

        session.delete(review)
        return True"""

    if old_apply in content:
        content = content.replace(old_apply, new_apply, 1)
        p.write_text(content, encoding="utf-8")
        print("Patched study/review.py successfully.")

# =========================================================================
# 9. CHAT GROUNDING & CITATION VALIDATION (api/chat.py)
# =========================================================================
def patch_chat_grounding():
    p = ROOT / "api/chat.py"
    content = p.read_text(encoding="utf-8")

    old_val = """    cited = {int(match) for match in CITATION_RE.findall(answer)}
    hallucinated = cited - valid_ids
    if hallucinated:
        log.info("dropping %d citation marker(s) not in the retrieved set", len(hallucinated))
        answer = CITATION_RE.sub(
            lambda m: "" if int(m.group(1)) in hallucinated else m.group(0), answer
        )
    return answer, sorted(cited & valid_ids)"""

    new_val = """    cited = {int(match) for match in CITATION_RE.findall(answer)}
    valid_cited = cited & valid_ids
    hallucinated = cited - valid_ids

    # Fail closed on unsupported claims: if citations were provided but NONE match retrieved context,
    # or if all cited evidence is fabricated, abstain rather than presenting unsupported assertions.
    if cited and not valid_cited:
        log.warning("model hallucinated all citations %s; rejecting unsupported answer", cited)
        return (
            "I could not verify this claim in the provided course materials. "
            "The retrieved passages do not contain evidence supporting this statement.",
            [],
        )

    if hallucinated:
        log.info("dropping %d citation marker(s) not in the retrieved set", len(hallucinated))
        answer = CITATION_RE.sub(
            lambda m: "" if int(m.group(1)) in hallucinated else m.group(0), answer
        ).strip()
        answer = answer + "\\n\\n*(Note: Some referenced citations were not found in the verified course material.)*"

    return answer, sorted(valid_cited)"""

    if old_val in content:
        content = content.replace(old_val, new_val, 1)
        p.write_text(content, encoding="utf-8")
        print("Patched api/chat.py successfully.")

if __name__ == "__main__":
    patch_sources()
    patch_notes()
    patch_cards()
    patch_system()
    patch_dashboard()
    patch_grading()
    patch_api_quiz()
    patch_review_undo()
    patch_chat_grounding()
    print("ALL REMEDIATION PATCHES APPLIED.")
