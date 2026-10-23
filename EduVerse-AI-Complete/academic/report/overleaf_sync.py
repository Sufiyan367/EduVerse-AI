"""
Overleaf Automation Script for EduVerse AI Project Report
Launches a visible Chrome browser, navigates to Overleaf, waits for user login,
uploads EduVerse_AI_Project_Report.zip, compiles, and downloads the verified PDF.
"""
import os
import sys
import time
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report"
ZIP_FILE = os.path.join(BASE_DIR, "EduVerse_AI_Project_Report.zip")
TARGET_PDF = os.path.join(BASE_DIR, "EduVerse_AI_Project_Report_Overleaf.pdf")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "overleaf_download")
CHROMEDRIVER_PATH = r"C:\Users\sufiy\.cache\selenium\chromedriver\win64\155.0.8059.84\chromedriver.exe"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

chrome_options = Options()
# Set default download directory to DOWNLOAD_DIR
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
})

print("=" * 60, flush=True)
print("EduVerse AI — Overleaf Automation Engine", flush=True)
print("=" * 60, flush=True)
print("Launching visible Chrome browser window on your desktop...", flush=True)

try:
    service = Service(executable_path=CHROMEDRIVER_PATH) if os.path.exists(CHROMEDRIVER_PATH) else None
    driver = webdriver.Chrome(service=service, options=chrome_options) if service else webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    print("Navigating to: https://www.overleaf.com/project", flush=True)
    driver.get("https://www.overleaf.com/project")
    print("Navigated to: https://www.overleaf.com/project", flush=True)
    
    # Check if user needs to log in
    if "login" in driver.current_url.lower():
        print("\n[AUTHENTICATION REQUIRED]", flush=True)
        print("Please log in to Overleaf in the opened Chrome browser window.", flush=True)
        print("Waiting for login to complete (waiting up to 15 minutes)...", flush=True)
        
        # Poll until user logs in and lands on project dashboard
        logged_in = False
        for _ in range(180):
            time.sleep(5)
            if "/project" in driver.current_url.lower() and "login" not in driver.current_url.lower():
                logged_in = True
                print(">> Login detected successfully! Dashboard loaded.", flush=True)
                break
        
        if not logged_in:
            print("[TIMEOUT] Login was not completed within the timeout period.", flush=True)
            driver.quit()
            sys.exit(1)
    else:
        print(">> Already logged in! Dashboard active.")

    time.sleep(3)
    
    # Look for "New Project" button
    print("Locating 'New Project' upload trigger...")
    try:
        new_proj_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'New Project') or contains(., 'New project')]"))
        )
        new_proj_btn.click()
        time.sleep(1)
        
        # Click "Upload Project"
        upload_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Upload Project') or contains(., 'Upload project')] | //button[contains(., 'Upload Project')]"))
        )
        upload_btn.click()
        time.sleep(2)
        
        # Send zip file to file input
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        file_input.send_keys(ZIP_FILE)
        print(f"Uploaded ZIP package: {ZIP_FILE}")
        
        # Wait for project to load in editor
        print("Waiting for Overleaf project editor to initialize...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]"))
        )
        print("Project editor loaded successfully!")
        time.sleep(3)
        
        # Click Recompile
        print("Triggering compilation in Overleaf...")
        recompile_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]")
        recompile_btn.click()
        
        # Wait for compilation to finish (button stops showing spinning/loading state)
        print("Compiling document in Overleaf...")
        time.sleep(10)
        
        # Look for PDF download button
        download_pdf_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@aria-label, 'Download PDF') or contains(@title, 'Download PDF')] | //button[contains(@aria-label, 'Download PDF')]"))
        )
        download_pdf_btn.click()
        print("Clicked Download PDF button.")
        
        # Wait for file to download in DOWNLOAD_DIR
        time.sleep(5)
        downloaded_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".pdf")]
        if downloaded_files:
            src_pdf = os.path.join(DOWNLOAD_DIR, downloaded_files[0])
            shutil.copy2(src_pdf, TARGET_PDF)
            print(f"Successfully downloaded and saved: {TARGET_PDF}")
            
            # Verify page count
            import fitz
            doc = fitz.open(TARGET_PDF)
            print(f"Verified Overleaf PDF Page Count: {len(doc)} pages")
        else:
            print("Download triggered; checking browser download state...")
            
    except Exception as e:
        print("Encountered step exception during automation:", e)
        print("Current URL:", driver.current_url)

except Exception as err:
    print("Error initializing browser automation:", err)
