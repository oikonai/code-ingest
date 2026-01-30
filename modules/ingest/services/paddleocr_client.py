"""
PaddleOCR-VL Client

Client for interacting with PaddleOCR-VL Modal service.
Supports OCR, table recognition, formula recognition, and chart recognition.
"""

import os
import base64
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path


class PaddleOCRClient:
    """Client for PaddleOCR-VL Modal service"""

    def __init__(self, endpoint_url: Optional[str] = None):
        """
        Initialize PaddleOCR client

        Args:
            endpoint_url: Modal endpoint URL (or set PADDLEOCR_ENDPOINT env var)
        """
        self.endpoint_url = endpoint_url or os.getenv("PADDLEOCR_ENDPOINT")
        if not self.endpoint_url:
            raise ValueError(
                "PaddleOCR endpoint URL required. "
                "Pass endpoint_url or set PADDLEOCR_ENDPOINT env var"
            )

        # Remove trailing slash
        self.endpoint_url = self.endpoint_url.rstrip("/")

    def ocr_image(
        self,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        task: str = "ocr",
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """
        Perform OCR on a single image

        Args:
            image_path: Path to local image file
            image_url: URL to image
            image_base64: Base64-encoded image
            task: Task type (ocr, table, formula, chart, markdown)
            prompt: Custom prompt (overrides task)
            temperature: Sampling temperature (0.0 for deterministic)
            timeout: Request timeout in seconds

        Returns:
            dict with extracted text and metadata
        """
        # Prepare request payload
        payload = {
            "task": task,
            "temperature": temperature,
        }

        if prompt:
            payload["prompt"] = prompt

        # Handle image input
        if image_path:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
                payload["image_base64"] = base64.b64encode(img_bytes).decode()
        elif image_url:
            payload["image_url"] = image_url
        elif image_base64:
            payload["image_base64"] = image_base64
        else:
            raise ValueError("Must provide image_path, image_url, or image_base64")

        # Call Modal endpoint
        response = requests.post(
            f"{self.endpoint_url}/ocr",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        return response.json()

    def ocr_pdf(
        self,
        pdf_path: Optional[str] = None,
        pdf_base64: Optional[str] = None,
        task: str = "ocr",
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Perform OCR on a PDF document

        Args:
            pdf_path: Path to local PDF file
            pdf_base64: Base64-encoded PDF
            task: Task type (ocr, table, formula, chart, markdown)
            prompt: Custom prompt (overrides task)
            temperature: Sampling temperature (0.0 for deterministic)
            timeout: Request timeout in seconds

        Returns:
            dict with extracted text and metadata
        """
        # Prepare request payload
        payload = {
            "task": task,
            "temperature": temperature,
        }

        if prompt:
            payload["prompt"] = prompt

        # Handle PDF input
        if pdf_path:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
                payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode()
        elif pdf_base64:
            payload["pdf_base64"] = pdf_base64
        else:
            raise ValueError("Must provide pdf_path or pdf_base64")

        # Call Modal endpoint
        response = requests.post(
            f"{self.endpoint_url}/ocr",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        return response.json()

    def ocr_batch(
        self,
        file_paths: List[str],
        task: str = "ocr",
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        timeout: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Perform OCR on multiple files (images or PDFs)

        Args:
            file_paths: List of file paths
            task: Task type (ocr, table, formula, chart, markdown)
            prompt: Custom prompt (overrides task)
            temperature: Sampling temperature
            timeout: Request timeout per file

        Returns:
            List of result dicts
        """
        results = []

        for file_path in file_paths:
            path = Path(file_path)
            try:
                if path.suffix.lower() == ".pdf":
                    result = self.ocr_pdf(
                        pdf_path=file_path,
                        task=task,
                        prompt=prompt,
                        temperature=temperature,
                        timeout=timeout,
                    )
                else:
                    result = self.ocr_image(
                        image_path=file_path,
                        task=task,
                        prompt=prompt,
                        temperature=temperature,
                        timeout=timeout,
                    )
                results.append(result)
            except Exception as e:
                results.append({
                    "error": str(e),
                    "file": file_path,
                    "success": False,
                })

        return results

    def health_check(self, timeout: int = 30) -> Dict[str, Any]:
        """
        Check service health

        Args:
            timeout: Request timeout in seconds

        Returns:
            dict with health status
        """
        response = requests.get(
            f"{self.endpoint_url}/paddleocr-health",
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()


def main():
    """CLI interface for PaddleOCR client"""
    import argparse

    parser = argparse.ArgumentParser(description="PaddleOCR-VL Client")
    parser.add_argument("--endpoint", required=True, help="Modal endpoint URL")
    parser.add_argument("--file", required=True, help="Image or PDF file path")
    parser.add_argument(
        "--task",
        choices=["ocr", "table", "formula", "chart", "markdown"],
        default="ocr",
        help="Task type",
    )
    parser.add_argument("--prompt", help="Custom prompt")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--health", action="store_true", help="Check service health")

    args = parser.parse_args()

    # Initialize client
    client = PaddleOCRClient(endpoint_url=args.endpoint)

    # Health check
    if args.health:
        health = client.health_check()
        print("🏥 Health Check:")
        print(f"   Status: {health['status']}")
        print(f"   Model: {health['model']}")
        print(f"   Parameters: {health['parameters']}")
        print(f"   Backend: {health['backend']}")
        return

    # Process file
    print(f"🚀 Processing {args.file}...")

    file_path = Path(args.file)
    if file_path.suffix.lower() == ".pdf":
        result = client.ocr_pdf(
            pdf_path=args.file,
            task=args.task,
            prompt=args.prompt,
        )
    else:
        result = client.ocr_image(
            image_path=args.file,
            task=args.task,
            prompt=args.prompt,
        )

    if result["success"]:
        print(f"✅ Success!")
        print(f"📊 Pages processed: {result['pages_processed']}")
        print(f"⏱️  Processing time: {result['processing_time_ms']:.1f}ms")
        print(f"\n📝 Extracted Text:")
        print("-" * 80)
        print(result["text"])
        print("-" * 80)

        # Save to file if specified
        if args.output:
            with open(args.output, "w") as f:
                f.write(result["text"])
            print(f"\n💾 Saved to {args.output}")

    else:
        print(f"❌ Failed: {result.get('error')}")


if __name__ == "__main__":
    main()
