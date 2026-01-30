"""
Batch Processor for Parallel Streaming

Handles parallel batch processing with retry queue and permanent failure detection.
Following CLAUDE.md: <500 lines, single responsibility (batch processing only).
"""

import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Processes chunks in parallel batches with retry logic.

    Responsibilities:
    - Stream code chunks to storage with parallel processing
    - Stream documentation chunks to storage
    - Retry failed batches with permanent failure detection
    - Rate limiting via embedding service semaphore
    """

    def __init__(
        self,
        embedding_service,
        storage_manager,
        batch_size: int = 100,
        max_workers: int = 4,
        max_retries: int = 3
    ):
        """
        Initialize batch processor.

        Args:
            embedding_service: EmbeddingService instance
            storage_manager: StorageManager instance
            batch_size: Number of chunks per batch
            max_workers: Maximum parallel workers
            max_retries: Maximum retry attempts for failed batches
        """
        self.embedding_service = embedding_service
        self.storage_manager = storage_manager
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.max_retries = max_retries

        logger.info(f"⚙️ Batch processor initialized")
        logger.info(f"   - Batch size: {batch_size}")
        logger.info(f"   - Max workers: {max_workers}")
        logger.info(f"   - Max retries: {max_retries}")

    def stream_chunks_to_storage(
        self,
        chunks: List[Any],  # RustCodeChunk objects
        collection_names: List[str],
        language: str
    ) -> int:
        """
        Stream code chunks to storage with parallel processing and retry queue.
        Supports multi-collection storage (BY_LANGUAGE + BY_SERVICE + BY_CONCERN).

        Args:
            chunks: List of code chunk objects
            collection_names: List of target Qdrant collections
            language: Programming language

        Returns:
            Number of chunks successfully stored
        """
        if not chunks:
            return 0

        total_stored = 0
        failed_batches = []

        # Create batches with IDs for tracking
        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[i:i + self.batch_size]
            batch_id = i // self.batch_size + 1
            batches.append({
                'id': batch_id,
                'chunks': batch_chunks,
                'retry_count': 0
            })

        total_batches = len(batches)

        # Process batches with retry logic
        for retry_round in range(self.max_retries):
            if retry_round == 0:
                batches_to_process = batches
                logger.info(
                    f"📊 Processing {len(batches_to_process)} batches in parallel "
                    f"(attempt 1/{self.max_retries})"
                )
            else:
                batches_to_process = failed_batches
                logger.info(
                    f"🔄 Retrying {len(batches_to_process)} failed batches "
                    f"(attempt {retry_round + 1}/{self.max_retries})"
                )
                failed_batches = []

            if not batches_to_process:
                break

            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                batch_futures = {}

                for batch_info in batches_to_process:
                    task = executor.submit(
                        self._process_code_batch_parallel,
                        batch_info['chunks'],
                        collection_names,
                        language,
                        batch_info['id'],
                        total_batches
                    )
                    batch_futures[task] = batch_info

                # Collect results as they complete
                for task in as_completed(batch_futures):
                    batch_info = batch_futures[task]
                    try:
                        batch_stored = task.result()
                        if batch_stored > 0:
                            total_stored += batch_stored
                            if batch_info['retry_count'] > 0:
                                logger.info(f"✅ Batch {batch_info['id']}: {batch_stored} vectors stored (after {batch_info['retry_count'] + 1} attempts)")
                            else:
                                logger.info(f"✅ Batch {batch_info['id']}: {batch_stored} vectors stored")
                        else:
                            # Batch failed - retry up to max_retries (increased from 1)
                            if batch_info['retry_count'] < self.max_retries - 1:
                                batch_info['retry_count'] += 1
                                failed_batches.append(batch_info)
                                logger.warning(
                                    f"⚠️ Batch {batch_info['id']} failed (likely timeout), will retry "
                                    f"(attempt {batch_info['retry_count'] + 1}/{self.max_retries})"
                                )
                            else:
                                # Max retries exceeded, likely permanent failure (validation error)
                                logger.error(
                                    f"❌ Batch {batch_info['id']} permanently failed after {self.max_retries} attempts "
                                    f"(validation, dimension, or persistent timeout error)"
                                )
                    except Exception as e:
                        # Exception during batch processing - this is transient, retry
                        if batch_info['retry_count'] < self.max_retries - 1:
                            batch_info['retry_count'] += 1
                            failed_batches.append(batch_info)
                            logger.error(
                                f"❌ Batch {batch_info['id']} exception: {e} "
                                f"(retry {batch_info['retry_count'] + 1}/{self.max_retries})"
                            )
                        else:
                            logger.error(
                                f"❌ Batch {batch_info['id']} exception after max retries: {e}"
                            )

        # Final report
        if failed_batches:
            failed_count = sum(len(b['chunks']) for b in failed_batches)
            logger.error(
                f"❌ {len(failed_batches)} batches ({failed_count} chunks) "
                f"failed after {self.max_retries} attempts"
            )
            for batch in failed_batches:
                logger.error(f"   - Batch {batch['id']}: {len(batch['chunks'])} chunks lost")

        logger.info(
            f"✅ Parallel streaming complete: {total_stored}/{len(chunks)} "
            f"chunks stored in Qdrant"
        )
        return total_stored

    def _process_code_batch_parallel(
        self,
        batch_chunks: List[Any],
        collection_names: List[str],
        language: str,
        batch_id: int,
        total_batches: int
    ) -> int:
        """Process a single code batch in parallel with rate limiting."""
        # Acquire semaphore to limit concurrent Modal requests
        with self.embedding_service.acquire_rate_limit():
            collections_str = ', '.join(collection_names)
            logger.info(
                f"🔄 Parallel batch {batch_id}/{total_batches} ({len(batch_chunks)} chunks) "
                f"→ {collections_str}"
            )

            # Extract texts from chunks with size validation
            texts = []
            valid_chunks = []
            max_chars = 131_000  # Cloudflare AI Gateway limit: 131,072 chars

            for chunk in batch_chunks:
                content_len = len(chunk.content)
                if content_len > max_chars:
                    logger.warning(
                        f"⚠️  Skipping chunk {chunk.item_name} - exceeds {max_chars} chars "
                        f"(actual: {content_len:,} chars)"
                    )
                    continue
                texts.append(chunk.content)
                valid_chunks.append(chunk)

            if not texts:
                logger.error(f"❌ Batch {batch_id}: all chunks exceeded size limit")
                return 0

            # Generate embeddings for valid chunks only
            embeddings = self.embedding_service.generate_embeddings(texts)

            if not embeddings or len(embeddings) != len(valid_chunks):
                logger.error(f"❌ Parallel batch {batch_id} embedding failed")
                return 0

            # Store batch immediately in all target collections
            batch_stored = self.storage_manager.store_code_vectors_multi_collection(
                valid_chunks,
                embeddings,
                collection_names,
                language
            )

            skipped_count = len(batch_chunks) - len(valid_chunks)
            logger.info(
                f"💾 Parallel batch {batch_id}: {batch_stored}/{len(valid_chunks)} vectors stored "
                f"in {len(collection_names)} collection(s)"
                + (f" (skipped {skipped_count} oversized chunks)" if skipped_count > 0 else "")
            )
            return batch_stored

    def stream_docs_to_storage(
        self,
        doc_chunks: List[Dict[str, Any]],
        collection_names: List[str]
    ) -> int:
        """
        Stream documentation chunks to storage with parallel processing.
        Supports multi-collection storage.

        Args:
            doc_chunks: List of documentation chunk dictionaries
            collection_names: List of target Qdrant collections

        Returns:
            Number of chunks successfully stored
        """
        if not doc_chunks:
            return 0

        total_stored = 0
        failed_batches = []

        # Create batches with IDs for tracking
        batches = []
        for i in range(0, len(doc_chunks), self.batch_size):
            batch_chunks = doc_chunks[i:i + self.batch_size]
            batch_id = i // self.batch_size + 1
            batches.append({
                'id': batch_id,
                'chunks': batch_chunks,
                'retry_count': 0
            })

        total_batches = len(batches)

        # Process batches with retry logic
        for retry_round in range(self.max_retries):
            if retry_round == 0:
                batches_to_process = batches
                logger.info(
                    f"📊 Processing {len(batches_to_process)} documentation batches in parallel "
                    f"(attempt 1/{self.max_retries})"
                )
            else:
                batches_to_process = failed_batches
                logger.info(
                    f"🔄 Retrying {len(batches_to_process)} failed documentation batches "
                    f"(attempt {retry_round + 1}/{self.max_retries})"
                )
                failed_batches = []

            if not batches_to_process:
                break

            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                batch_futures = {}

                for batch_info in batches_to_process:
                    task = executor.submit(
                        self._process_doc_batch_parallel,
                        batch_info['chunks'],
                        collection_names,
                        batch_info['id'],
                        total_batches
                    )
                    batch_futures[task] = batch_info

                # Collect results as they complete
                for task in as_completed(batch_futures):
                    batch_info = batch_futures[task]
                    try:
                        batch_stored = task.result()
                        if batch_stored > 0:
                            total_stored += batch_stored
                            if batch_info['retry_count'] > 0:
                                logger.info(
                                    f"✅ Doc Batch {batch_info['id']}: {batch_stored} vectors stored "
                                    f"(after {batch_info['retry_count'] + 1} attempts)"
                                )
                            else:
                                logger.info(
                                    f"✅ Doc Batch {batch_info['id']}: {batch_stored} vectors stored"
                                )
                        else:
                            # Batch failed - retry up to max_retries (increased from 1)
                            if batch_info['retry_count'] < self.max_retries - 1:
                                batch_info['retry_count'] += 1
                                failed_batches.append(batch_info)
                                logger.warning(
                                    f"⚠️ Doc Batch {batch_info['id']} failed (likely timeout), will retry "
                                    f"(attempt {batch_info['retry_count'] + 1}/{self.max_retries})"
                                )
                            else:
                                # Max retries exceeded, likely permanent failure
                                logger.error(
                                    f"❌ Doc Batch {batch_info['id']} permanently failed after {self.max_retries} attempts "
                                    f"(validation, dimension, or persistent timeout error)"
                                )
                    except Exception as e:
                        # Exception during batch processing - this is transient
                        if batch_info['retry_count'] < self.max_retries - 1:
                            batch_info['retry_count'] += 1
                            failed_batches.append(batch_info)
                            logger.error(
                                f"❌ Doc Batch {batch_info['id']} exception: {e} "
                                f"(retry {batch_info['retry_count'] + 1}/{self.max_retries})"
                            )
                        else:
                            logger.error(
                                f"❌ Doc Batch {batch_info['id']} exception after max retries: {e}"
                            )

        # Final report
        if failed_batches:
            failed_count = sum(len(b['chunks']) for b in failed_batches)
            logger.error(
                f"❌ {len(failed_batches)} documentation batches ({failed_count} chunks) "
                f"failed after {self.max_retries} attempts"
            )
            for batch in failed_batches:
                logger.error(f"   - Doc Batch {batch['id']}: {len(batch['chunks'])} chunks lost")

        logger.info(
            f"✅ Parallel streaming complete: {total_stored}/{len(doc_chunks)} "
            f"documentation chunks stored in Qdrant"
        )
        return total_stored

    def _process_doc_batch_parallel(
        self,
        batch_chunks: List[Dict[str, Any]],
        collection_names: List[str],
        batch_id: int,
        total_batches: int
    ) -> int:
        """Process a single documentation batch in parallel with rate limiting."""
        # Acquire semaphore to limit concurrent Modal requests
        with self.embedding_service.acquire_rate_limit():
            collections_str = ', '.join(collection_names)
            logger.info(
                f"🔄 Parallel batch {batch_id}/{total_batches} "
                f"({len(batch_chunks)} documentation chunks) → {collections_str}"
            )

            # Extract texts from documentation chunks
            texts = [chunk.get('content_preview', '') for chunk in batch_chunks]

            # Generate embeddings
            embeddings = self.embedding_service.generate_embeddings(texts)

            if not embeddings or len(embeddings) != len(batch_chunks):
                logger.error(f"❌ Parallel batch {batch_id} documentation embedding failed")
                return 0

            # Store batch immediately in all target collections
            batch_stored = self.storage_manager.store_doc_vectors_multi_collection(
                batch_chunks,
                embeddings,
                collection_names
            )

            logger.info(
                f"💾 Parallel batch {batch_id}: {batch_stored}/{len(batch_chunks)} "
                f"documentation vectors stored in {len(collection_names)} collection(s)"
            )
            return batch_stored
