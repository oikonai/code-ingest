#!/usr/bin/env python3
"""
Inspect SurrealDB namespace/database: list tables and record counts.

Uses SURREALDB_URL, SURREALDB_NS, SURREALDB_DB, SURREALDB_USER, SURREALDB_PASS
from environment (e.g. from .env or docker-compose). Run from repo root:

  python scripts/inspect_surrealdb.py

Or inside the ingest/mcp container (env already set):

  docker compose run --rm ingest python /app/scripts/inspect_surrealdb.py
"""

import os
import sys

# Add repo root so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

def main():
    base_url = os.getenv("SURREALDB_URL", "http://localhost:8000").rstrip("/")
    if "/rpc" not in base_url:
        base_url = f"{base_url}/rpc"
    url = base_url
    ns = os.getenv("SURREALDB_NS", "code_ingest")
    db = os.getenv("SURREALDB_DB", "vectors")
    user = os.getenv("SURREALDB_USER", "root")
    password = os.getenv("SURREALDB_PASS", "root")

    print(f"Connecting to {url} (ns={ns}, db={db})")
    print()

    try:
        from surrealdb import Surreal
        client = Surreal(url)
        client.signin({"username": user, "password": password})
        client.use(ns, db)

        # Raw INFO FOR DB (Python client may return dict keyed by index or list)
        result = client.query("INFO FOR DB;")
        print("Raw result type:", type(result))
        if result is not None:
            if isinstance(result, dict):
                print("Raw result keys:", list(result.keys())[:20])
            else:
                print("Raw result length:", len(result))
        # Python client returns the INFO FOR DB object directly as a dict with 'tables' key
        tables = []
        db_info = result if isinstance(result, dict) and "tables" in result else None
        if not db_info and result and isinstance(result, (list, tuple)) and len(result) > 0:
            db_info = result[0] if isinstance(result[0], dict) else None
        if not db_info and isinstance(result, dict):
            db_info = result.get(0) or result.get("result")
        if result:
            print("DB info keys:", list(db_info.keys()) if isinstance(db_info, dict) else type(db_info))
            if isinstance(db_info, dict) and "tables" in db_info:
                tbls = db_info["tables"]
                tables = list(tbls.keys()) if isinstance(tbls, dict) else []
                print("Tables (collections):", tables)
            else:
                print("No 'tables' in result. Result keys:", list(result.keys()) if isinstance(result, dict) else "n/a")
        else:
            print("Result is empty or None")
        print()

        # Count records per table
        for name in sorted(tables):
            try:
                count_result = client.query(f"SELECT count() FROM {name} GROUP ALL;")
                if count_result and len(count_result) > 0 and count_result[0]:
                    # count() returns [{ count: N }]
                    row = count_result[0]
                    if isinstance(row, dict) and "count" in row:
                        print(f"  {name}: {row['count']} records")
                    else:
                        print(f"  {name}: (raw) {row}")
                else:
                    print(f"  {name}: 0 or no result")
            except Exception as e:
                print(f"  {name}: error - {e}")

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
