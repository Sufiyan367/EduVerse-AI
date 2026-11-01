import json
from pathlib import Path

path = Path(r"C:\Users\sufiy\AppData\Roaming\DBeaverData\workspace6\General\.dbeaver\data-sources.json")
data = json.loads(path.read_text(encoding="utf-8"))
for cid, conf in data.get("connections", {}).items():
    print(json.dumps({cid: conf}, indent=2))
