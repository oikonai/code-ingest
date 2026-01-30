"""
NuExtract-2.0-8B Modal Client

Single responsibility: Interface with Modal-deployed NuExtract service
for structured information extraction from text/images.

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
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
import json

logger = logging.getLogger(__name__)

@dataclass
class ExtractionRequest:
    """Request for structured extraction."""
    text: Optional[str] = None
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    template: Dict[str, Any] = None
    temperature: float = 0.0

@dataclass
class ExtractionResponse:
    """Response from NuExtract service."""
    extracted_data: Dict[str, Any]
    model: str
    processing_time_ms: float
    template: Dict[str, Any]
    success: bool
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

class NuExtractClient:
    """
    Client for Modal-deployed NuExtract-2.0-8B service.

    Interfaces with Modal's serverless vLLM deployment to extract
    structured information from text/images using JSON templates.
    """

    def __init__(self,
                 modal_app_name: str = "nuextract-service",
                 modal_endpoint: str = None,
                 requests_per_second: float = 10.0,
                 max_retries: int = 3,
                 timeout: float = 120.0):
        """
        Initialize NuExtract client.

        Args:
            modal_app_name: Name of the deployed Modal app
            modal_endpoint: Direct endpoint URL (if available)
            requests_per_second: Rate limit for Modal calls
            max_retries: Maximum retry attempts
            timeout: Request timeout (Modal functions can have cold starts)
        """
        self.modal_app_name = modal_app_name
        self.modal_endpoint = modal_endpoint or os.getenv('NUEXTRACT_ENDPOINT')

        # Try to import modal client for direct function calls
        self.modal_available = self._check_modal_client()

        if not self.modal_endpoint and not self.modal_available:
            raise ValueError(
                "Either NUEXTRACT_ENDPOINT environment variable or modal client required"
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

        logger.info(f"NuExtract client initialized")

    def _check_modal_client(self) -> bool:
        """Check if modal client is available for direct function calls."""
        try:
            import modal
            return True
        except ImportError:
            logger.warning("Modal client not available, using HTTP endpoint")
            return False

    def extract_from_text(self,
                         text: str,
                         template: Dict[str, Any],
                         temperature: float = 0.0) -> ExtractionResponse:
        """
        Extract structured information from text using JSON template.

        Args:
            text: Text to extract from
            template: JSON template defining extraction fields
            temperature: Sampling temperature (0.0 for precise extraction)

        Returns:
            ExtractionResponse with extracted data or error
        """
        if not text:
            return ExtractionResponse(
                extracted_data={},
                model="numind/NuExtract-2.0-8B",
                processing_time_ms=0.0,
                template=template,
                success=False,
                error_message="No text provided"
            )

        if not template:
            return ExtractionResponse(
                extracted_data={},
                model="numind/NuExtract-2.0-8B",
                processing_time_ms=0.0,
                template={},
                success=False,
                error_message="No template provided"
            )

        request = ExtractionRequest(
            text=text,
            template=template,
            temperature=temperature
        )

        return self._process_request(request)

    def extract_from_image(self,
                          image_url: Optional[str] = None,
                          image_base64: Optional[str] = None,
                          template: Dict[str, Any] = None,
                          temperature: float = 0.0) -> ExtractionResponse:
        """
        Extract structured information from image using JSON template.

        Args:
            image_url: URL to image (optional)
            image_base64: Base64-encoded image (optional)
            template: JSON template defining extraction fields
            temperature: Sampling temperature (0.0 for precise extraction)

        Returns:
            ExtractionResponse with extracted data or error
        """
        if not image_url and not image_base64:
            return ExtractionResponse(
                extracted_data={},
                model="numind/NuExtract-2.0-8B",
                processing_time_ms=0.0,
                template=template or {},
                success=False,
                error_message="No image provided"
            )

        if not template:
            return ExtractionResponse(
                extracted_data={},
                model="numind/NuExtract-2.0-8B",
                processing_time_ms=0.0,
                template={},
                success=False,
                error_message="No template provided"
            )

        request = ExtractionRequest(
            image_url=image_url,
            image_base64=image_base64,
            template=template,
            temperature=temperature
        )

        return self._process_request(request)

    def _process_request(self, request: ExtractionRequest) -> ExtractionResponse:
        """Process a single extraction request with Modal function."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit permission
                if not self.rate_limiter.acquire(timeout=30.0):
                    return ExtractionResponse(
                        extracted_data={},
                        model="numind/NuExtract-2.0-8B",
                        processing_time_ms=0.0,
                        template=request.template or {},
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

                    return ExtractionResponse(
                        extracted_data=result.get("extracted_data", {}),
                        model=result.get("model", "numind/NuExtract-2.0-8B"),
                        processing_time_ms=processing_time,
                        template=result.get("template", request.template or {}),
                        success=True
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
        return ExtractionResponse(
            extracted_data={},
            model="numind/NuExtract-2.0-8B",
            processing_time_ms=0.0,
            template=request.template or {},
            success=False,
            error_message=last_error or "All retry attempts failed"
        )

    def _call_modal_function(self, request: ExtractionRequest) -> Dict[str, Any]:
        """Call Modal function directly using modal client."""
        import modal

        # Get reference to deployed function
        app = modal.App.lookup(self.modal_app_name, create_if_missing=False)
        extract_func = app.cls_lookup("NuExtractService").extract

        # Build request payload
        payload = {
            "template": request.template,
            "temperature": request.temperature
        }

        if request.text:
            payload["text"] = request.text
        elif request.image_url:
            payload["image_url"] = request.image_url
        elif request.image_base64:
            payload["image_base64"] = request.image_base64

        # Call the function
        return extract_func.remote(payload)

    def _call_http_endpoint(self, request: ExtractionRequest) -> Dict[str, Any]:
        """Call Modal function via HTTP endpoint with startup detection."""
        payload = {
            "template": request.template,
            "temperature": request.temperature
        }

        if request.text:
            payload["text"] = request.text
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
