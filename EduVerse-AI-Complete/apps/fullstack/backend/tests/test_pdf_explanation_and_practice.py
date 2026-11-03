"""Regression tests for Document Intelligence, AI Explanations, Interactive Practice, and User Data Isolation."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from quicklearn.db.bootstrap import init_database
from quicklearn.db.session import session_scope
from quicklearn.db.models import (
    User, Source, Segment, Concept, Card, Review, QuizItem,
    QuizSession, QuizAttempt, ActivityLog, PracticeAttempt
)
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus, QuizItemType
from quicklearn.study.document_intelligence import (
    generate_grounded_explanation,
    generate_practice_challenges,
    evaluate_practice_attempt,
    _detect_subject,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_database()


@pytest.fixture
def test_users():
    with session_scope() as session:
        # Create user A
        u_a = session.execute(text("SELECT id, email, username FROM users WHERE email = 'student_a@eduverse.test'")).fetchone()
        if not u_a:
            session.execute(text("INSERT INTO users (email, username, hashed_password, created_at) VALUES ('student_a@eduverse.test', 'student_a', 'hash', datetime('now'))"))
        
        # Create user B
        u_b = session.execute(text("SELECT id, email, username FROM users WHERE email = 'student_b@eduverse.test'")).fetchone()
        if not u_b:
            session.execute(text("INSERT INTO users (email, username, hashed_password, created_at) VALUES ('student_b@eduverse.test', 'student_b', 'hash', datetime('now'))"))
        session.commit()

        user_a = session.execute(text("SELECT id, email, username FROM users WHERE email = 'student_a@eduverse.test'")).fetchone()
        user_b = session.execute(text("SELECT id, email, username FROM users WHERE email = 'student_b@eduverse.test'")).fetchone()

        return (
            User(id=user_a[0], email=user_a[1], username=user_a[2]),
            User(id=user_b[0], email=user_b[1], username=user_b[2]),
        )


@pytest.fixture
def multi_subject_sources():
    """Create test sources for OS, Mathematics, Database, and Statistics."""
    sources = {}
    with session_scope() as session:
        # 1. Operating Systems Source
        s_os = Source(
            title="Operating Systems Principles: CPU Scheduling and Memory Management",
            origin=SourceOrigin.UPLOAD,
            kind=SourceKind.PDF,
            status=SourceStatus.READY,
            page_count=12,
        )
        session.add(s_os)
        session.flush()
        sources["os"] = s_os.id

        session.add(Segment(source_id=s_os.id, index=0, page_no=1, text="Round Robin scheduling allocates a fixed time quantum to each ready process to ensure bounded turnaround time."))
        session.add(Segment(source_id=s_os.id, index=1, page_no=2, text="Paging translates 32-bit virtual addresses into physical frames using a page table with 12 offset bits for 4KB pages."))

        # 2. Database Systems Source
        s_db = Source(
            title="Database Systems: Normalization and Relational Schemas",
            origin=SourceOrigin.UPLOAD,
            kind=SourceKind.PDF,
            status=SourceStatus.READY,
            page_count=8,
        )
        session.add(s_db)
        session.flush()
        sources["db"] = s_db.id

        session.add(Segment(source_id=s_db.id, index=0, page_no=1, text="A relation R is in Boyce-Codd Normal Form (BCNF) if every non-trivial functional dependency X -> Y has X as a superkey."))
        session.add(Segment(source_id=s_db.id, index=1, page_no=2, text="Lossless decomposition guarantees that natural join of decomposed relations reproduces the original relation without spurious tuples."))

        # 3. Mathematics Source
        s_math = Source(
            title="Linear Algebra: Characteristic Polynomials and Spectral Theory",
            origin=SourceOrigin.UPLOAD,
            kind=SourceKind.PDF,
            status=SourceStatus.READY,
            page_count=15,
        )
        session.add(s_math)
        session.flush()
        sources["math"] = s_math.id

        session.add(Segment(source_id=s_math.id, index=0, page_no=1, text="The eigenvalues of a linear transformation are the roots of the characteristic polynomial det(A - lambda * I) = 0."))
        session.add(Segment(source_id=s_math.id, index=1, page_no=2, text="Eigenvectors remain invariant in direction under matrix operator multiplication, scaling only by the eigenvalue scalar."))

        # 4. Statistics Source
        s_stat = Source(
            title="Statistical Inference: Hypothesis Testing and Sampling",
            origin=SourceOrigin.UPLOAD,
            kind=SourceKind.PDF,
            status=SourceStatus.READY,
            page_count=10,
        )
        session.add(s_stat)
        session.flush()
        sources["stat"] = s_stat.id

        session.add(Segment(source_id=s_stat.id, index=0, page_no=1, text="Student's t-test evaluates null hypothesis H0 against sample mean differences scaled by standard error s / sqrt(n)."))
        session.add(Segment(source_id=s_stat.id, index=1, page_no=2, text="Type I error alpha represents the probability of falsely rejecting a true null hypothesis."))

        session.commit()

    return sources


@pytest.mark.asyncio
async def test_explanation_across_document_types(multi_subject_sources, test_users):
    """Verify semantic relevance, subject definitions, and valid worked examples across 4 subject domains."""
    user_a, _ = test_users

    with session_scope() as session:
        # 1. Operating Systems
        source_os = session.get(Source, multi_subject_sources["os"])
        res_os = await generate_grounded_explanation(source_os, "Round Robin Scheduling", depth="worked_example", user=user_a)
        assert res_os["available"] is True
        assert "turnaround" in res_os["summary"].lower() or "quantum" in res_os["summary"].lower()
        assert len(res_os["definitions"]) >= 2
        # Verify valid technical worked example
        assert "Gantt" in res_os["worked_example"] or "Turnaround" in res_os["worked_example"]
        # Verify no generic traffic-control analogies
        assert "traffic control" not in res_os["mode_explanation"].lower() or "bank" in res_os["mode_explanation"].lower()
        assert len(res_os["citations"]) > 0

        # 2. Database Systems
        source_db = session.get(Source, multi_subject_sources["db"])
        res_db = await generate_grounded_explanation(source_db, "Boyce-Codd Normal Form BCNF", depth="principle", user=user_a)
        assert res_db["available"] is True
        assert any("superkey" in (d["term"] + " " + d["definition"]).lower() or "dependency" in (d["term"] + " " + d["definition"]).lower() for d in res_db["definitions"])
        assert "BCNF" in res_db["worked_example"] or "Decomposition" in res_db["worked_example"]

        # 3. Mathematics
        source_math = session.get(Source, multi_subject_sources["math"])
        res_math = await generate_grounded_explanation(source_math, "Eigenvalues and Characteristic Polynomial", depth="worked_example", user=user_a)
        assert res_math["available"] is True
        assert any("eigenvalue" in d["term"].lower() or "polynomial" in d["term"].lower() for d in res_math["definitions"])
        assert "det(A" in res_math["worked_example"] or "λ" in res_math["worked_example"] or "lambda" in res_math["worked_example"]

        # 4. Statistics
        source_stat = session.get(Source, multi_subject_sources["stat"])
        res_stat = await generate_grounded_explanation(source_stat, "Student's t-test hypothesis testing", depth="compare", user=user_a)
        assert res_stat["available"] is True
        assert any("null hypothesis" in d["term"].lower() or "error" in d["term"].lower() or "p-value" in d["term"].lower() for d in res_stat["definitions"])
        assert "Standard Error" in res_stat["worked_example"] or "t-statistic" in res_stat["worked_example"]


def test_interactive_practice_generation_and_evaluation(multi_subject_sources, test_users):
    """Verify challenge generation, user answer submission, rubric scoring, and attempt persistence."""
    user_a, _ = test_users

    with session_scope() as session:
        source_os = session.get(Source, multi_subject_sources["os"])
        segments = list(session.execute(text("SELECT id, text, page_no FROM segments WHERE source_id = :sid"), {"sid": source_os.id}))
        segs = [Segment(id=s[0], text=s[1], page_no=s[2], source_id=source_os.id) for s in segments]
        
        # 1. Challenge generation
        challenges = generate_practice_challenges(source_os, segs, [])
        assert len(challenges) >= 1
        ch = challenges[0]
        assert "problem_statement" in ch
        assert len(ch["hints"]) >= 3
        assert len(ch["expected_criteria"]) >= 2

        # 2. Incomplete student answer gets low score with clear missed points
        bad_res = evaluate_practice_attempt(
            challenge_id=ch["id"],
            question=ch["problem_statement"],
            student_answer="I don't know.",
            concept=ch["concept"],
            source=source_os,
            user=user_a,
        )
        assert bad_res.is_passing is False
        assert bad_res.score < 50
        assert len(bad_res.missed_points) > 0

        # 3. Thorough student answer passing criteria
        good_ans = (
            "Gantt chart order: P1 runs first for quantum Q=3, then P2 runs for Q=3, then P3 runs. "
            "Completion times: P3 completes at 5, P2 completes at 8, and P1 completes at 14. "
            "Average turnaround time = (14 + 8 + 5) / 3 = 9.0 time units."
        )
        good_res = evaluate_practice_attempt(
            challenge_id=ch["id"],
            question=ch["problem_statement"],
            student_answer=good_ans,
            concept=ch["concept"],
            source=source_os,
            user=user_a,
        )
        assert good_res.is_passing is True
        assert good_res.score >= 70
        assert len(good_res.strengths) >= 2
        assert "Model Solution" in good_res.step_by_step_solution

        # 4. Verify attempt is persisted in database for user_a
        persisted = session.execute(
            text("SELECT id, score, is_passing FROM practice_attempts WHERE user_id = :uid AND challenge_id = :cid ORDER BY id DESC"),
            {"uid": user_a.id, "cid": ch["id"]}
        ).fetchone()
        assert persisted is not None
        assert persisted[1] == good_res.score
        assert bool(persisted[2]) is True


def test_user_progress_data_isolation(multi_subject_sources, test_users):
    """Verify that User A's cards, quiz attempts, and passage reads do NOT leak to User B on the same source."""
    user_a, user_b = test_users
    source_id = multi_subject_sources["os"]

    with session_scope() as session:
        # Create a card for this source
        card = Card(source_id=source_id, front="What is time quantum?", back="Fixed CPU allocation slice.")
        session.add(card)
        session.flush()
        card_id = card.id

        # User A reviews this card twice
        rev1 = Review(card_id=card_id, rating=3, duration_ms=1200, user_id=user_a.id)
        rev2 = Review(card_id=card_id, rating=4, duration_ms=900, user_id=user_a.id)
        session.add_all([rev1, rev2])

        # User A creates a quiz session and attempts an item
        quiz_item = QuizItem(
            source_id=source_id,
            type=QuizItemType.MCQ,
            question="What is time quantum in Round Robin scheduling?",
            options=["Slice of CPU time", "RAM size", "Disk block", "Bus clock"],
            answer="Slice of CPU time",
        )
        session.add(quiz_item)
        session.flush()

        sess_a = QuizSession(user_id=user_a.id, mode="practice", source_ids=[source_id])
        session.add(sess_a)
        session.flush()

        att_a = QuizAttempt(session_id=sess_a.id, quiz_item_id=quiz_item.id, is_correct=True, score=1.0)
        session.add(att_a)

        # User A reads passage segment 1
        seg = session.execute(text("SELECT id FROM segments WHERE source_id = :sid LIMIT 1"), {"sid": source_id}).fetchone()
        seg_id = seg[0]
        act_a = ActivityLog(
            user_id=user_a.id,
            action="read_passage",
            entity_type="segment",
            entity_id=seg_id,
            title=f"Studied passage in {source_id}",
            details={"source_id": source_id},
        )
        session.add(act_a)

        session.commit()

    # Now verify workspace progress calculation for User A vs User B
    from quicklearn.api.sources import get_source_workspace

    # User A workspace progress
    ws_a = get_source_workspace(source_id=source_id, user=user_a)
    prog_a = ws_a["progress"]

    # Distinct cards reviewed by User A: exactly 1 (even though reviewed twice!)
    assert prog_a["cards_reviewed"] == 1
    assert prog_a["quiz_attempts"] == 1
    assert prog_a["quiz_correct"] == 1
    assert prog_a["quiz_accuracy_pct"] == 100.0
    assert prog_a["passages_read"] == 1
    assert prog_a["mastery_score"] > 0.0

    # User B workspace progress on the EXACT SAME SOURCE:
    ws_b = get_source_workspace(source_id=source_id, user=user_b)
    prog_b = ws_b["progress"]

    # User B has performed no reviews, attempts, or reads -> MUST BE ZERO!
    assert prog_b["cards_reviewed"] == 0
    assert prog_b["quiz_attempts"] == 0
    assert prog_b["quiz_correct"] == 0
    assert prog_b["quiz_accuracy_pct"] is None
    assert prog_b["passages_read"] == 0
    assert prog_b["mastery_score"] == 0.0, "User B must have exactly 0.0% mastery score with zero activity"
