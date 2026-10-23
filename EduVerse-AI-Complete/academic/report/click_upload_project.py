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

# Click on Upload Project at (120, 275)
print("Clicking Upload Project at (120, 275)...")
pyautogui.click(120, 275)
time.sleep(2.0)

# Capture screenshot to see the upload modal
rect = win32gui.GetWindowRect(brave_hwnd)
x, y, r, b = rect
screenshot = pyautogui.screenshot(region=(x, y, r-x, b-y))
screenshot.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
print("Saved modal_screen.png")
