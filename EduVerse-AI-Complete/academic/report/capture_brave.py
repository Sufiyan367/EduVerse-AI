import ctypes
import win32gui
import pyautogui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

brave_hwnd = 67008
win32gui.SetForegroundWindow(brave_hwnd)
rect = win32gui.GetWindowRect(brave_hwnd)
print("Brave rect:", rect)

# Capture screenshot of Brave window
x, y, r, b = rect
w = r - x
h = b - y

screenshot = pyautogui.screenshot(region=(x, y, w, h))
out_path = r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_overleaf_screen.png"
screenshot.save(out_path)
print("Saved screenshot to:", out_path)
