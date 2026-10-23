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

# Click on the button at (494, 265)
print("Clicking at (494, 265)...")
pyautogui.click(494, 265)
time.sleep(1.0)

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
print("Dialog check 1:", res)

if not res:
    print("Pressing Space/Enter on focused element...")
    pyautogui.press('enter')
    time.sleep(1.5)
    res = []
    win32gui.EnumDesktopWindows(hdesk, cb, res)
    print("Dialog check 2:", res)

if res:
    dlg_hwnd = res[0][0]
    print(f"File dialog opened! HWND: {dlg_hwnd}")
    win32gui.SetForegroundWindow(dlg_hwnd)
    time.sleep(0.5)
    zip_path = r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.zip"
    pyautogui.write(zip_path, interval=0.01)
    time.sleep(0.5)
    pyautogui.press('enter')
    print("Submitted file path to dialog!")
