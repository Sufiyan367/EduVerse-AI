import time
from playwright.sync_api import sync_playwright

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()

        console_logs = []
        page.on('console', lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("1. Navigating to http://127.0.0.1:8000 ...")
        page.goto('http://127.0.0.1:8000', wait_until='networkidle')
        print(f"   Page Title: '{page.title()}'")

        # Step 1: Initial screenshot
        page.screenshot(path='EduVerse_AI_Project_Report/images/actual_running_app.png')
        print("   Saved initial screenshot: EduVerse_AI_Project_Report/images/actual_running_app.png")

        # Step 2: Load sample document
        print("2. Clicking 'Load Verified ML Syllabus Sample Notes'...")
        page.click('text=Load Verified ML Syllabus Sample Notes')
        page.wait_for_selector('#doc-details-container', state='visible', timeout=10000)
        time.sleep(1)
        doc_name = page.inner_text('#active-doc-name')
        print(f"   Active Document: '{doc_name}'")

        # Step 3: Tutor Query
        print("3. Asking tutor question: 'What is deep learning and how does it relate to artificial intelligence?'...")
        page.fill('#user-input', 'What is deep learning and how does it relate to artificial intelligence?')
        page.click('#send-btn')
        time.sleep(3)

        # Step 4: Concept simplification
        print("4. Testing Simplify concept: 'Overfitting'...")
        page.fill('#user-input', 'Overfitting')
        page.click('#simplify-btn')
        time.sleep(3)

        # Step 5: Quiz Generation
        print("5. Clicking 'Generate Quiz'...")
        page.click('#gen-quiz-btn')
        page.wait_for_selector('#quiz-submit-bar', state='visible', timeout=15000)
        print("   Quiz generated!")

        # Step 6: Select answers
        print("6. Answering quiz questions...")
        page.click('#opt-label-1-0')
        page.click('#opt-label-2-0')
        page.click('#opt-label-3-0')
        time.sleep(0.5)

        # Step 7: Submit Quiz
        print("7. Submitting quiz for evaluation...")
        page.click('#submit-quiz-btn')
        page.wait_for_selector('#quiz-score-container', state='visible', timeout=10000)
        score_text = page.inner_text('#quiz-score-container')
        print(f"   Evaluation Score Banner: {score_text.replace(chr(10), ' | ')}")

        # Step 8: Capture interactive workspace screenshot
        time.sleep(1)
        page.screenshot(path='EduVerse_AI_Project_Report/images/actual_interactive_workspace.png')
        print("   Saved interactive screenshot: EduVerse_AI_Project_Report/images/actual_interactive_workspace.png")

        print("\nBrowser Console Output (filtered for warnings/errors):")
        warnings = [log for log in console_logs if '[error]' in log or '[warning]' in log]
        if warnings:
            for w in warnings:
                print(f"   {w}")
        else:
            print("   0 JavaScript errors, 0 warnings. Clean execution!")

        browser.close()

if __name__ == '__main__':
    run_verification()
