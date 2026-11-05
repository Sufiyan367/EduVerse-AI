import json
from pathlib import Path

path = Path(r"C:\Users\sufiy\AppData\Roaming\DBeaverData\workspace6\General\.dbeaver\data-sources.json")
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    conns = data.get("connections", {})
    print(f"Found DBeaver data-sources.json with {len(conns)} connections:")
    for cid, conf in conns.items():
        name = conf.get("name")
        cfg = conf.get("configuration", {})
        host = cfg.get("host")
        port = cfg.get("port")
        db = cfg.get("database")
        user = cfg.get("user")
        print(f"  [{cid}] {name} -> {user}@{host}:{port}/{db}")
else:
    print(f"File not found: {path}")
