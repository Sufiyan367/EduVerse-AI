import os
import sqlite3
import shutil

def check_history(browser, history_path):
    if not os.path.exists(history_path):
        print(f"{browser} history not found at {history_path}")
        return
    tmp = f"temp_hist_{browser}.db"
    try:
        shutil.copy2(history_path, tmp)
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, last_visit_time FROM urls WHERE url LIKE '%overleaf%' ORDER BY last_visit_time DESC LIMIT 5")
        rows = cursor.fetchall()
        print(f"=== {browser} Overleaf History ===")
        for r in rows:
            print("  ", r[0], "-->", r[1])
        conn.close()
    except Exception as e:
        print(f"{browser} error:", e)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except:
                pass

chrome_hist = os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\User Data\Default\History"
brave_hist = os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\History"

check_history("Chrome", chrome_hist)
check_history("Brave", brave_hist)
