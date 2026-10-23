from playwright.sync_api import sync_playwright
import time

def capture_active_quiz():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://127.0.0.1:8000/", timeout=15000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Generate practice quiz
        page.locator("#btn-start-quiz").click()
        page.wait_for_selector(".quiz-card", timeout=15000)

        # Select option B for Q1 and option A for Q2
        cards = page.locator(".quiz-card")
        if cards.count() >= 2:
            cards.nth(0).locator(".quiz-option-card").nth(1).click()
            cards.nth(1).locator(".quiz-option-card").nth(0).click()

        # Capture Active Quiz screenshot
        shot_path = "EduVerse_AI_Project_Report/images/astra_active_quiz.png"
        page.screenshot(path=shot_path, full_page=False)
        print(f"Captured: {shot_path}")
        browser.close()

if __name__ == "__main__":
    capture_active_quiz()
