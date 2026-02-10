#!/usr/bin/env python3
"""
Verify SurrealDB connection and list all tables (collections).

Use this to confirm SurrealDB is reachable and see which tables exist
before or after ingestion. Requires SURREALDB_* in .env (or environment).

Usage (from repo root, with Docker SurrealDB on localhost:8000):
  python scripts/verify_surrealdb_collections.py
  make verify-surrealdb

Expect 0 tables until ingestion has run (docker compose up with ingest).
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv("SURREALDB_URL", "http://localhost:8000")
    ns = os.getenv("SURREALDB_NS", "code_ingest")
    db = os.getenv("SURREALDB_DB", "vectors")
    user = os.getenv("SURREALDB_USER", "root")
    password = os.getenv("SURREALDB_PASS", "root")

    print(f"Connecting to SurrealDB at {url} (ns={ns}, db={db}) ...")
    try:
        from modules.ingest.services.surrealdb_vector_client import SurrealDBVectorClient
        client = SurrealDBVectorClient()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Ensure SurrealDB is running (e.g. docker compose up surrealdb) and .env has SURREALDB_* set.")
        sys.exit(1)

    health = client.health_check()
    print("\n--- Health ---")
    print(json.dumps({k: v for k, v in health.items() if k != "collections"}, indent=2))
    collections = health.get("collections") or []
    print(f"\n--- Tables in database ({len(collections)} total) ---")
    if not collections:
        print("  (none yet — run full ingestion: docker compose up)")
    else:
        for name in sorted(collections):
            info = client.get_collection_info(name)
            count = info.get("vectors_count", 0) if info else 0
            print(f"  {name}: {count} vectors")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
