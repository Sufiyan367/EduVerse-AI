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

CHROMEDRIVER_PATH = r"C:\Users\sufiy\.cache\selenium\chromedriver\win64\155.0.8059.84\chromedriver.exe"
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USER_DATA = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data"
PROJECT_URL = "https://www.overleaf.com/project/6ad9c095e8f63a5d7432bd06"

# Kill any existing brave processes
subprocess.run(["taskkill", "/F", "/IM", "brave.exe"], capture_output=True)
time.sleep(1)

options = Options()
options.binary_location = BRAVE_PATH
options.add_argument(f"--user-data-dir={BRAVE_USER_DATA}")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")

service = Service(executable_path=CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

print(f"Opening project at: {PROJECT_URL}", flush=True)
driver.get(PROJECT_URL)

try:
    print("Waiting for Overleaf project editor and Recompile button...", flush=True)
    recompile_btn = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'recompile') or contains(., 'Recompile')]"))
    )
    print("Clicking Recompile...", flush=True)
    recompile_btn.click()
    print("Recompiling in Overleaf...", flush=True)
    time.sleep(10)
    print(">> PROJECT IS COMPILED AND VISIBLE ON SCREEN!", flush=True)
except Exception as e:
    print("Note during load:", e, flush=True)

print("Keeping browser window open indefinitely for user interaction...", flush=True)
# Keep running so browser stays open
while True:
    time.sleep(60)
