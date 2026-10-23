import ctypes
import time
import win32gui
import pyautogui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

brave_hwnd = 67008
win32gui.SetForegroundWindow(brave_hwnd)
time.sleep(0.5)

# Click on New Project button at (120, 160)
print("Clicking New Project button at (120, 160)...")
pyautogui.click(120, 160)
time.sleep(1.5)

# Capture screenshot of the dropdown
rect = win32gui.GetWindowRect(brave_hwnd)
x, y, r, b = rect
screenshot = pyautogui.screenshot(region=(x, y, r-x, b-y))
screenshot.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\dropdown_screen.png")
print("Saved dropdown screenshot.")
