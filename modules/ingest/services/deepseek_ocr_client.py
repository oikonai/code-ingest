"""
DeepSeek-OCR Modal Client

Single responsibility: Interface with Modal-deployed DeepSeek-OCR service
for image-to-text/markdown conversion.

Following CLAUDE.md guidelines:
- Under 400 lines
- OOP-first design
- Single responsibility principle
- Modular and reusable
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

@dataclass
class OCRRequest:
    """Request for OCR processing."""
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    prompt: str = "<image>\n<|grounding|>Convert the document to markdown"
    page_num: Optional[int] = None  # For PDF: specific page to extract (1-indexed), or None for all pages
    base_size: int = 1024
    image_size: int = 640

@dataclass
class OCRResponse:
    """Response from DeepSeek-OCR service."""
    text: str
    model: str
    processing_time_ms: float
    success: bool
    pages_processed: int = 1
    error_message: Optional[str] = None

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

class DeepSeekOCRClient:
    """
    Client for Modal-deployed DeepSeek-OCR service.

    Interfaces with Modal's serverless vLLM deployment to convert
    images to text/markdown for document digitization.
    """

    def __init__(self,
                 modal_app_name: str = "deepseek-ocr-service",
                 modal_endpoint: str = None,
                 requests_per_second: float = 10.0,
                 max_retries: int = 3,
                 timeout: float = 120.0):
        """
        Initialize DeepSeek-OCR client.

        Args:
            modal_app_name: Name of the deployed Modal app
            modal_endpoint: Direct endpoint URL (if available)
            requests_per_second: Rate limit for Modal calls
            max_retries: Maximum retry attempts
            timeout: Request timeout (Modal functions can have cold starts)
        """
        self.modal_app_name = modal_app_name
        self.modal_endpoint = modal_endpoint or os.getenv('DEEPSEEK_OCR_ENDPOINT')

        # Try to import modal client for direct function calls
        self.modal_available = self._check_modal_client()

        if not self.modal_endpoint and not self.modal_available:
            raise ValueError(
                "Either DEEPSEEK_OCR_ENDPOINT environment variable or modal client required"
            )

        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize rate limiter
        self.rate_limiter = ModalRateLimiter(requests_per_second)

        # Request headers for HTTP endpoint
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'I2P/1.0'
        }

        # Performance tracking
        self.request_count = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        self.cold_starts = 0

        logger.info(f"DeepSeek-OCR client initialized")

    def _check_modal_client(self) -> bool:
        """Check if modal client is available for direct function calls."""
        try:
            import modal
            return True
        except ImportError:
            logger.warning("Modal client not available, using HTTP endpoint")
            return False

    def process_image(self,
                     image_url: Optional[str] = None,
                     image_base64: Optional[str] = None,
                     pdf_url: Optional[str] = None,
                     pdf_base64: Optional[str] = None,
                     prompt: str = "<image>\n<|grounding|>Convert the document to markdown",
                     page_num: Optional[int] = None,
                     base_size: int = 1024,
                     image_size: int = 640) -> OCRResponse:
        """
        Process image/PDF and extract text/markdown via Modal service.

        Args:
            image_url: URL to image (optional)
            image_base64: Base64-encoded image (optional)
            pdf_url: URL to PDF (optional)
            pdf_base64: Base64-encoded PDF (optional)
            prompt: Extraction prompt
            page_num: PDF page number (1-indexed), or None for all pages
            base_size: Base image size for processing
            image_size: Target image size for processing

        Returns:
            OCRResponse with extracted text or error
        """
        if not any([image_url, image_base64, pdf_url, pdf_base64]):
            return OCRResponse(
                text="",
                model="deepseek-ai/DeepSeek-OCR",
                processing_time_ms=0.0,
                success=False,
                error_message="No input provided (need image_url, image_base64, pdf_url, or pdf_base64)"
            )

        request = OCRRequest(
            image_url=image_url,
            image_base64=image_base64,
            pdf_url=pdf_url,
            pdf_base64=pdf_base64,
            prompt=prompt,
            page_num=page_num,
            base_size=base_size,
            image_size=image_size
        )

        return self._process_request(request)

    def _process_request(self, request: OCRRequest) -> OCRResponse:
        """Process a single OCR request with Modal function."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit permission
                if not self.rate_limiter.acquire(timeout=30.0):
                    return OCRResponse(
                        text="",
                        model="deepseek-ai/DeepSeek-OCR",
                        processing_time_ms=0.0,
                        mode=request.mode,
                        success=False,
                        error_message="Rate limiter timeout"
                    )

                # Make Modal function call
                start_time = time.time()

                if self.modal_available:
                    result = self._call_modal_function(request)
                else:
                    result = self._call_http_endpoint(request)

                processing_time = (time.time() - start_time) * 1000

                if result and result.get("success", False):
                    self.request_count += 1
                    self.total_processing_time += processing_time

                    return OCRResponse(
                        text=result.get("text", ""),
                        model=result.get("model", "deepseek-ai/DeepSeek-OCR"),
                        processing_time_ms=processing_time,
                        success=True,
                        pages_processed=result.get("pages_processed", 1)
                    )
                else:
                    last_error = result.get("error", "Unknown error") if result else "No result"

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
        return OCRResponse(
            text="",
            model="deepseek-ai/DeepSeek-OCR",
            processing_time_ms=0.0,
            success=False,
            pages_processed=0,
            error_message=last_error or "All retry attempts failed"
        )

    def _call_modal_function(self, request: OCRRequest) -> Dict[str, Any]:
        """Call Modal function directly using modal client."""
        import modal

        # Get reference to deployed function
        app = modal.App.lookup(self.modal_app_name, create_if_missing=False)
        process_func = app.cls_lookup("DeepSeekOCRService").process_image

        # Build request payload
        payload = {
            "prompt": request.prompt,
            "base_size": request.base_size,
            "image_size": request.image_size
        }

        if request.page_num is not None:
            payload["page_num"] = request.page_num

        # Add input source
        if request.pdf_url:
            payload["pdf_url"] = request.pdf_url
        elif request.pdf_base64:
            payload["pdf_base64"] = request.pdf_base64
        elif request.image_url:
            payload["image_url"] = request.image_url
        elif request.image_base64:
            payload["image_base64"] = request.image_base64

        # Call the function
        return process_func.remote(payload)

    def _call_http_endpoint(self, request: OCRRequest) -> Dict[str, Any]:
        """Call Modal function via HTTP endpoint with startup detection."""
        payload = {
            "prompt": request.prompt,
            "base_size": request.base_size,
            "image_size": request.image_size
        }

        if request.page_num is not None:
            payload["page_num"] = request.page_num

        # Add input source
        if request.pdf_url:
            payload["pdf_url"] = request.pdf_url
        elif request.pdf_base64:
            payload["pdf_base64"] = request.pdf_base64
        elif request.image_url:
            payload["image_url"] = request.image_url
        elif request.image_base64:
            payload["image_base64"] = request.image_base64

        max_retries = 3
        startup_timeout = 90  # 90 seconds for container startup

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.modal_endpoint,
                    json=payload,
                    headers=self.headers,
                    timeout=startup_timeout if attempt == 0 else self.timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 502 and attempt < max_retries - 1:
                    # Container might be starting up
                    logger.warning(f"Modal container starting up (attempt {attempt + 1}/{max_retries}), retrying in 10s...")
                    time.sleep(10)
                    continue
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}", "success": False}

            except requests.exceptions.Timeout as e:
                if attempt == 0:
                    logger.warning(f"Modal container startup timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(5)
                    continue
                else:
                    return {"error": f"Request timeout: {e}", "success": False}
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Modal connection error (attempt {attempt + 1}/{max_retries}), retrying in 15s...")
                    time.sleep(15)
                    continue
                else:
                    return {"error": f"Connection failed: {e}", "success": False}

        return {"error": "All retry attempts failed", "success": False}

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
            'rate_limit_rps': self.rate_limiter.requests_per_second,
            'modal_app_name': self.modal_app_name,
            'modal_endpoint': self.modal_endpoint,
            'modal_client_available': self.modal_available,
            'cold_start_rate': (
                self.cold_starts / self.request_count
                if self.request_count > 0 else 0.0
            )
        }
