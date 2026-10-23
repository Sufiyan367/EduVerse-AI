import ctypes
import time
import win32gui
import win32con
import pyautogui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

brave_hwnd = 67008
win32gui.SetForegroundWindow(brave_hwnd)
time.sleep(0.5)

# Click on Select a .zip file at (499, 269)
print("Clicking 'Select a .zip file' at (499, 269)...")
pyautogui.click(499, 269)
time.sleep(2.0)

# Check if Open File Dialog appeared
dialog_hwnd = 0
def cb(h, extra):
    if win32gui.IsWindowVisible(h):
        c = win32gui.GetClassName(h)
        t = win32gui.GetWindowText(h)
        if c == '#32770' or 'open' in t.lower():
            extra.append((h, t))
    return True

res = []
win32gui.EnumDesktopWindows(hdesk, cb, res)
print("Found dialogs:", res)

zip_path = r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.zip"

if res:
    dialog_hwnd = res[0][0]
    win32gui.SetForegroundWindow(dialog_hwnd)
    time.sleep(0.5)
    print("Typing ZIP file path into Open File Dialog...")
    pyautogui.write(zip_path, interval=0.01)
    time.sleep(0.5)
    pyautogui.press('enter')
    print("Pressed Enter to submit file.")
else:
    print("File dialog not detected by class; typing path directly via pyautogui...")
    pyautogui.write(zip_path, interval=0.01)
    time.sleep(0.5)
    pyautogui.press('enter')

# Wait for Overleaf to upload, extract, and load project
print("Waiting 12 seconds for Overleaf to load project editor...")
time.sleep(12)

# Check window title
title = win32gui.GetWindowText(brave_hwnd)
print("Brave window title after upload:", title)

# Take screenshot to verify editor
rect = win32gui.GetWindowRect(brave_hwnd)
x, y, r, b = rect
screenshot = pyautogui.screenshot(region=(x, y, r-x, b-y))
screenshot.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\overleaf_editor_screen.png")
print("Saved editor screenshot to: overleaf_editor_screen.png")
