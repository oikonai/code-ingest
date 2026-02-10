"""
Unit tests for BatchProcessor: embedding → storage flow.

Run without Docker; uses mocked EmbeddingService and StorageManager.
Validates that when embedding fails (returns []), no storage is called and 0 chunks stored.

Run: make test-unit  (or python -m unittest tests.unit.test_batch_processor -v)

Note: The failure-path tests suppress batch_processor logging so "embedding failed" messages
don't appear in the test output (the tests still pass; those logs are from the code under test).
"""
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules.ingest.core.batch_processor import BatchProcessor

# Logger used by BatchProcessor (we suppress it during failure-path tests so output is clean)
_BATCH_LOGGER = "modules.ingest.core.batch_processor"


def make_chunk(content: str, item_name: str = "test") -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        item_name=item_name,
        metadata={"file_path": "test.rs", "language": "rust"},
    )


class TestBatchProcessorEmbeddingFailure(TestCase):
    """When embedding returns empty, storage must not be called and stored count is 0."""

    def test_embedding_empty_returns_zero_stored_and_no_storage_call(self):
        mock_embed = MagicMock()
        mock_embed.acquire_rate_limit.return_value.__enter__ = MagicMock(return_value=None)
        mock_embed.acquire_rate_limit.return_value.__exit__ = MagicMock(return_value=None)
        mock_embed.generate_embeddings.return_value = []  # simulate API failure

        mock_storage = MagicMock()

        processor = BatchProcessor(
            embedding_service=mock_embed,
            storage_manager=mock_storage,
            batch_size=10,
            max_workers=1,
            max_retries=2,
        )
        chunks = [make_chunk("fn foo() {}", f"chunk_{i}") for i in range(5)]
        collection_names = ["eco_code_rust"]
        language = "rust"

        # Suppress BatchProcessor logs so "embedding failed" messages don't look like test failure
        log = logging.getLogger(_BATCH_LOGGER)
        old_level = log.level
        log.setLevel(logging.CRITICAL)
        try:
            stored = processor.stream_chunks_to_storage(chunks, collection_names, language)
        finally:
            log.setLevel(old_level)

        self.assertEqual(stored, 0)
        mock_embed.generate_embeddings.assert_called()
        mock_storage.store_code_vectors_multi_collection.assert_not_called()

    def test_embedding_length_mismatch_returns_zero_stored_and_no_storage_call(self):
        mock_embed = MagicMock()
        mock_embed.acquire_rate_limit.return_value.__enter__ = MagicMock(return_value=None)
        mock_embed.acquire_rate_limit.return_value.__exit__ = MagicMock(return_value=None)
        mock_embed.generate_embeddings.return_value = [[0.1] * 4096]  # 1 vector for 2 chunks

        mock_storage = MagicMock()

        processor = BatchProcessor(
            embedding_service=mock_embed,
            storage_manager=mock_storage,
            batch_size=10,
            max_workers=1,
            max_retries=1,
        )
        chunks = [make_chunk("fn a() {}", "a"), make_chunk("fn b() {}", "b")]
        collection_names = ["eco_code_rust"]
        language = "rust"

        log = logging.getLogger(_BATCH_LOGGER)
        old_level = log.level
        log.setLevel(logging.CRITICAL)
        try:
            stored = processor.stream_chunks_to_storage(chunks, collection_names, language)
        finally:
            log.setLevel(old_level)

        self.assertEqual(stored, 0)
        mock_storage.store_code_vectors_multi_collection.assert_not_called()


class TestBatchProcessorEmbeddingSuccess(TestCase):
    """When embedding returns correct-length vectors, storage is called."""

    def test_embedding_success_calls_storage_and_returns_stored_count(self):
        mock_embed = MagicMock()
        mock_embed.acquire_rate_limit.return_value.__enter__ = MagicMock(return_value=None)
        mock_embed.acquire_rate_limit.return_value.__exit__ = MagicMock(return_value=None)
        mock_embed.generate_embeddings.return_value = [[0.1] * 4096, [0.2] * 4096]

        mock_storage = MagicMock()
        mock_storage.store_code_vectors_multi_collection.return_value = 2

        processor = BatchProcessor(
            embedding_service=mock_embed,
            storage_manager=mock_storage,
            batch_size=10,
            max_workers=1,
            max_retries=1,
        )
        chunks = [make_chunk("fn a() {}", "a"), make_chunk("fn b() {}", "b")]
        collection_names = ["eco_code_rust"]
        language = "rust"

        stored = processor.stream_chunks_to_storage(chunks, collection_names, language)

        self.assertEqual(stored, 2)
        mock_storage.store_code_vectors_multi_collection.assert_called_once()
        call_args = mock_storage.store_code_vectors_multi_collection.call_args
        self.assertEqual(len(call_args[0][0]), 2)
        self.assertEqual(len(call_args[0][1]), 2)
        self.assertEqual(call_args[0][2], ["eco_code_rust"])
        self.assertEqual(call_args[0][3], "rust")
