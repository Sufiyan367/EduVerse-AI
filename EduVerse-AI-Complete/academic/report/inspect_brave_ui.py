import ctypes
import time
import win32gui
import uiautomation as auto

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

hwnd = win32gui.FindWindow("Chrome_WidgetWin_1", None)
print("FindWindow Chrome_WidgetWin_1:", hwnd)

# Let's inspect all Chrome_WidgetWin_1 windows
hwnds = []
def cb(h, extra):
    if win32gui.GetClassName(h) == "Chrome_WidgetWin_1":
        hwnds.append((h, win32gui.GetWindowText(h)))
    return True

win32gui.EnumDesktopWindows(hdesk, cb, 0)
for h, title in hwnds:
    print(f"  HWND {h}: {title}")
