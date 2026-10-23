import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

CHROMEDRIVER_PATH = r"C:\Users\sufiy\.cache\selenium\chromedriver\win64\155.0.8059.84\chromedriver.exe"
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USER_DATA = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data"

options = Options()
options.binary_location = BRAVE_PATH
options.add_argument(f"--user-data-dir={BRAVE_USER_DATA}")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")
options.add_experimental_option("detach", True)

service = Service(executable_path=CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

try:
    driver.get("https://www.overleaf.com/project")
    time.sleep(3)
    
    # Click New Project
    new_btn = driver.find_element(By.XPATH, "//button[contains(., 'New Project') or contains(., 'New project')]")
    new_btn.click()
    time.sleep(1.5)
    
    # Find all links and buttons in the opened dropdown
    elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'dropdown') or contains(@class, 'menu')]//a | //div[contains(@class, 'dropdown') or contains(@class, 'menu')]//button | //ul//li//a | //ul//li//button")
    print(f"Found {len(elements)} dropdown elements:")
    for el in elements:
        txt = el.text.strip().replace('\n', ' ')
        href = el.get_attribute("href")
        print(f"  TAG: {el.tag_name}, TEXT: '{txt}', HREF: '{href}'")
        
except Exception as e:
    print("Error:", e)
