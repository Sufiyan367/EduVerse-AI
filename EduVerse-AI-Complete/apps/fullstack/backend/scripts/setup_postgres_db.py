"""Setup and initialize PostgreSQL role and database for EduVerse AI."""

import sys
import psycopg

ADMIN_URL = "host=127.0.0.1 port=5432 user=postgres password=Postgres@123 dbname=postgres"

def main():
    print("Connecting to PostgreSQL administrative database...")
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # 1. Role
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'eduverse_app';")
            if not cur.fetchone():
                cur.execute("CREATE ROLE eduverse_app WITH LOGIN PASSWORD 'EduVerse_App_2026_SecureKey!';")
                print("Role 'eduverse_app' created.")
            else:
                cur.execute("ALTER ROLE eduverse_app WITH LOGIN PASSWORD 'EduVerse_App_2026_SecureKey!';")
                print("Role 'eduverse_app' password updated.")

            # 2. Database
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'eduverse_db';")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE eduverse_db OWNER eduverse_app ENCODING 'UTF8';")
                print("Database 'eduverse_db' created.")
            else:
                cur.execute("ALTER DATABASE eduverse_db OWNER TO eduverse_app;")
                print("Database 'eduverse_db' exists; owner confirmed as eduverse_app.")

    # 3. Grant schema permissions
    db_admin_url = "host=127.0.0.1 port=5432 user=postgres password=Postgres@123 dbname=eduverse_db"
    with psycopg.connect(db_admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("GRANT ALL ON SCHEMA public TO eduverse_app;")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO eduverse_app;")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO eduverse_app;")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO eduverse_app;")
            print("Schema privileges granted on eduverse_db.")

    # 4. Verify login as eduverse_app
    app_url = "host=127.0.0.1 port=5432 user=eduverse_app password=EduVerse_App_2026_SecureKey! dbname=eduverse_db"
    with psycopg.connect(app_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_database(), current_user;")
            ver, db, u = cur.fetchone()
            print("VERIFIED CONNECTION AS APPLICATION ROLE:")
            print(f"  PostgreSQL Version: {ver}")
            print(f"  Current Database:   {db}")
            print(f"  Current User:       {u}")

if __name__ == "__main__":
    main()
