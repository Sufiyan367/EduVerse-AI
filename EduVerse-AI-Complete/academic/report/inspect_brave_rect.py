import ctypes
import win32gui
from PIL import Image

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

# Find Brave HWND
brave_hwnd = 0
def cb(h, extra):
    if win32gui.IsWindowVisible(h):
        t = win32gui.GetWindowText(h)
        if "brave" in t.lower() or "overleaf" in t.lower():
            extra.append((h, t, win32gui.GetWindowRect(h)))
    return True

res = []
win32gui.EnumDesktopWindows(hdesk, cb, res)
print("Brave windows found:")
for h, t, rect in res:
    print(f"  HWND {h}: '{t}' at rect={rect}")

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\full_desktop_screen.png")
if res:
    h, t, rect = res[0]
    x, y, r, b = rect
    # Ensure within bounds
    x = max(0, x)
    y = max(0, y)
    r = min(img.width, r)
    b = min(img.height, b)
    if r > x and b > y:
        crop = img.crop((x, y, r, b))
        crop.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\current_brave_crop.png")
        print(f"Saved current_brave_crop.png, size: {crop.size}")
