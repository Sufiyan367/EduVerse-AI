import ctypes
import time
import win32gui
import win32con
import pyautogui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

# Find Brave HWND
brave_hwnd = 67008
if not win32gui.IsWindow(brave_hwnd):
    def cb(h, extra):
        if "brave" in win32gui.GetWindowText(h).lower():
            extra.append(h)
        return True
    res = []
    win32gui.EnumDesktopWindows(hdesk, cb, res)
    if res:
        brave_hwnd = res[0]

print("Target Brave HWND:", brave_hwnd)
win32gui.ShowWindow(brave_hwnd, win32con.SW_RESTORE)
win32gui.SetForegroundWindow(brave_hwnd)
time.sleep(1)

# Open new tab in Brave
print("Sending Ctrl+T to open new tab in Brave...")
pyautogui.hotkey('ctrl', 't')
time.sleep(1)

# Type URL
print("Typing Overleaf project URL...")
pyautogui.write('https://www.overleaf.com/project', interval=0.02)
time.sleep(0.5)
pyautogui.press('enter')
print("Navigating to Overleaf in Brave...")
time.sleep(5)

title = win32gui.GetWindowText(brave_hwnd)
print("Brave window title is now:", title)
