import os
import shutil

brave_user_data = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data"
auto_user_data = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\AutomationUserData"

os.makedirs(auto_user_data, exist_ok=True)
os.makedirs(os.path.join(auto_user_data, "Default"), exist_ok=True)
os.makedirs(os.path.join(auto_user_data, "Default", "Network"), exist_ok=True)

# 1. Copy Local State (contains encryption key)
shutil.copy2(os.path.join(brave_user_data, "Local State"), os.path.join(auto_user_data, "Local State"))
print("Copied Local State.")

# 2. Copy Cookies
src_cookies = os.path.join(brave_user_data, "Default", "Network", "Cookies")
if os.path.exists(src_cookies):
    shutil.copy2(src_cookies, os.path.join(auto_user_data, "Default", "Network", "Cookies"))
    print("Copied Network/Cookies.")

# 3. Copy Preferences
src_prefs = os.path.join(brave_user_data, "Default", "Preferences")
if os.path.exists(src_prefs):
    shutil.copy2(src_prefs, os.path.join(auto_user_data, "Default", "Preferences"))
    print("Copied Preferences.")

print("Automation profile prepared successfully at:", auto_user_data)
