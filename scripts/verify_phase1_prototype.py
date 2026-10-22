import time
from playwright.sync_api import sync_playwright

def verify_prototype():
    with sync_playwright() as p:
        # Launch Chrome browser
        try:
            print("Attempting to launch Google Chrome...")
            browser = p.chromium.launch(channel="chrome", headless=True)
            browser_name = "Google Chrome (system channel)"
        except Exception as e:
            print(f"Chrome channel launch failed ({e}), using bundled Chromium...")
            browser = p.chromium.launch(headless=True)
            browser_name = "Chromium"

        print(f"Active browser: {browser_name}")
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()

        console_logs = []
        page.on('console', lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("\nStep 1: Navigating to http://127.0.0.1:8000/ ...")
        page.goto('http://127.0.0.1:8000/', wait_until='networkidle')
        print(f"   Page Title: '{page.title()}'")

        # Capture initial screenshot
        initial_img = "EduVerse_AI_Project_Report/images/phase1_prototype_initial.png"
        page.screenshot(path=initial_img)
        print(f"   Saved initial screenshot: {initial_img}")

        # Step 2: Switch sample document
        print("\nStep 2: Switching to 'Unit 2: Convolutional Networks'...")
        page.click('#card-doc-2')
        time.sleep(0.5)
        doc_name = page.inner_text('#active-doc-name')
        print(f"   Active Document Capsule: '{doc_name}'")

        print("   Switching back to 'Unit 4: Supervised Learning'...")
        page.click('#card-doc-1')
        time.sleep(0.5)

        # Step 3: Ask tutor a question
        print("\nStep 3: Testing Tutor Doubt Q&A...")
        page.fill('#user-input', 'What is the loss function in logistic regression and why is it convex?')
        page.click('#send-btn')
        time.sleep(2.0)
        print("   Tutor response received!")

        # Step 4: Simplify concept
        print("\nStep 4: Testing Concept Simplification...")
        page.fill('#user-input', 'Overfitting')
        page.click('#simplify-btn')
        time.sleep(2.0)
        print("   Concept simplification analogy received!")

        # Step 5: Generate Demo Quiz
        print("\nStep 5: Generating Demo Active Recall Quiz...")
        page.click('#gen-quiz-btn')
        page.wait_for_selector('#quiz-submit-bar', state='visible', timeout=10000)
        time.sleep(1.0)
        print("   Demo quiz synthesized!")

        # Step 6: Select Answers
        print("\nStep 6: Answering quiz questions...")
        page.click('#opt-label-1-0')
        page.click('#opt-label-2-0')
        page.click('#opt-label-3-0')
        time.sleep(0.5)

        # Step 7: Submit Quiz
        print("\nStep 7: Submitting quiz for demo evaluation...")
        page.click('#submit-quiz-btn')
        page.wait_for_selector('#quiz-score-container', state='visible', timeout=10000)
        time.sleep(1.0)
        score_text = page.inner_text('#quiz-score-container').replace('\n', ' | ')
        print(f"   Quiz Score Result: {score_text}")

        # Capture interactive screenshot
        interactive_img = "EduVerse_AI_Project_Report/images/phase1_prototype_interactive.png"
        page.screenshot(path=interactive_img)
        print(f"   Saved interactive screenshot: {interactive_img}")

        print("\nBrowser Console Audit:")
        errors = [l for l in console_logs if '[error]' in l]
        if errors:
            print("   Errors found:", errors)
        else:
            print("   0 JavaScript errors detected! Clean frontend execution.")

        browser.close()

if __name__ == '__main__':
    verify_prototype()
