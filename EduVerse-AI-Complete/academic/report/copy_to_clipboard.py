import ctypes
from ctypes import wintypes
import os

class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]

def copy_file_to_clipboard(filepath):
    filepath = os.path.abspath(filepath)
    if not os.path.exists(filepath):
        print("File does not exist:", filepath)
        return False
    
    # Text with double null terminator
    files_data = filepath.encode('utf-16le') + b'\x00\x00\x00\x00'
    
    df = DROPFILES()
    df.pFiles = ctypes.sizeof(DROPFILES)
    df.pt = wintypes.POINT(0, 0)
    df.fNC = False
    df.fWide = True
    
    data = bytes(df) + files_data
    
    GMEM_MOVEABLE = 0x0002
    GMEM_ZEROINIT = 0x0040
    CF_HDROP = 15
    
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    
    hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    pGlobal = kernel32.GlobalLock(hGlobal)
    ctypes.memmove(pGlobal, data, len(data))
    kernel32.GlobalUnlock(hGlobal)
    
    user32.OpenClipboard(0)
    user32.EmptyClipboard()
    user32.SetClipboardData(CF_HDROP, hGlobal)
    user32.CloseClipboard()
    print("Successfully set CF_HDROP clipboard data for:", filepath)
    return True

zip_file = r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.zip"
copy_file_to_clipboard(zip_file)
