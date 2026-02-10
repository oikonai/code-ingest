"""
Pytest fixtures for ingest module tests.

Use these to test batch processing and storage flow without Docker or live APIs.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Ensure modules are importable from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_chunk(content: str, item_name: str = "test") -> SimpleNamespace:
    """Minimal chunk-like object for BatchProcessor tests (has .content and .metadata)."""
    return SimpleNamespace(
        content=content,
        item_name=item_name,
        metadata={"file_path": "test.rs", "language": "rust"},
    )


@pytest.fixture
def mock_embedding_service():
    """EmbeddingService that returns controllable embeddings (no live API)."""
    service = MagicMock()
    service.acquire_rate_limit.return_value.__enter__ = MagicMock(return_value=None)
    service.acquire_rate_limit.return_value.__exit__ = MagicMock(return_value=None)
    return service


@pytest.fixture
def mock_storage_manager():
    """StorageManager that records store calls (no live DB)."""
    manager = MagicMock()
    manager.store_code_vectors_multi_collection.return_value = 0
    return manager
