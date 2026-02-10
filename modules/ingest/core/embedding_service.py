"""
Embedding Service for DeepInfra Integration

Handles embedding generation via DeepInfra's OpenAI-compatible API.
Following CLAUDE.md: <500 lines, single responsibility (embedding generation only).
"""

import logging
import os
import time
import math
import threading
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings via DeepInfra.

    Responsibilities:
    - Generate embeddings using OpenAI-compatible API
    - Validate embedding quality (dimensions, None/NaN check)
    - Rate limiting via semaphore
    - Error handling and retry logic
    """

    def __init__(
        self,
        base_url: str = "https://api.deepinfra.com/v1/openai",
        model: str = "Qwen/Qwen3-Embedding-8B",
        rate_limit: int = 4,
        embedding_size: int = 4096,
        timeout: int = 60,
    ):
        """
        Initialize embedding service with DeepInfra.

        Args:
            base_url: DeepInfra API endpoint (default: https://api.deepinfra.com/v1/openai)
            model: Embedding model name (default: Qwen/Qwen3-Embedding-8B)
            rate_limit: Maximum concurrent requests
            embedding_size: Expected embedding dimension (4096 for Qwen3)
            timeout: Request timeout in seconds
        """
        # Get API key from environment
        self.deepinfra_key = os.getenv("DEEPINFRA_API_KEY")

        if not self.deepinfra_key:
            raise ValueError("DEEPINFRA_API_KEY environment variable required")

        # Configuration
        self.base_url = base_url
        self.model = model
        self.embedding_size = embedding_size
        self.timeout = timeout

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.deepinfra_key,
            base_url=self.base_url,
            timeout=timeout,
        )

        # Rate limiting
        self.semaphore = threading.Semaphore(rate_limit)

        logger.info(f"🔗 Embedding service initialized (DeepInfra)")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - Model: {self.model}")
        logger.info(f"   - Rate limit: {rate_limit} concurrent requests")
        logger.info(f"   - Embedding size: {embedding_size}D")
        logger.info(f"   - Timeout: {timeout}s")

    def warmup_containers(self, num_containers: int = 4, min_success_rate: float = 0.5) -> bool:
        """
        Warmup method for backward compatibility.

        DeepInfra API has minimal cold starts, so this is a no-op.
        Always returns True.

        Args:
            num_containers: Ignored (kept for API compatibility)
            min_success_rate: Ignored (kept for API compatibility)

        Returns:
            True (always succeeds)
        """
        logger.info(f"✅ DeepInfra embedding service ready")
        logger.info(f"   Model: {self.model} ({self.embedding_size}D)")
        return True

    def generate_embeddings(
        self,
        texts: List[str],
        max_retries: int = 3
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed
            max_retries: Maximum retry attempts for transient failures

        Returns:
            List of embedding vectors, or empty list on failure
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    logger.info(f"🔄 Embedding batch: {len(texts)} texts")
                else:
                    logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for {len(texts)} texts")

                start_time = time.time()

                # Call OpenAI-compatible embeddings API
                response = self.client.embeddings.create(
                    input=texts,
                    model=self.model,
                    encoding_format="float"
                )

                elapsed_ms = (time.time() - start_time) * 1000

                # Extract embeddings
                embeddings = []
                for emb_obj in response.data:
                    embedding = emb_obj.embedding

                    # Validate embedding
                    if not self.validate_embedding(embedding):
                        return []  # Reject entire batch on validation failure

                    embeddings.append(embedding)

                if attempt > 0:
                    logger.info(f"✅ Successfully generated {len(embeddings)} embeddings (after {attempt + 1} attempts)")
                else:
                    logger.info(f"✅ Successfully generated {len(embeddings)} embeddings ({elapsed_ms:.1f}ms)")

                return embeddings

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Request failed on attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {e}")

                if attempt < max_retries - 1:
                    wait_time = min(2 ** attempt, 8)  # Exponential backoff: 1s, 2s, 4s max
                    logger.info(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"❌ Embedding batch failed after {max_retries} retries: "
                        f"{type(last_error).__name__}: {last_error}"
                    )
                    return []

        return []

    def validate_embedding(self, embedding: List[float]) -> bool:
        """
        Validate embedding quality.

        Checks:
        - No None values
        - No NaN or infinite values
        - Correct dimension (4096 for Qwen3)

        Args:
            embedding: Embedding vector to validate

        Returns:
            True if valid, False otherwise
        """
        # Check for None values
        if None in embedding:
            logger.error(f"❌ Embedding contains None values - rejecting batch")
            return False

        # Check for NaN or infinite values
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in embedding):
            logger.error(f"❌ Embedding contains NaN or infinite values - rejecting batch")
            return False

        # Validate dimension
        if len(embedding) != self.embedding_size:
            logger.error(
                f"❌ Embedding dimension mismatch: expected {self.embedding_size}, "
                f"got {len(embedding)} - rejecting batch"
            )
            return False

        return True

    def acquire_rate_limit(self):
        """Acquire rate limit semaphore (for use in context manager)."""
        return self.semaphore
