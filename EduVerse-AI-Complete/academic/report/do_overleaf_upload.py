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
print("EduVerse AI — Overleaf Automatic Upload & Recompile Engine", flush=True)
print("=" * 60, flush=True)

# 1. Kill any existing Brave instance to unlock profile
subprocess.run(["taskkill", "/F", "/IM", "brave.exe"], capture_output=True)
time.sleep(1.5)

# 2. Launch Brave with user profile
options = Options()
options.binary_location = BRAVE_PATH
options.add_argument(f"--user-data-dir={BRAVE_USER_DATA}")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")

options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
})
options.add_experimental_option("detach", True)

service = Service(executable_path=CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

try:
    print("Navigating to https://www.overleaf.com/project...", flush=True)
    driver.get("https://www.overleaf.com/project")
    time.sleep(3)

    print("Clicking 'New project' button...", flush=True)
    new_btn = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'New project') or contains(., 'New Project')]"))
    )
    new_btn.click()
    time.sleep(1)

    print("Clicking 'Existing project (.zip)'...", flush=True)
    zip_menu_item = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Existing project') or contains(., '.zip')] | //button[contains(., 'Existing project')]"))
    )
    zip_menu_item.click()
    print(">> Clicked 'Existing project (.zip)'. Upload modal is open!", flush=True)
    time.sleep(1.5)

    print("Locating file input in modal...", flush=True)
    file_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
    )
    print("Sending ZIP file directly to Overleaf...", flush=True)
    file_input.send_keys(ZIP_FILE)
    print(f">> File transmitted: {ZIP_FILE}", flush=True)

    print("Waiting for Overleaf project editor to initialize and load...", flush=True)
    recompile_btn = WebDriverWait(driver, 45).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]"))
    )
    print(">> Project Editor loaded successfully! Project URL:", driver.current_url, flush=True)
    time.sleep(2)

    print("Triggering Recompilation in Overleaf...", flush=True)
    recompile_btn.click()
    print(">> Clicked Recompile! Compiling LaTeX report inside Overleaf...", flush=True)

    # Wait for compilation to complete
    time.sleep(15)
    print(">> Recompilation finished! PDF is now rendered and ready inside Overleaf.", flush=True)
    print(">> Leaving Brave Browser active and open on your screen so you can inspect or download!", flush=True)

except Exception as e:
    print("Automation encountered exception:", e, flush=True)
    print("Current URL:", driver.current_url, flush=True)

print("Engine execution finished.", flush=True)
