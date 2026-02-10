"""
Unit tests for SurrealDB vector client get_collections() response parsing.

The Python Surreal client returns INFO FOR DB as a single dict (not a list).
These tests verify we parse it correctly without a live SurrealDB.

Run: make test-unit  (or python -m unittest tests.unit.test_surrealdb_get_collections -v)
"""
import logging
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


class TestSurrealDBGetCollectionsParsing(TestCase):
    """Test get_collections() handles dict response from client.query('INFO FOR DB')."""

    def test_get_collections_when_result_is_dict_with_tables_key(self):
        from modules.ingest.services.surrealdb_vector_client import SurrealDBVectorClient

        mock_conn = MagicMock()
        mock_conn.query.return_value = {
            "accesses": {},
            "analyzers": {},
            "tables": {"eco_code_rust": "DEFINE TABLE ...", "eco_code_typescript": "DEFINE TABLE ..."},
            "users": {},
        }

        with patch.dict("os.environ", {"SURREALDB_URL": "http://localhost:8000"}):
            with patch("modules.ingest.services.surrealdb_vector_client.Surreal", return_value=mock_conn):
                client = SurrealDBVectorClient(embedding_size=4096)
                tables = client.get_collections()

        self.assertEqual(tables, ["eco_code_rust", "eco_code_typescript"])

    def test_get_collections_when_tables_empty(self):
        from modules.ingest.services.surrealdb_vector_client import SurrealDBVectorClient

        mock_conn = MagicMock()
        mock_conn.query.return_value = {"accesses": {}, "tables": {}, "users": {}}

        with patch.dict("os.environ", {"SURREALDB_URL": "http://localhost:8000"}):
            with patch("modules.ingest.services.surrealdb_vector_client.Surreal", return_value=mock_conn):
                log = logging.getLogger("modules.ingest.services.surrealdb_vector_client")
                old_level = log.level
                log.setLevel(logging.CRITICAL)
                try:
                    client = SurrealDBVectorClient(embedding_size=4096)
                    tables = client.get_collections()
                finally:
                    log.setLevel(old_level)

        self.assertEqual(tables, [])
