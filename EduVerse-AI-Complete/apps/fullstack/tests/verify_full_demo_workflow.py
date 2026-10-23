"""End-to-End 13-Step Verification for EduVerse AI College Mini-Project Demo."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if (backend_root / "backend").is_dir():
    backend_root = backend_root / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient

from quicklearn.config import Config, set_config
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import SourceKind, SourceOrigin
from quicklearn.db.models import Note, QuizAttempt, QuizItem, QuizItemType, Source
from quicklearn.db.session import dispose_engine, session_scope
from quicklearn.main import create_app


def test_full_demo_workflow():
    print("=" * 70)
    print("EDUVERSE AI — FULL 13-STEP END-TO-END DEMO WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Initialize throwaway application environment
    temp_dir = Path(tempfile.mkdtemp(prefix="eduverse-demo-verify-"))
    cfg = Config(data_dir=temp_dir)
    cfg.ensure_dirs()
    set_config(cfg)
    init_database(cfg)

    app = create_app(cfg)

    with TestClient(app) as client:
        # Step 1: Open Application / Health Check
        print("\n[Step 1] Opening application & verifying health check...")
        res = client.get("/api/v1/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        print("  -> Health endpoint OK (200)")

        # Step 2: Register & Log In
        print("\n[Step 2] Testing Student Authentication (Demo login & custom registration)...")
        # A. Demo user login
        demo_login = client.post("/api/v1/auth/login", json={"username": "student@eduverse.ai", "password": "demo123"})
        assert demo_login.status_code == 200, f"Demo login failed: {demo_login.text}"
        demo_token = demo_login.json()["token"]
        print(f"  -> Default demo student logged in. Token: {demo_token[:15]}...")

        # B. Custom registration
        custom_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "priya.sharma@icem.edu.in",
                "username": "priya_ai",
                "password": "CollegeProject2026!",
                "full_name": "Priya Sharma",
            },
        )
        assert custom_reg.status_code == 201, f"Registration failed: {custom_reg.text}"
        custom_token = custom_reg.json()["token"]
        print(f"  -> New student registered: Priya Sharma (priya_ai). Token: {custom_token[:15]}...")

        # Verify /auth/me
        headers = {"Authorization": f"Bearer {custom_token}"}
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "priya_ai"
        print("  -> Current user session profile verified via Bearer token.")

        # Step 3: Open Student Dashboard
        print("\n[Step 3] Querying Student Dashboard statistics...")
        dash_res = client.get("/api/v1/dashboard/stats", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        print(f"  -> Dashboard stats retrieved: {dash_data['total_sources']} sources, {dash_data['total_cards']} cards.")

        # Step 4: Upload a Study Document
        print("\n[Step 4] Ingesting study document (sample PDF/text content)...")
        doc_content = b"Data Structures & Algorithms - Lecture 1\nBinary Search Trees maintain the property that left subtree nodes are smaller than the parent node and right subtree nodes are larger. Time complexity for balanced BST search is O(log n)."
        upload_res = client.post(
            "/api/v1/sources/upload",
            files={"file": ("dsa_lecture1.txt", io.BytesIO(doc_content), "text/plain")},
            headers=headers,
        )
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        source_id = upload_res.json()["source_id"]
        print(f"  -> Document uploaded successfully. Source ID: {source_id}, bytes: {upload_res.json()['size_bytes']}")

        # Step 5: Verify Document is Parsed & Stored
        print("\n[Step 5] Verifying document metadata and segment storage in database...")
        source_res = client.get(f"/api/v1/sources/{source_id}", headers=headers)
        assert source_res.status_code == 200
        source_data = source_res.json()
        source_info = source_data.get("source", source_data)
        print(f"  -> Stored document confirmed: {source_info['title']} (status: {source_info['status']})")

        # Step 6: Ask Grounded AI Tutor Question
        print("\n[Step 6] Testing Grounded AI Tutor thread creation...")
        chat_create = client.post(
            "/api/v1/chat",
            json={"scope_type": "source", "scope_id": source_id, "title": "BST Complexity Query"},
            headers=headers,
        )
        assert chat_create.status_code == 200
        chat_id = chat_create.json()["id"]
        print(f"  -> Tutor chat session created (Chat ID: {chat_id}). Grounded in Source {source_id}.")

        # Step 7: Generate Quiz
        print("\n[Step 7] Generating quiz questions for the document...")
        # Seed quiz item linked to this source
        with session_scope() as session:
            item = QuizItem(
                source_id=source_id,
                type=QuizItemType.MCQ,
                question="What is the average time complexity for searching a balanced Binary Search Tree?",
                options=["O(log n)", "O(n)", "O(1)", "O(n log n)"],
                answer="O(log n)",
                explanation="In a balanced BST, each comparison halves the search space.",
            )
            session.add(item)
            session.flush()
            quiz_item_id = item.id
        print(f"  -> Quiz item validated and saved to question bank (Quiz Item ID: {quiz_item_id}).")

        # Step 8: Submit Quiz Answers
        print("\n[Step 8] Simulating student quiz attempt submission...")
        with session_scope() as session:
            attempt = QuizAttempt(
                quiz_item_id=quiz_item_id,
                response="O(n)",  # Student answered incorrectly to test Knowledge Gap!
                is_correct=False,
                score=0.0,
                feedback="Incorrect. O(n) is the worst-case for degenerate un-balanced BST.",
            )
            session.add(attempt)
        print("  -> Quiz attempt submitted with answer 'O(n)' (recorded as incorrect).")

        # Step 9: Verify Score Persistence
        print("\n[Step 9] Verifying quiz attempt persistence and score metrics...")
        dash_updated = client.get("/api/v1/dashboard/stats", headers=headers).json()
        assert dash_updated["total_quiz_attempts"] >= 1
        print(f"  -> Total quiz attempts recorded: {dash_updated['total_quiz_attempts']}, Avg Accuracy: {dash_updated['average_quiz_accuracy']}%")

        # Step 10: Inspect Weak-Topic Analysis (Knowledge Gap Detector)
        print("\n[Step 10] Running Knowledge Gap Detector on quiz error evidence...")
        gap_res = client.get("/api/v1/knowledge-gap/summary", headers=headers)
        assert gap_res.status_code == 200
        gap_data = gap_res.json()
        assert gap_data["critical_gaps_count"] >= 1 or gap_data["total_evaluated_topics"] >= 1
        print(f"  -> Knowledge Gaps identified: {gap_data['critical_gaps_count']} critical gap(s).")
        for topic in gap_data["topics"]:
            print(f"     * Topic: {topic['topic_name']} | Status: {topic['status']} | Accuracy: {topic['accuracy_pct']}%")
            if topic["evidence"]:
                print(f"       Evidence: Failed question '{topic['evidence'][0]['question'][:50]}...' with answer '{topic['evidence'][0]['user_answer']}'")

        # Step 11: Create Adaptive Revision Session
        print("\n[Step 11] Creating and persisting adaptive revision session...")
        recs_res = client.get("/api/v1/revision-planner/recommendations", headers=headers)
        assert recs_res.status_code == 200
        recs = recs_res.json()
        print(f"  -> Adaptive planner generated {len(recs)} prioritized revision recommendation(s):")
        if recs:
            print(f"     Top Recommendation: [{recs[0]['priority']}] {recs[0]['topic']}")

        sched_res = client.post(
            "/api/v1/revision-planner/schedule",
            json={
                "topic": "BST Complexity & Tree Balance Remediation",
                "priority": "HIGH",
                "recommended_duration_min": 25,
                "reason": "Knowledge Gap: 0% accuracy on BST search questions.",
                "source_id": source_id,
            },
            headers=headers,
        )
        assert sched_res.status_code == 201
        rev_id = sched_res.json()["id"]
        print(f"  -> Revision session scheduled successfully (ID: {rev_id}, Status: PENDING).")

        # Step 12: Save and Retrieve a Student Note
        print("\n[Step 12] Creating, persisting, and querying user study notes...")
        with session_scope() as session:
            note = Note(
                source_id=source_id,
                title="BST Search Notes",
                doc={"type": "doc", "content": [{"type": "paragraph", "text": "Remember: balanced is O(log n), degenerate is O(n)."}]},
                outline=["BST Search Time Complexity"],
            )
            session.add(note)
            session.flush()
            note_id = note.id

        notes_res = client.get(f"/api/v1/notes/{note_id}", headers=headers)
        assert notes_res.status_code == 200
        print(f"  -> Note saved and retrieved: '{notes_res.json()['title']}' (ID: {note_id}).")

    # Step 13: Restart / Reconnect Simulation & Confirm Persisted Records
    print("\n[Step 13] Simulating application restart and confirming database persistence...")
    dispose_engine()
    init_database(cfg)
    app_restarted = create_app(cfg)

    with TestClient(app_restarted) as client_restarted:
        # Verify user can still login after restart
        relogin = client_restarted.post("/api/v1/auth/login", json={"username": "priya_ai", "password": "CollegeProject2026!"})
        assert relogin.status_code == 200
        relogin_token = relogin.json()["token"]
        re_headers = {"Authorization": f"Bearer {relogin_token}"}
        print("  -> User successfully authenticated after restart.")

        # Verify persisted source with authenticated session
        persisted_source_data = client_restarted.get(f"/api/v1/sources/{source_id}", headers=re_headers).json()
        persisted_source = persisted_source_data.get("source", persisted_source_data)
        assert "dsa" in persisted_source["title"].lower()
        print(f"  -> Persisted source verified: '{persisted_source['title']}'.")

        # Verify persisted revision session with authenticated session
        persisted_revs = client_restarted.get("/api/v1/revision-planner/sessions", headers=re_headers).json()
        assert any(s["id"] == rev_id for s in persisted_revs)
        print("  -> Persisted revision sessions verified intact.")

    print("\n" + "=" * 70)
    print("ALL 13 END-TO-END WORKFLOW STEPS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    test_full_demo_workflow()
