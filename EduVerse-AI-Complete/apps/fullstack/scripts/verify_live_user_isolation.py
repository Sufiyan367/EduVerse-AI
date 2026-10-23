"""Live End-to-End Multi-User Isolation Verification Script.

Tests the live EduVerse API at http://127.0.0.1:8080:
1. Registers/Logs in User 1 (Alice).
2. Registers/Logs in User 2 (Bob).
3. User 1 creates a private source.
4. User 2 attempts to read User 1's source -> must return 403 Forbidden.
5. User 2 attempts to update User 1's source -> must return 403 Forbidden.
6. User 2 attempts to delete User 1's source -> must return 403 Forbidden.
7. User 2 lists sources -> User 1's source must NOT appear.
8. User 1 schedules a revision session via /revision-planner/schedule.
9. User 2 lists revision sessions via /revision-planner/sessions -> User 1's session must NOT appear.
10. User 2 attempts to update User 1's revision session -> must return 403 Forbidden.
11. User 2 attempts to delete User 1's revision session -> must return 403 Forbidden.
12. User 1 can view, edit, and access her own content and revision session without restriction.
"""

import sys
import uuid
import requests

BASE_URL = "http://127.0.0.1:8080/api/v1"

def run_multiuser_isolation_audit():
    print("[1/5] Setting up live multi-user test identities...")
    tag = uuid.uuid4().hex[:6]
    alice_email = f"alice_{tag}@eduverse.test"
    bob_email = f"bob_{tag}@eduverse.test"
    alice_user = f"alice_{tag}"
    bob_user = f"bob_{tag}"
    password = "SecurePassword123!"

    # Register Alice
    r_alice = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": alice_email, "username": alice_user, "password": password, "full_name": "Alice Auditor"}
    )
    assert r_alice.status_code == 201, f"Failed Alice registration: {r_alice.text}"
    alice_data = r_alice.json()
    alice_token = alice_data["token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    print(f" -> Alice registered: ID={alice_data['user']['id']}, username={alice_user}")

    # Register Bob
    r_bob = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": bob_email, "username": bob_user, "password": password, "full_name": "Bob PenetrationTester"}
    )
    assert r_bob.status_code == 201, f"Failed Bob registration: {r_bob.text}"
    bob_data = r_bob.json()
    bob_token = bob_data["token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    print(f" -> Bob registered: ID={bob_data['user']['id']}, username={bob_user}")

    # Step 2: Alice creates a text source
    print("[2/5] Alice creates a confidential study source...")
    r_source = requests.post(
        f"{BASE_URL}/sources/text",
        headers=alice_headers,
        json={"title": f"Alice Private Notes {tag}", "content": "Confidential Study Guide on Advanced Distributed Systems and Raft Consensus."}
    )
    assert r_source.status_code == 200, f"Alice source creation failed: {r_source.text}"
    alice_source_id = r_source.json()["source_id"]
    print(f" -> Alice created source ID {alice_source_id}")

    # Step 3: Bob attempts unauthorized access on Alice's source
    print("[3/5] Verifying Bob cannot read, modify, or delete Alice's source...")
    # Bob tries to read Alice's source
    r_bob_read_src = requests.get(f"{BASE_URL}/sources/{alice_source_id}", headers=bob_headers)
    assert r_bob_read_src.status_code == 403, f"Bob could read Alice source! Code: {r_bob_read_src.status_code}"
    print(f" -> SUCCESS: Bob reading Alice source returned 403 Forbidden")

    # Bob tries to edit Alice's source
    r_bob_patch_src = requests.patch(
        f"{BASE_URL}/sources/{alice_source_id}",
        headers=bob_headers,
        json={"title": "Hacked Source Title"}
    )
    assert r_bob_patch_src.status_code == 403, f"Bob could edit Alice source! Code: {r_bob_patch_src.status_code}"
    print(f" -> SUCCESS: Bob editing Alice source returned 403 Forbidden")

    # Bob tries to delete Alice's source
    r_bob_del_src = requests.delete(f"{BASE_URL}/sources/{alice_source_id}", headers=bob_headers)
    assert r_bob_del_src.status_code == 403, f"Bob could delete Alice source! Code: {r_bob_del_src.status_code}"
    print(f" -> SUCCESS: Bob deleting Alice source returned 403 Forbidden")

    # Bob lists sources - Alice's source must NOT be in Bob's library
    r_bob_sources = requests.get(f"{BASE_URL}/sources", headers=bob_headers)
    assert r_bob_sources.status_code == 200
    bob_sources_list = r_bob_sources.json().get("sources", [])
    bob_source_ids = [s["id"] for s in bob_sources_list]
    assert alice_source_id not in bob_source_ids, f"Alice's source {alice_source_id} leaked into Bob's sources list!"
    print(f" -> SUCCESS: Alice source {alice_source_id} is completely hidden from Bob's library")

    # Step 4: Test Revision Session Isolation
    print("[4/5] Testing scheduled revision session isolation...")
    r_rev = requests.post(
        f"{BASE_URL}/revision-planner/schedule",
        headers=alice_headers,
        json={
            "topic": f"Alice Exam Prep Topic {tag}",
            "priority": "HIGH",
            "recommended_duration_min": 30,
            "reason": "Final review",
        }
    )
    assert r_rev.status_code == 201, f"Alice revision creation failed: {r_rev.text}"
    alice_rev_id = r_rev.json()["id"]
    print(f" -> Alice created revision session ID {alice_rev_id}")

    # Bob tries to update Alice's revision session
    r_bob_patch_rev = requests.patch(
        f"{BASE_URL}/revision-planner/sessions/{alice_rev_id}",
        headers=bob_headers,
        json={"status": "COMPLETED"}
    )
    assert r_bob_patch_rev.status_code == 403, f"Bob could update Alice revision! Code: {r_bob_patch_rev.status_code}"
    print(f" -> SUCCESS: Bob updating Alice revision returned 403 Forbidden")

    # Bob tries to delete Alice's revision session
    r_bob_del_rev = requests.delete(f"{BASE_URL}/revision-planner/sessions/{alice_rev_id}", headers=bob_headers)
    assert r_bob_del_rev.status_code == 403, f"Bob could delete Alice revision! Code: {r_bob_del_rev.status_code}"
    print(f" -> SUCCESS: Bob deleting Alice revision returned 403 Forbidden")

    # Bob lists revision sessions - Alice's session must NOT appear
    r_bob_revs = requests.get(f"{BASE_URL}/revision-planner/sessions", headers=bob_headers)
    assert r_bob_revs.status_code == 200
    bob_rev_ids = [s["id"] for s in r_bob_revs.json()]
    assert alice_rev_id not in bob_rev_ids, f"Alice revision session {alice_rev_id} leaked into Bob's schedule!"
    print(f" -> SUCCESS: Alice revision session {alice_rev_id} is completely hidden from Bob's schedule")

    # Step 5: Alice accesses and cleans up her own records
    print("[5/5] Verifying Alice retains full access to her own data...")
    r_alice_read = requests.get(f"{BASE_URL}/sources/{alice_source_id}", headers=alice_headers)
    assert r_alice_read.status_code == 200
    assert r_alice_read.json()["source"]["title"] == f"Alice Private Notes {tag}"

    r_alice_patch = requests.patch(
        f"{BASE_URL}/sources/{alice_source_id}",
        headers=alice_headers,
        json={"title": f"Alice Renamed Source {tag}"}
    )
    assert r_alice_patch.status_code == 200
    assert r_alice_patch.json()["title"] == f"Alice Renamed Source {tag}"

    r_alice_upd_rev = requests.patch(
        f"{BASE_URL}/revision-planner/sessions/{alice_rev_id}",
        headers=alice_headers,
        json={"status": "COMPLETED", "notes": "Completed high priority review"}
    )
    assert r_alice_upd_rev.status_code == 200
    assert r_alice_upd_rev.json()["status"] == "COMPLETED"

    r_alice_del_rev = requests.delete(f"{BASE_URL}/revision-planner/sessions/{alice_rev_id}", headers=alice_headers)
    assert r_alice_del_rev.status_code == 200
    print(f" -> SUCCESS: Alice successfully accessed, edited, and cleaned up her own records")

    print("\n=======================================================")
    print(" ALL MULTI-USER ISOLATION TESTS PASSED ON LIVE SERVER! ")
    print("=======================================================")

if __name__ == "__main__":
    try:
        run_multiuser_isolation_audit()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
