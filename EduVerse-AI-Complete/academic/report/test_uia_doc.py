import ctypes
import uiautomation as auto
import win32gui

user32 = ctypes.windll.user32
hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
if hdesk:
    user32.SetThreadDesktop(hdesk)

hwnd = 67008
win = auto.ControlFromHandle(hwnd)
print("Brave window:", win.Name)

# Find DocumentControl
doc = win.DocumentControl(searchDepth=10)
if doc.Exists(3):
    print("Found DocumentControl:", doc.Name)
    # Search for "New Project"
    btn = doc.ButtonControl(searchDepth=10, SubName="New Project")
    if btn.Exists(2):
        print("FOUND NEW PROJECT BUTTON!", btn.Name, btn.BoundingRectangle)
        # Click it!
        btn.Click()
        print("Clicked New Project button!")
    else:
        print("Button 'New Project' not found directly. Listing all buttons in document:")
        for b in doc.GetChildren():
            print("  Child:", b.ControlTypeName, b.Name)
else:
    print("DocumentControl not found in 3s.")
