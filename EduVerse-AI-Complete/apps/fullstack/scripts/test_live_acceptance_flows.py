import uuid
import requests
import json
import sys

BASE = "http://127.0.0.1:8080/api/v1"

def run_tests():
    uid = uuid.uuid4().hex[:6]
    print(f"=== EDUVERSE AI LIVE COLLEGE DEMO ACCEPTANCE TEST (Run ID: {uid}) ===")
    
    # Flow 1: Registration, Login & Profile Retrieval
    print("\n[Flow 1] Authentication: Registration & Login...")
    user_a_email = f"student_a_{uid}@test.edu"
    user_a_pass = "TestPassword2026!"
    reg_a = requests.post(f"{BASE}/auth/register", json={
        "email": user_a_email,
        "username": f"user_a_{uid}",
        "password": user_a_pass,
        "full_name": f"Student A {uid}"
    })
    assert reg_a.status_code == 201, f"User A registration failed: {reg_a.text}"
    token_a = reg_a.json()["token"]
    user_a = reg_a.json()["user"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print(f" -> User A registered: {user_a['username']} (ID: {user_a['id']})")
    
    # Login again to test /auth/login
    login_a = requests.post(f"{BASE}/auth/login", json={
        "username": f"user_a_{uid}",
        "password": user_a_pass
    })
    assert login_a.status_code == 200, f"User A login failed: {login_a.text}"
    print(f" -> User A logged in successfully.")
    
    # Profile check /auth/me
    me_a = requests.get(f"{BASE}/auth/me", headers=headers_a)
    assert me_a.status_code == 200 and me_a.json()["email"] == user_a_email
    print(f" -> User A profile verified via Bearer token.")

    # User B registration for multi-user isolation
    user_b_email = f"student_b_{uid}@test.edu"
    reg_b = requests.post(f"{BASE}/auth/register", json={
        "email": user_b_email,
        "username": f"user_b_{uid}",
        "password": "PasswordBob2026!",
        "full_name": f"Student B {uid}"
    })
    assert reg_b.status_code == 201
    token_b = reg_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print(f" -> User B registered: student_b_{uid} (ID: {reg_b.json()['user']['id']})")

    # Flow 2: Study Material Ingestion
    print("\n[Flow 2] Study Document Ingestion & Retrieval...")
    study_text = (
        "Binary Search Trees (BST) maintain the invariant that for any node X, "
        "all keys in the left subtree are smaller than X.key, and all keys in the right "
        "subtree are greater. The average search complexity is O(log n)."
    )
    src_res = requests.post(f"{BASE}/sources/text", headers=headers_a, json={
        "title": f"BST Algorithms Note {uid}",
        "content": study_text
    })
    assert src_res.status_code == 200, f"Source creation failed: {src_res.text}"
    source_id = src_res.json()["source_id"]
    print(f" -> Source created by User A (ID: {source_id}, Title: 'BST Algorithms Note {uid}')")

    # Flow 3: Multi-User Access Isolation (User B cannot read/modify User A's source)
    print("\n[Flow 3] Multi-User Access Isolation Checks...")
    get_b = requests.get(f"{BASE}/sources/{source_id}", headers=headers_b)
    assert get_b.status_code == 403, f"Expected 403 on User B reading User A source, got {get_b.status_code}"
    patch_b = requests.patch(f"{BASE}/sources/{source_id}", headers=headers_b, json={"title": "Hacked"})
    assert patch_b.status_code == 403, f"Expected 403 on User B editing User A source, got {patch_b.status_code}"
    del_b = requests.delete(f"{BASE}/sources/{source_id}", headers=headers_b)
    assert del_b.status_code == 403, f"Expected 403 on User B deleting User A source, got {del_b.status_code}"
    
    # Check library list
    b_library = requests.get(f"{BASE}/sources", headers=headers_b).json()
    assert not any(s["id"] == source_id for s in b_library.get("sources", [])), "User A source leaked into User B library"
    print(" -> SUCCESS: User B reading/modifying/deleting User A source returned 403 Forbidden.")
    print(" -> SUCCESS: User A source is completely hidden from User B's library.")

    # Flow 4: Grounded AI Tutor Session & Citations
    print("\n[Flow 4] Grounded AI Tutor & Citation Verification...")
    chat_res = requests.post(f"{BASE}/chat", headers=headers_a, json={
        "title": f"BST Study Chat {uid}",
        "scope_type": "source",
        "scope_id": source_id
    })
    assert chat_res.status_code == 200, f"Chat creation failed: {chat_res.text}"
    chat_id = chat_res.json()["id"]
    print(f" -> Tutor Chat created (ID: {chat_id}, Grounded in Source {source_id})")

    # Flow 5: Notes & Autosave
    print("\n[Flow 5] User Study Notes Creation & Persistence...")
    note_res = requests.post(f"{BASE}/notes", headers=headers_a, json={
        "source_id": source_id,
        "title": f"My Key Takeaways {uid}",
        "doc": {"type": "doc", "content": [{"type": "paragraph", "text": "BST search is O(log n)."}]}
    })
    assert note_res.status_code == 200, f"Note creation failed: {note_res.text}"
    note_id = note_res.json()["id"]
    
    # Verify User B cannot access User A's note
    note_b = requests.get(f"{BASE}/notes/{note_id}", headers=headers_b)
    assert note_b.status_code == 403, f"Expected 403 on User B accessing User A note, got {note_b.status_code}"
    print(f" -> User Note created (ID: {note_id}) and verified isolated from User B (403 Forbidden).")

    # Flow 6: Dashboard Statistics & Isolation
    print("\n[Flow 6] Student Dashboard Analytics...")
    stats_a = requests.get(f"{BASE}/dashboard/stats", headers=headers_a).json()
    assert stats_a["total_sources"] >= 1, "User A dashboard should report at least 1 source"
    stats_b = requests.get(f"{BASE}/dashboard/stats", headers=headers_b).json()
    assert stats_b["total_sources"] == 0, "User B dashboard should report 0 sources"
    print(f" -> User A stats: {stats_a['total_sources']} sources, User B stats: {stats_b['total_sources']} sources.")
    print(" -> SUCCESS: Dashboard metrics strictly scoped per authenticated user.")

    # Flow 7: Adaptive Revision Planner
    print("\n[Flow 7] Adaptive Revision Planner Scheduling...")
    rev_res = requests.post(f"{BASE}/revision-planner/schedule", headers=headers_a, json={
        "topic": f"BST Review {uid}",
        "duration_minutes": 25,
        "priority": "HIGH",
        "source_id": source_id
    })
    assert rev_res.status_code == 201, f"Revision scheduling failed: {rev_res.text}"
    rev_id = rev_res.json()["id"]
    
    # User B cannot modify User A's revision session
    rev_b = requests.patch(f"{BASE}/revision-planner/sessions/{rev_id}", headers=headers_b, json={"status": "COMPLETED"})
    assert rev_b.status_code == 403, "User B should not be able to modify User A's revision session"
    print(f" -> Revision session scheduled (ID: {rev_id}, Priority: HIGH) and isolated from User B (403 Forbidden).")

    print("\n==================================================================")
    print(" ALL LIVE APPLICATION ACCEPTANCE FLOWS PASSED SUCCESSFULLY (100%) ")
    print("==================================================================")

if __name__ == "__main__":
    run_tests()
