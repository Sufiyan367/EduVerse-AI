import ctypes
import uiautomation as auto

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

hwnd = 67008
win = auto.ControlFromHandle(hwnd)
doc = win.DocumentControl(searchDepth=10)

def search_controls(control, depth=0, max_depth=8):
    if depth > max_depth:
        return
    for c in control.GetChildren():
        name = c.Name or ""
        ctype = c.ControlTypeName or ""
        rect = c.BoundingRectangle
        if any(k in name.lower() for k in ["new project", "upload", "project", "blank", "recompile", "download"]):
            print(f"{'  '*depth}[{ctype}] '{name}' at {rect}")
            if "new project" in name.lower():
                print(f"--> CLICKING NEW PROJECT: {rect}")
                c.Click()
                return True
        if search_controls(c, depth + 1, max_depth):
            return True
    return False

print("Scanning document tree...")
found = search_controls(doc)
print("Search finished, found:", found)
