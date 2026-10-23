import ctypes
import uiautomation as auto
import win32gui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

brave_hwnd = 67008
win = auto.ControlFromHandle(brave_hwnd)
print("Root control:", win.Name, win.ControlTypeName)

# Search for "New Project"
new_proj = win.ButtonControl(searchDepth=15, SubName="New Project")
if not new_proj.Exists(2):
    new_proj = win.MenuItemControl(searchDepth=15, SubName="New Project")
if not new_proj.Exists(1):
    new_proj = win.Control(searchDepth=15, Name="New Project")

if new_proj.Exists(2):
    print("Found 'New Project':", new_proj.Name, new_proj.BoundingRectangle)
else:
    print("Looking for all buttons/links in window...")
    buttons = win.GetChildren()
    for c in win.GetDescendants():
        if c.Name and any(k in c.Name.lower() for k in ["new project", "upload", "project", "new"]):
            print(f"  {c.ControlTypeName}: '{c.Name}' at {c.BoundingRectangle}")
