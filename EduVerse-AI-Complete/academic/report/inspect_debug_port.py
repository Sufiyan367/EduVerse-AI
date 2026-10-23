import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Connected to remote debugging! Found {len(data)} targets:")
        for item in data:
            print(f"  [{item.get('type')}] {item.get('title')} -> {item.get('url')}")
except Exception as e:
    print("Error connecting to port 9222:", e)
