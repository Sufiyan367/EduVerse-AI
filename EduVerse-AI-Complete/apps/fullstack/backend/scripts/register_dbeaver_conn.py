import json
import uuid
from pathlib import Path

path = Path(r"C:\Users\sufiy\AppData\Roaming\DBeaverData\workspace6\General\.dbeaver\data-sources.json")
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    conns = data.get("connections", {})

    eduverse_conn_id = "postgres-jdbc-eduverse-app-db"
    conns[eduverse_conn_id] = {
        "provider": "postgresql",
        "driver": "postgres-jdbc",
        "name": "EduVerse AI (eduverse_db)",
        "save-password": True,
        "configuration": {
            "host": "127.0.0.1",
            "port": "5432",
            "database": "eduverse_db",
            "url": "jdbc:postgresql://127.0.0.1:5432/eduverse_db",
            "user": "eduverse_app",
            "configurationType": "MANUAL",
            "type": "dev",
            "closeIdleConnection": True,
            "properties": {
                "connectTimeout": "20",
                "loginTimeout": "20",
                "escapeSyntaxCallMode": "callIfNoReturn",
            },
            "provider-properties": {
                "@dbeaver-show-non-default-db@": "true",
                "@dbeaver-chosen-role@": "",
                "@dbeaver-show-template-db@": "false",
                "@dbeaver-show-unavailable-db@": "false",
                "show-database-statistics": "true",
                "@dbeaver-read-all-data-types-db@": "true",
                "read-keys-with-columns": "true",
                "replace-legacy-timezone": "false",
                "@dbeaver-use-prepared-statements-db@": "false",
            },
            "auth-model": "native"
        }
    }

    data["connections"] = conns
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Registered 'EduVerse AI (eduverse_db)' in DBeaver workspace successfully!")
else:
    print("DBeaver workspace not found at:", path)
