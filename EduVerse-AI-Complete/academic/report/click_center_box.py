import ctypes
import time
import win32gui
import pyautogui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

hwnd = 67008
win32gui.SetForegroundWindow(hwnd)
time.sleep(0.5)

print("Clicking at center of upload box (500, 330)...")
pyautogui.click(500, 330)
time.sleep(1.5)

# Check if Open dialog appeared
res = []
def cb(h, extra):
    if win32gui.IsWindowVisible(h):
        c = win32gui.GetClassName(h)
        t = win32gui.GetWindowText(h)
        if c == '#32770' or 'open' in t.lower():
            extra.append((h, c, t))
    return True

win32gui.EnumDesktopWindows(hdesk, cb, res)
print("Visible dialogs:", res)

# Capture screenshot
rect = win32gui.GetWindowRect(hwnd)
x, y, r, b = rect
img = pyautogui.screenshot(region=(x, y, r-x, b-y))
img.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\after_click_330.png")
print("Saved after_click_330.png")
