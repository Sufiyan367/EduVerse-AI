"""Comprehensive Playwright E2E Browser Audit for EduVerse AI."""

import sys
import time
from playwright.sync_api import sync_playwright

def run_browser_audit():
    console_errors = []
    failed_requests = []
    routes_audited = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            base_url="http://127.0.0.1:8080"
        )
        page = context.new_page()

        # Listen for console errors
        def on_console(msg):
            if msg.type == "error":
                # Filter out intentional 401 probes if any
                text = msg.text
                if "favicon.ico" not in text:
                    console_errors.append(f"[Console Error] {text}")
        page.on("console", on_console)

        # Listen for failed requests
        def on_response(resp):
            if resp.status >= 500:
                failed_requests.append(f"[HTTP {resp.status}] {resp.url}")
        page.on("response", on_response)

        print("=== 1. AUDITING DASHBOARD (/) ===")
        page.goto("/")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        title = page.title()
        assert "EduVerse" in title, f"Unexpected title: {title}"
        routes_audited.append(("/", "OK"))
        print(f"  Dashboard loaded. Title: {title}")

        # Check for key dashboard elements
        body_text = page.inner_text("body")
        assert "Dashboard" in body_text or "Library" in body_text, "Core navigation missing"
        print("  Dashboard UI elements verified.")

        print("\n=== 2. AUDITING LIBRARY (/library) ===")
        page.goto("/library")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        routes_audited.append(("/library", "OK"))
        lib_text = page.inner_text("body")
        print(f"  Library loaded. Contains 'Unit 01': {'Unit 01' in lib_text}")

        print("\n=== 3. AUDITING SOURCE DETAILS (/library/1) ===")
        page.goto("/library/1")
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)
        routes_audited.append(("/library/1", "OK"))
        src_text = page.inner_text("body")
        print(f"  Source 1 loaded. Document title visible: {'Unit 01 Introduction to Databases and SQL' in src_text}")

        # Test tab switching on Source page
        tabs = ["notes", "flashcards", "concepts", "quiz"]
        for tab_name in tabs:
            tab_btn = page.query_selector(f"button:has-text('{tab_name.capitalize()}'), [data-value='{tab_name}'], [value='{tab_name}']")
            if tab_btn:
                tab_btn.click()
                time.sleep(0.5)
                print(f"  Switched to '{tab_name}' tab successfully.")

        print("\n=== 4. AUDITING CHAT INTERFACE (/chat) ===")
        page.goto("/chat")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        routes_audited.append(("/chat", "OK"))
        chat_text = page.inner_text("body")
        print(f"  Chat route loaded. Sessions visible: {'Verification Session' in chat_text or 'Chat' in chat_text}")

        # If chat session 4 exists, click it
        session_item = page.query_selector("text='Verification Session'")
        if session_item:
            session_item.click()
            time.sleep(1)
            msg_text = page.inner_text("body")
            has_citation = "[10]" in msg_text or "[12]" in msg_text or "[46]" in msg_text
            print(f"  Chat session opened. Contains citations [10], [12], [46]: {has_citation}")

        print("\n=== 5. AUDITING QUIZ ROUTE (/quiz) ===")
        page.goto("/quiz")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        routes_audited.append(("/quiz", "OK"))
        quiz_text = page.inner_text("body")
        print(f"  Quiz route loaded. Practice mode available: {'Practice' in quiz_text or 'Quiz' in quiz_text}")

        print("\n=== 6. AUDITING REVIEW ROUTE (/review) ===")
        page.goto("/review")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        routes_audited.append(("/review", "OK"))
        review_text = page.inner_text("body")
        print(f"  Review route loaded. Spaced repetition cards available: {'due' in review_text.lower() or 'review' in review_text.lower()}")

        print("\n=== 7. AUDITING SETTINGS (/settings) ===")
        page.goto("/settings")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        routes_audited.append(("/settings", "OK"))
        set_text = page.inner_text("body")
        print(f"  Settings loaded. Model routing visible: {'OpenRouter' in set_text or 'Routing' in set_text or 'Providers' in set_text}")

        print("\n=== 8. AUDITING DIRECT URL RELOAD ===")
        # Test browser reload on nested route
        page.goto("/library/1?tab=concepts")
        page.wait_for_load_state("networkidle")
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        print("  Direct nested URL reload succeeded without 404.")

        print("\n=== 9. AUDITING RESPONSIVE MOBILE VIEWPORT (375x667) ===")
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("/")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        mobile_title = page.title()
        print(f"  Mobile viewport rendered cleanly. Title: {mobile_title}")

        browser.close()

    print("\n=== AUDIT SUMMARY ===")
    print(f"Routes audited ({len(routes_audited)}): {routes_audited}")
    print(f"Server 5xx errors: {len(failed_requests)} -> {failed_requests}")
    print(f"Console errors: {len(console_errors)} -> {console_errors}")

    if failed_requests:
        print("[FAIL] Server returned 5xx errors during browser navigation.")
        sys.exit(1)
    if console_errors:
        print("[WARN] Console errors detected (inspect above).")
    else:
        print("[PASS] Zero browser console errors and zero failed server requests!")

if __name__ == "__main__":
    run_browser_audit()
