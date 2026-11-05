import asyncio
import sqlite3
import os

# Instruct pytest not to treat this standalone verification script as a unit test
__test__ = False

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

async def run_e2e_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("[E2E] Navigating to http://127.0.0.1:8000/ ...")
        await page.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded")

        # 1. Verify Page Loaded & Title
        title = await page.title()
        print(f"[E2E] Page title: {title}")
        assert "EduVerse AI" in title

        # Verify clean right panel (hologram removed per targeted cleanup)
        assert await page.locator("#avatar-canvas").count() == 0, "Avatar canvas must be removed!"
        assert await page.locator("#avatar-state-text").count() == 0, "Avatar state text must be removed!"
        assert await page.locator(".suggested-prompts").count() == 0, "Suggestion prompt chips must be removed!"
        await page.wait_for_selector("#quiz-count-select", state="visible")
        print("[E2E] Clean right panel verified (hologram & topic chips cleanly removed).")

        # 2. Check Active Document Capsule
        doc_capsule = page.locator("#active-doc-name")
        doc_text = await doc_capsule.inner_text()
        print(f"[E2E] Header document status: '{doc_text}'")

        # If no document loaded yet, click Load Sample Notes
        if "No study document loaded" in doc_text:
            print("[E2E] Clicking 'Load Verified ML Syllabus Notes' button...")
            sample_btn = page.locator(".btn-sample-load")
            await sample_btn.click()
            await page.wait_for_selector("#stat-filename", state="visible", timeout=15000)

        active_file = await page.locator("#stat-filename").inner_text()
        doc_text = await doc_capsule.inner_text()
        print(f"[E2E] Active study document loaded: {active_file} ({doc_text})")

        # 3. Test Tutor Query
        chat_input = page.locator("#user-input")
        send_btn = page.locator("#send-btn")
        
        test_query = "What is the primary difference between supervised and unsupervised learning?"
        print(f"[E2E] Submitting tutor question: '{test_query}'")
        await chat_input.fill(test_query)
        await send_btn.click()

        # Wait for tutor response in chat
        print("[E2E] Waiting for syllabus-grounded tutor response...")
        await page.wait_for_selector(".msg.tutor .msg-bubble p", state="visible", timeout=30000)
        # Give a moment for text to render
        await page.wait_for_timeout(2000)
        tutor_bubbles = await page.locator(".msg.tutor .msg-bubble").all()
        last_tutor_msg = await tutor_bubbles[-1].inner_text()
        print(f"[E2E] Tutor response received ({len(last_tutor_msg)} chars):\n{last_tutor_msg[:140]}...\n")

        # 4. Test Concept Simplification
        print("[E2E] Testing Simplify Concept action...")
        await chat_input.fill("Gradient Descent")
        simplify_btn = page.locator("#simplify-btn")
        await simplify_btn.click()
        await page.wait_for_selector("#simplify-btn:not([disabled])", timeout=45000)
        await page.wait_for_timeout(1000)
        print("[E2E] Simplify response rendered.")

        # 5. Generate Active Recall Quiz
        print("[E2E] Generating active recall quiz from syllabus...")
        gen_quiz_btn = page.locator("#gen-quiz-btn")
        await gen_quiz_btn.click()

        # Wait for questions to appear
        await page.wait_for_selector(".question-card", state="visible", timeout=60000)
        q_cards = await page.locator(".question-card").all()
        print(f"[E2E] Rendered {len(q_cards)} quiz questions.")

        # 6. Select Answers
        for q_idx in range(len(q_cards)):
            # Pick first option for each question
            first_radio = page.locator(f"input[name^='q-']").nth(q_idx * 4)
            await first_radio.check(force=True)
            print(f"[E2E] Answered Question {q_idx + 1}")

        # 7. Submit Quiz & Verify SQLite Evaluation
        submit_btn = page.locator("#submit-quiz-btn")
        await submit_btn.wait_for(state="visible", timeout=5000)
        btn_text = await submit_btn.inner_text()
        print(f"[E2E] Submit button state: '{btn_text}'")
        await submit_btn.click()

        # Wait for evaluation score banner
        await page.wait_for_selector("#quiz-score-container .quiz-score-banner", state="visible", timeout=20000)
        score_banner = page.locator("#quiz-score-container .quiz-score-banner")
        score_text = await score_banner.inner_text()
        print(f"\n[E2E] Evaluation Score Banner:\n{score_text}\n")

        # 8. Capture Full-Stack Screenshot
        os.makedirs("EduVerse_AI_Project_Report/images", exist_ok=True)
        screenshot_path = "EduVerse_AI_Project_Report/images/actual_fullstack_workspace.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"[E2E] Screenshot saved to: {screenshot_path}")

        await browser.close()

    # 9. Verify Directly from SQLite Database
    conn = sqlite3.connect("data/eduverse.db")
    cur = conn.cursor()
    docs_count = cur.execute("SELECT count(*) FROM documents").fetchone()[0]
    quiz_count = cur.execute("SELECT count(*) FROM quizzes").fetchone()[0]
    latest_eval = cur.execute("""
        SELECT eval_id, quiz_id, score_percentage, correct_count, total_questions, passed, evaluated_at 
        FROM quiz_evaluations 
        ORDER BY rowid DESC LIMIT 1
    """).fetchone()
    conn.close()

    print("--- SQLITE3 DATABASE CONFIRMATION (data/eduverse.db) ---")
    print(f"Total Documents in SQLite: {docs_count}")
    print(f"Total Quizzes in SQLite: {quiz_count}")
    print(f"Latest Evaluation Record: ID={latest_eval[0]}, Score={latest_eval[2]}%, Correct={latest_eval[3]}/{latest_eval[4]}, Passed={bool(latest_eval[5])}, Time={latest_eval[6]}")
    assert latest_eval is not None, "Evaluation must be saved to SQLite!"
    print("\n>>> FULL STACK VALIDATION COMPLETE: FRONTEND + BACKEND + DATABASE 100% OPERATIONAL <<<\n")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
