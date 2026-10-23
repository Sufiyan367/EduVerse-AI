import os
import sys
import time
from playwright.sync_api import sync_playwright

def verify_astra():
    print("[1/6] Launching Playwright Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Test Desktop 1440x900
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        print("[2/6] Navigating to http://127.0.0.1:8000/ ...")
        page.goto("http://127.0.0.1:8000/", timeout=15000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # 1. Verify Header and SQLite
        brand = page.locator(".brand-name").text_content()
        print(f"  Brand title: {brand.strip()}")
        assert "EduVerse" in brand

        sqlite_pill = page.locator("#sqlite-status-pill").text_content()
        print(f"  Database indicator: {sqlite_pill.strip()}")
        assert "SQLite Connected" in sqlite_pill

        # 2. Verify Constellation SVG
        nodes = page.locator(".constellation-node")
        node_count = nodes.count()
        print(f"  Grounded constellation nodes rendered: {node_count}")
        assert node_count >= 3

        # Click a node
        nodes.first.click()
        time.sleep(0.5)
        inspector_title = page.locator("#inspector-title").text_content()
        print(f"  Selected node in inspector: {inspector_title}")
        assert len(inspector_title.strip()) > 0

        # Toggle to List View
        page.locator("#btn-view-list").click()
        time.sleep(0.5)
        list_items = page.locator("#constellation-list-view .doc-item")
        print(f"  Accessible list view items: {list_items.count()}")
        assert list_items.count() >= 3

        # Toggle back to Graph View
        page.locator("#btn-view-graph").click()
        time.sleep(0.5)

        # 3. Test Tutor Q&A
        print("[3/6] Testing Evidence-First Tutor...")
        tutor_input = page.locator("#tutor-input")
        tutor_input.fill("What is the difference between classification and regression?")
        page.locator("#btn-send-tutor").click()
        
        # Wait for tutor response
        page.wait_for_selector(".evidence-card", timeout=15000)
        print("  ✓ Tutor responded with verified syllabus evidence card!")

        # 4. Test Practice Quiz
        print("[4/6] Testing Document-Level Practice...")
        page.on("dialog", lambda dialog: dialog.accept())
        page.locator("#btn-start-quiz").click()
        page.wait_for_selector(".quiz-card", timeout=15000)
        quiz_cards = page.locator(".quiz-card")
        print(f"  Synthesized quiz cards: {quiz_cards.count()}")
        assert quiz_cards.count() >= 1

        # Select option A for all questions
        for card in quiz_cards.all():
            card.locator(".quiz-option-card").first.click()
            time.sleep(0.2)

        # Submit Quiz
        page.locator("#btn-submit-assessment").click()
        page.wait_for_selector(".assessment-score-banner", timeout=15000)
        score_val = page.locator(".score-big-number").text_content()
        print(f"  Assessment scored: {score_val}")

        # Check History Tab
        page.locator("#tab-history").click()
        time.sleep(0.5)
        history_items = page.locator(".history-item")
        print(f"  Persisted assessment history items in SQLite: {history_items.count()}")
        assert history_items.count() >= 1

        # Capture Desktop Screenshot
        os.makedirs("EduVerse_AI_Project_Report/images", exist_ok=True)
        desktop_shot = "EduVerse_AI_Project_Report/images/astra_desktop_workspace.png"
        page.screenshot(path=desktop_shot, full_page=False)
        print(f"[5/6] Desktop screenshot saved: {desktop_shot}")

        # Test Mobile Viewport (390 x 844)
        print("[6/6] Testing Mobile Viewport (390x844)...")
        mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
        mobile_page.goto("http://127.0.0.1:8000/", timeout=15000)
        mobile_page.wait_for_load_state("networkidle")
        time.sleep(1)

        mobile_nav = mobile_page.locator(".mobile-nav-bar")
        assert mobile_nav.is_visible()

        mobile_shot = "EduVerse_AI_Project_Report/images/astra_mobile_workspace.png"
        mobile_page.screenshot(path=mobile_shot, full_page=False)
        print(f"  Mobile screenshot saved: {mobile_shot}")

        browser.close()
        print("\n=== ALL ASTRA FRONTEND & E2E CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    verify_astra()
