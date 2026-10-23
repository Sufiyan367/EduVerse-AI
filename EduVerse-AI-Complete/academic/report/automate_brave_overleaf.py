import os
import sys
import time
import subprocess
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
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USER_DATA = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

print("=" * 60, flush=True)
print("EduVerse AI — Brave Overleaf Automation Engine", flush=True)
print("=" * 60, flush=True)

# 1. Close running Brave processes to release profile lock
print("Closing existing Brave processes to unlock profile...", flush=True)
subprocess.run(["taskkill", "/F", "/IM", "brave.exe"], capture_output=True)
time.sleep(2)

# 2. Configure Selenium ChromeOptions for Brave
options = Options()
options.binary_location = BRAVE_PATH
options.add_argument(f"--user-data-dir={BRAVE_USER_DATA}")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")

# Configure download preferences
options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
})

# Detach driver so browser stays open on desktop after script
options.add_experimental_option("detach", True)

print("Launching Brave with your active profile...", flush=True)
service = Service(executable_path=CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

try:
    print("Navigating to: https://www.overleaf.com/project", flush=True)
    driver.get("https://www.overleaf.com/project")
    time.sleep(4)
    print("Current URL:", driver.current_url, flush=True)

    # Check if logged in
    if "login" in driver.current_url.lower():
        print("[WARNING] Overleaf requires login. Please complete login in the opened Brave window.", flush=True)
        # Wait up to 3 minutes for user login
        for _ in range(36):
            time.sleep(5)
            if "/project" in driver.current_url.lower() and "login" not in driver.current_url.lower():
                print(">> Login detected!", flush=True)
                break
    
    print("Looking for 'New Project' button on Overleaf dashboard...", flush=True)
    new_proj_btn = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'New Project') or contains(., 'New project')]"))
    )
    new_proj_btn.click()
    print("Clicked 'New Project'.", flush=True)
    time.sleep(1)

    print("Locating 'Upload Project' trigger...", flush=True)
    upload_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Upload Project') or contains(., 'Upload project')] | //button[contains(., 'Upload Project')]"))
    )
    upload_btn.click()
    print("Clicked 'Upload Project'.", flush=True)
    time.sleep(1.5)

    print("Sending ZIP file to file input...", flush=True)
    file_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
    )
    file_input.send_keys(ZIP_FILE)
    print(f">> Uploaded ZIP archive: {ZIP_FILE}", flush=True)

    print("Waiting for Overleaf project editor to load...", flush=True)
    WebDriverWait(driver, 35).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]"))
    )
    print(">> Project Editor loaded successfully! URL:", driver.current_url, flush=True)
    time.sleep(3)

    print("Triggering Recompilation in Overleaf...", flush=True)
    recompile_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]")
    recompile_btn.click()
    print(">> Recompile button clicked! Compiling document in Overleaf...", flush=True)
    
    # Wait for recompile to finish
    time.sleep(12)
    print(">> Compilation completed in Overleaf! Leaving browser open for user download.", flush=True)

except Exception as e:
    print("Exception during automation:", e, flush=True)
    print("Current URL:", driver.current_url, flush=True)

print("Done. Brave remains open with project ready.", flush=True)
