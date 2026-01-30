"""
PaddleOCR-VL Service on Modal

Deploys PaddleOCR-VL (0.9B) using vLLM serve with OpenAI-compatible API.
Ultra-compact vision-language model specialized for document understanding.

Architecture:
- Uses vLLM serve for OpenAI-compatible API
- Runs on A100 GPU (0.9B model)
- Persistent model caching via Modal Volume
- Standard /v1/chat/completions endpoint

Model: PaddlePaddle/PaddleOCR-VL (0.9B params)
Capabilities: OCR, table recognition, formula recognition, chart recognition
"""

import modal
import subprocess

APP_NAME = "pocr"
app = modal.App(APP_NAME)

# Build image with vLLM nightly (PaddleOCR-VL support)
paddleocr_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "pillow",
        "requests",
        "openai",  # For OpenAI client
    )
    .run_commands(
        # Install vLLM nightly with BOTH indices for proper dependency resolution
        "pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly --extra-index-url https://download.pytorch.org/whl/cu129"
    )
)

# Model storage volume
model_volume = modal.Volume.from_name("paddleocr-models", create_if_missing=True)
MODEL_CACHE = "/models"

@app.cls(
    gpu="A100",  # 0.9B model - smaller GPU sufficient
    image=paddleocr_image,
    volumes={MODEL_CACHE: model_volume},
    scaledown_window=300,  # Scale down after 5 min idle
    timeout=3600,
    max_containers=2,
    allow_concurrent_inputs=100,  # Allow 100 concurrent requests per container
)
class OCR:
    """PaddleOCR-VL service using vLLM serve with OpenAI API"""

    @modal.enter()
    def start_server(self):
        """Start vLLM OpenAI-compatible server"""
        import os
        from pathlib import Path
        from huggingface_hub import snapshot_download
        import time
        import threading

        # Set cache directories
        os.environ["HF_HOME"] = MODEL_CACHE
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE
        os.environ["HF_DATASETS_CACHE"] = MODEL_CACHE

        self.model_name = "PaddlePaddle/PaddleOCR-VL"
        model_cache_path = f"{MODEL_CACHE}/models--PaddlePaddle--PaddleOCR-VL"

        # Download model if not cached
        if not Path(model_cache_path).exists():
            print(f"⬇️ Downloading {self.model_name} (0.9B params)...")
            snapshot_download(
                repo_id=self.model_name,
                cache_dir=MODEL_CACHE,
                local_files_only=False,
                ignore_patterns=["*.msgpack", "*.h5"],
            )
            print("💾 Committing model to volume...")
            model_volume.commit()
            print("✅ Model cached successfully!")
        else:
            print("📦 Model found in cache")

        # Start vLLM server in background
        print("🚀 Starting vLLM OpenAI-compatible server...")

        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.model_name,
            "--host", "0.0.0.0",
            "--port", "8000",
            "--download-dir", MODEL_CACHE,
            "--trust-remote-code",
            "--dtype", "bfloat16",
            "--max-model-len", "16384",
            "--max-num-batched-tokens", "16384",
            "--max-num-seqs", "32",  # Allow up to 32 concurrent sequences
            "--disable-log-requests",
            "--gpu-memory-utilization", "0.9",
        ]

        # Start vLLM process
        self.vllm_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def stream_output():
            # Stream output
            for line in self.vllm_process.stdout:
                print(line.rstrip())

        # Start output streaming in background thread
        output_thread = threading.Thread(target=stream_output, daemon=True)
        output_thread.start()

        # Wait for server to be ready
        print("⏳ Waiting for vLLM server to start...")
        import requests
        for i in range(180):  # Wait up to 3 minutes for model loading
            try:
                # Check if process is still alive
                if self.vllm_process.poll() is not None:
                    raise RuntimeError(f"vLLM process died with exit code {self.vllm_process.returncode}")

                response = requests.get("http://localhost:8000/health", timeout=1)
                if response.status_code == 200:
                    print("✅ vLLM server ready!")
                    break
            except requests.exceptions.RequestException:
                # Connection error is expected while server is starting
                pass

            if i % 10 == 0:  # Log progress every 10 seconds
                print(f"⏳ Still waiting... ({i}s elapsed)")
            time.sleep(1)
        else:
            raise RuntimeError("vLLM server failed to start within 3 minutes")

        # Initialize OpenAI client pointing to local vLLM server
        from openai import OpenAI
        self.client = OpenAI(
            base_url="http://localhost:8000/v1",
            api_key="dummy",  # vLLM doesn't require real API key
        )

    @modal.method()
    def chat_completion(self, messages: list, temperature: float = 0.0, max_tokens: int = 4096):
        """
        OpenAI-compatible chat completion

        Args:
            messages: OpenAI-style messages list
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            OpenAI-style completion response
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.model_dump()

    @modal.fastapi_endpoint(method="POST")
    def chat(self, request: dict):
        """
        OpenAI-compatible /v1/chat/completions endpoint

        Request format (OpenAI standard):
        {
            "model": "PaddlePaddle/PaddleOCR-VL",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
                        {"type": "text", "text": "OCR:"}
                    ]
                }
            ],
            "temperature": 0.0,
            "max_tokens": 4096
        }
        """
        import time
        start = time.time()

        try:
            messages = request.get("messages", [])
            temperature = request.get("temperature", 0.0)
            max_tokens = request.get("max_tokens", 4096)

            # Call vLLM server
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            elapsed = (time.time() - start) * 1000
            print(f"✅ Completed request in {elapsed:.1f}ms")

            return response.model_dump()

        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "model": "PaddlePaddle/PaddleOCR-VL",
            "parameters": "0.9B",
            "capabilities": ["ocr", "table", "formula", "chart"],
            "backend": "vLLM-serve",
            "api": "OpenAI-compatible"
        }


@app.local_entrypoint()
def main():
    """Test PaddleOCR-VL endpoint locally"""
    import base64
    from pathlib import Path

    print("🧪 Testing PaddleOCR-VL Service (OpenAI API)")
    print("=" * 80)

    # Load test image
    test_file = "test.pdf"
    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return

    with open(test_file, "rb") as f:
        file_bytes = f.read()
        file_base64 = base64.b64encode(file_bytes).decode()

    print(f"📄 Loaded test file: {test_file}")

    # Initialize service
    service = PaddleOCRService()

    # Health check
    health = service.health.remote()
    print(f"✅ Health check: {health}")

    # Create OpenAI-style message
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:application/pdf;base64,{file_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": "OCR:"
                }
            ]
        }
    ]

    # Call chat completion
    print("\n⚡ Processing with OpenAI API...")
    result = service.chat_completion.remote(messages=messages)

    print(f"\n✅ Response:")
    print(result["choices"][0]["message"]["content"][:500])
