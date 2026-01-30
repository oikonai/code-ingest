"""
Modal Client for Qwen3-Embedding-8B

Single responsibility: Interface with Modal-deployed Qwen3-Embedding-8B service
to generate high-precision 4096-dimensional embeddings for Rust code chunks.

Following AGENTS.md guidelines:
- Under 400 lines
- OOP-first design  
- Single responsibility principle
- Modular and reusable
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import requests
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingRequest:
    """Request for embedding generation."""
    text: str
    chunk_id: str
    metadata: Dict[str, Any]

@dataclass  
class EmbeddingResponse:
    """Response from Modal Qwen3-Embedding-8B service."""
    chunk_id: str
    embedding: List[float]
    model: str
    dimensions: int
    tokens_used: int
    processing_time_ms: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class BatchResult:
    """Result of processing a batch of embedding requests."""
    successful_responses: List[EmbeddingResponse]
    failed_requests: List[Tuple[EmbeddingRequest, str]]
    total_requests: int
    success_rate: float
    total_processing_time_ms: float

class ModalRateLimiter:
    """Thread-safe rate limiter for Modal function calls."""
    
    def __init__(self, requests_per_second: float = 10.0):
        """Initialize rate limiter for Modal's generous limits."""
        self.requests_per_second = requests_per_second
        self.tokens = requests_per_second
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire permission to make a Modal function call."""
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                
                self.tokens = min(
                    self.requests_per_second,
                    self.tokens + elapsed * self.requests_per_second
                )
                self.last_update = now
                
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True
            
            if time.time() - start_time > timeout:
                return False
                
            time.sleep(0.1)

class ModalEmbeddingClient:
    """
    Client for Modal-deployed Qwen3-Embedding-8B service.
    
    Interfaces with Modal's serverless vLLM deployment to generate
    high-precision 4096-dimensional embeddings for Rust code chunks.
    """
    
    def __init__(self, 
                 modal_app_name: str = "qwen3-embedding-service",
                 modal_endpoint: str = None,
                 requests_per_second: float = 10.0,
                 max_retries: int = 3,
                 timeout: float = 120.0):
        """
        Initialize Modal embedding client.
        
        Args:
            modal_app_name: Name of the deployed Modal app
            modal_endpoint: Direct endpoint URL (if available)
            requests_per_second: Rate limit for Modal calls
            max_retries: Maximum retry attempts
            timeout: Request timeout (Modal functions can have cold starts)
        """
        self.modal_app_name = modal_app_name
        self.modal_endpoint = modal_endpoint or os.getenv('MODAL_ENDPOINT')
        
        # Try to import modal client for direct function calls
        self.modal_available = self._check_modal_client()
        
        if not self.modal_endpoint and not self.modal_available:
            raise ValueError(
                "Either MODAL_ENDPOINT environment variable or modal client required"
            )
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.expected_dimensions = 4096  # Qwen3-Embedding-8B dimensions
        self.max_context_tokens = 32768  # Model context limit
        self.max_chunk_tokens = 30000    # Safe limit per PRD
        
        # Initialize rate limiter
        self.rate_limiter = ModalRateLimiter(requests_per_second)
        
        # Request headers for HTTP endpoint
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'RustCodeSearch/1.0'
        }
        
        # Performance tracking
        self.request_count = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        self.cold_starts = 0
        
        logger.info(f"Modal embedding client initialized for {self.expected_dimensions}D embeddings")
    
    def _check_modal_client(self) -> bool:
        """Check if modal client is available for direct function calls."""
        try:
            import modal
            return True
        except ImportError:
            logger.warning("Modal client not available, using HTTP endpoint")
            return False
    
    def create_embedding(self, text: str, chunk_id: str, 
                        metadata: Dict[str, Any] = None) -> EmbeddingResponse:
        """
        Create embedding for a single text chunk via Modal service.
        
        Args:
            text: Rust code text to embed
            chunk_id: Unique identifier for the chunk
            metadata: Additional metadata
            
        Returns:
            EmbeddingResponse with embedding vector or error
        """
        if not text.strip():
            return EmbeddingResponse(
                chunk_id=chunk_id,
                embedding=[],
                model="qwen3-embedding-8b",
                dimensions=0,
                tokens_used=0,
                processing_time_ms=0.0,
                success=False,
                error_message="Empty text provided"
            )
        
        # Validate token count
        estimated_tokens = self._estimate_tokens(text)
        if estimated_tokens > self.max_chunk_tokens:
            return EmbeddingResponse(
                chunk_id=chunk_id,
                embedding=[],
                model="qwen3-embedding-8b", 
                dimensions=0,
                tokens_used=estimated_tokens,
                processing_time_ms=0.0,
                success=False,
                error_message=f"Text exceeds {self.max_chunk_tokens} token limit: {estimated_tokens}"
            )
        
        request = EmbeddingRequest(
            text=text,
            chunk_id=chunk_id,
            metadata=metadata or {}
        )
        
        return self._process_single_request(request)
    
    def create_batch_embeddings(self, requests: List[EmbeddingRequest], 
                              batch_size: int = 50) -> BatchResult:
        """
        Create embeddings for multiple chunks via Modal batch processing.
        
        Args:
            requests: List of embedding requests
            batch_size: Number of requests per batch (Modal handles large batches well)
            
        Returns:
            BatchResult with successful and failed responses
        """
        start_time = time.time()
        successful_responses = []
        failed_requests = []
        
        # Process in batches optimized for Modal's serverless architecture
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            
            # Use batch processing for efficiency
            batch_response = self._process_batch_request(batch)
            
            if batch_response:
                successful_responses.extend(batch_response.successful_responses)
                failed_requests.extend(batch_response.failed_requests)
            else:
                # Fallback to individual processing
                for request in batch:
                    response = self._process_single_request(request)
                    
                    if response.success:
                        successful_responses.append(response)
                    else:
                        failed_requests.append((request, response.error_message))
            
            # Brief pause between batches
            if i + batch_size < len(requests):
                time.sleep(0.1)
        
        total_time = (time.time() - start_time) * 1000
        success_rate = len(successful_responses) / len(requests) if requests else 0.0
        
        return BatchResult(
            successful_responses=successful_responses,
            failed_requests=failed_requests,
            total_requests=len(requests),
            success_rate=success_rate,
            total_processing_time_ms=total_time
        )
    
    def _process_batch_request(self, requests: List[EmbeddingRequest]) -> Optional[BatchResult]:
        """Process multiple requests in a single Modal function call."""
        try:
            # Acquire rate limit permission
            if not self.rate_limiter.acquire(timeout=30.0):
                return None
            
            texts = [req.text for req in requests]
            
            start_time = time.time()
            
            if self.modal_available:
                # Use direct Modal function call
                results = self._call_modal_function(texts)
            else:
                # Use HTTP endpoint
                results = self._call_http_endpoint(texts)
            
            processing_time = (time.time() - start_time) * 1000
            
            return self._parse_batch_results(results, requests, processing_time)
            
        except Exception as e:
            logger.warning(f"Batch processing failed, will fallback to individual: {e}")
            return None
    
    def _call_modal_function(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Call Modal function directly using modal client."""
        import modal
        
        # Get reference to deployed function
        app = modal.App.lookup(self.modal_app_name, create_if_missing=False)
        embed_func = app.cls_lookup("QwenEmbeddingModel").embed
        
        # Call the function
        return embed_func.remote(texts)
    
    def _call_http_endpoint(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Call Modal function via HTTP endpoint with startup detection."""
        payload = {
            "texts": texts,
            "model": "qwen3-embedding-8b"
        }
        
        max_retries = 3
        startup_timeout = 60  # 60 seconds for container startup
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.modal_endpoint,
                    json=payload,
                    headers=self.headers,
                    timeout=startup_timeout if attempt == 0 else self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("results", [])
                elif response.status_code == 502 and attempt < max_retries - 1:
                    # Container might be starting up
                    logger.warning(f"Modal container starting up (attempt {attempt + 1}/{max_retries}), retrying in 10s...")
                    time.sleep(10)
                    continue
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout as e:
                if attempt == 0:
                    logger.warning(f"Modal container startup timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(5)
                    continue
                else:
                    raise Exception(f"Request timeout after startup: {e}")
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Modal connection error (attempt {attempt + 1}/{max_retries}), retrying in 15s...")
                    time.sleep(15)
                    continue
                else:
                    raise Exception(f"Connection failed after retries: {e}")
        
        raise Exception("All retry attempts failed")
    
    def _process_single_request(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Process a single embedding request with Modal function."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit permission
                if not self.rate_limiter.acquire(timeout=30.0):
                    return EmbeddingResponse(
                        chunk_id=request.chunk_id,
                        embedding=[],
                        model="qwen3-embedding-8b",
                        dimensions=0,
                        tokens_used=0,
                        processing_time_ms=0.0,
                        success=False,
                        error_message="Rate limiter timeout"
                    )
                
                # Make Modal function call
                start_time = time.time()
                
                if self.modal_available:
                    results = self._call_modal_function([request.text])
                else:
                    results = self._call_http_endpoint([request.text])
                
                processing_time = (time.time() - start_time) * 1000
                
                if results and len(results) > 0:
                    result = results[0]
                    
                    if result.get("success", False):
                        embedding = result["embedding"]
                        
                        # Validate dimensions
                        if len(embedding) != self.expected_dimensions:
                            return EmbeddingResponse(
                                chunk_id=request.chunk_id,
                                embedding=[],
                                model=result.get("model", "qwen3-embedding-8b"),
                                dimensions=len(embedding),
                                tokens_used=result.get("tokens_used", 0),
                                processing_time_ms=processing_time,
                                success=False,
                                error_message=f"Expected {self.expected_dimensions}D, got {len(embedding)}D"
                            )
                        
                        self.request_count += 1
                        self.total_processing_time += processing_time
                        
                        return EmbeddingResponse(
                            chunk_id=request.chunk_id,
                            embedding=embedding,
                            model=result.get("model", "qwen3-embedding-8b"),
                            dimensions=len(embedding),
                            tokens_used=result.get("tokens_used", 0),
                            processing_time_ms=processing_time,
                            success=True
                        )
                    else:
                        last_error = result.get("error_message", "Unknown error")
                else:
                    last_error = "No results returned"
                
                # Handle retries with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 1.0
                    logger.warning(f"Request failed, retrying in {wait_time}s: {last_error}")
                    time.sleep(wait_time)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Request attempt {attempt + 1} failed: {e}")
                
                # Check for Modal-specific errors
                if "cold start" in str(e).lower() or "timeout" in str(e).lower():
                    self.cold_starts += 1
        
        # All retries failed
        self.error_count += 1
        return EmbeddingResponse(
            chunk_id=request.chunk_id,
            embedding=[],
            model="qwen3-embedding-8b",
            dimensions=0, 
            tokens_used=0,
            processing_time_ms=0.0,
            success=False,
            error_message=last_error or "All retry attempts failed"
        )
    
    def _parse_batch_results(self, results: List[Dict[str, Any]], 
                           requests: List[EmbeddingRequest],
                           processing_time_ms: float) -> BatchResult:
        """Parse batch results from Modal function."""
        successful_responses = []
        failed_requests = []
        
        for i, result in enumerate(results):
            request = requests[i] if i < len(requests) else None
            
            if not request:
                continue
            
            if result.get("success", False):
                response = EmbeddingResponse(
                    chunk_id=request.chunk_id,
                    embedding=result["embedding"],
                    model=result.get("model", "qwen3-embedding-8b"),
                    dimensions=len(result["embedding"]),
                    tokens_used=result.get("tokens_used", 0),
                    processing_time_ms=processing_time_ms / len(results),
                    success=True
                )
                successful_responses.append(response)
            else:
                failed_requests.append((request, result.get("error_message", "Unknown error")))
        
        return BatchResult(
            successful_responses=successful_responses,
            failed_requests=failed_requests,
            total_requests=len(requests),
            success_rate=len(successful_responses) / len(requests),
            total_processing_time_ms=processing_time_ms
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for Rust code text."""
        # Qwen tokenization is roughly 1 token per 3-4 characters for code
        return len(text) // 3
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics including Modal-specific metrics."""
        avg_processing_time = (
            self.total_processing_time / self.request_count 
            if self.request_count > 0 else 0.0
        )
        
        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'cold_starts': self.cold_starts,
            'success_rate': (
                (self.request_count - self.error_count) / self.request_count
                if self.request_count > 0 else 0.0
            ),
            'average_processing_time_ms': avg_processing_time,
            'total_processing_time_ms': self.total_processing_time,
            'expected_dimensions': self.expected_dimensions,
            'rate_limit_rps': self.rate_limiter.requests_per_second,
            'modal_app_name': self.modal_app_name,
            'modal_endpoint': self.modal_endpoint,
            'modal_client_available': self.modal_available,
            'cold_start_rate': (
                self.cold_starts / self.request_count 
                if self.request_count > 0 else 0.0
            )
        }
    
    def validate_embedding(self, embedding: List[float]) -> bool:
        """
        Validate an embedding vector.
        
        Args:
            embedding: Embedding vector to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(embedding, list):
            return False
        
        if len(embedding) != self.expected_dimensions:
            return False
        
        try:
            # Check if all elements are valid floats
            float_embedding = [float(x) for x in embedding]
            
            # Check for NaN or infinite values
            for val in float_embedding:
                if np.isnan(val) or np.isinf(val):
                    return False
            
            return True
            
        except (ValueError, TypeError):
            return False