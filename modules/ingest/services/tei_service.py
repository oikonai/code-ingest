"""
TEI Service on Modal - Correct Architecture

TEI runs as standalone HTTP server on port 8080
Python wrapper exposes it via Modal's web endpoint
"""

import modal

APP_NAME = "tei-embedding-service"
app = modal.App(APP_NAME)

# Build image: Start with TEI, add Python layer (no model download)
tei_image = (
    modal.Image.from_registry(
        "ghcr.io/huggingface/text-embeddings-inference:1.7.2"
    )
    # Clear the entrypoint so Modal can run Python
    .dockerfile_commands("ENTRYPOINT []")
    # Install Python for Modal's wrapper
    .apt_install("python3", "python3-pip", "git")
    .run_commands("ln -s /usr/bin/python3 /usr/bin/python")
    .pip_install("fastapi", "requests", "huggingface-hub")
)

# Model storage volume - persistent across deployments
model_volume = modal.Volume.from_name("tei-models", create_if_missing=True)
MODEL_CACHE = "/data"  # TEI's default HuggingFace cache location

@app.cls(
    gpu="A100",  # A100 = compute cap 8.0 (compatible with TEI 1.7.2 build)
    image=tei_image,
    volumes={MODEL_CACHE: model_volume},
    container_idle_timeout=300,  # Scale down after 5 min idle
    timeout=3600,
    allow_concurrent_inputs=100,
    max_containers=3,  # Limit to 3 GPUs (10 GPU total / 3 services)
)
class TEIEmbeddingService:
    """TEI service with Python wrapper for Modal"""

    @modal.enter()
    def start_tei(self):
        """Download model to volume if needed, then start TEI server"""
        import subprocess
        import time
        import requests
        from pathlib import Path
        from huggingface_hub import snapshot_download

        self.model_name = "Qwen/Qwen3-Embedding-8B"
        # HuggingFace cache structure: models--<org>--<name>
        self.model_cache_path = f"{MODEL_CACHE}/models--Qwen--Qwen3-Embedding-8B"

        # Check if model is cached in volume
        if Path(self.model_cache_path).exists():
            print("📦 Model found in Modal volume cache")
        else:
            print("⬇️ Model not in cache, downloading 15.5GB to volume...")
            print(f"   Target: {self.model_cache_path}")
            print("   Note: Qwen3-Embedding-8B uses sharded safetensors (6 files)")
            print("   Ignoring 404 warning for model.safetensors - this is expected")

            # Download model to volume
            # Note: Qwen3-Embedding-8B uses sharded model format, not single model.safetensors
            # snapshot_download will automatically download all required files
            snapshot_download(
                repo_id=self.model_name,
                cache_dir=MODEL_CACHE,
                local_files_only=False,
                ignore_patterns=["*.msgpack", "*.h5"],  # Skip unnecessary file formats
            )

            # Commit to volume (critical for persistence)
            print("💾 Committing model to volume...")
            model_volume.commit()
            print("✅ Model cached successfully!")

        print("🚀 Starting TEI server...")

        # Start TEI as background process
        # Note: We cleared ENTRYPOINT, so we call the binary directly
        self.tei_process = subprocess.Popen([
            "/usr/local/bin/text-embeddings-router",
            "--model-id", self.model_name,
            "--port", "8080",
            "--hostname", "0.0.0.0",
            "--max-concurrent-requests", "512",
            "--max-batch-tokens", "30000",
            "--max-batch-requests", "256",
            "--max-client-batch-size", "100",
            "--pooling", "mean",
            "--dtype", "float16",
            "--auto-truncate",  # Model max length (32768) used automatically
            "--huggingface-hub-cache", MODEL_CACHE,
        ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream logs in background
        import threading
        def log_tei():
            for line in self.tei_process.stdout:
                print(f"[TEI] {line.rstrip()}")

        log_thread = threading.Thread(target=log_tei, daemon=True)
        log_thread.start()

        # Wait for TEI to be ready (GPU load, much faster now that model is cached)
        print("⏳ Waiting for TEI startup (loading model to GPU)...")
        max_wait = 300  # 5 minutes

        for i in range(max_wait):
            try:
                resp = requests.get("http://localhost:8080/health", timeout=2)
                if resp.status_code == 200:
                    print(f"✅ TEI ready after {i}s")

                    # Get model info
                    info = requests.get("http://localhost:8080/info").json()
                    print(f"📊 Model: {info.get('model_id')}")
                    print(f"📊 Max tokens: {info.get('max_input_length')}")
                    print(f"📊 Tokenizer: {info.get('tokenizer_name')}")
                    return
            except:
                if i % 10 == 0 and i > 0:
                    print(f"⏳ {i}s elapsed...")
                time.sleep(1)

        raise RuntimeError(f"TEI failed to start within {max_wait}s")

    @modal.web_endpoint(method="POST", label="embed")
    def embed(self, request: dict):
        """
        Forward embedding requests to TEI

        Request: {"texts": ["text1", "text2"], "model": "..."}
        Response: {"results": [{"embedding": [...], "success": true}, ...]}
        """
        import requests
        import time

        texts = request.get("texts", [])
        if not texts:
            return {"error": "No texts provided"}

        start = time.time()

        try:
            # Forward to TEI (TEI expects {"inputs": [...]})
            response = requests.post(
                "http://localhost:8080/embed",
                json={"inputs": texts},
                timeout=180  # Increased from 60s to 180s to handle larger batches
            )

            if response.status_code == 200:
                # TEI returns array of embeddings directly
                embeddings = response.json()

                # Format to match your existing API
                results = []
                for emb in embeddings:
                    # Validate and clean embedding values
                    # TEI sometimes returns None at specific positions (2109, 2284)
                    validated_emb = []
                    for val in emb:
                        if val is None or (isinstance(val, float) and not (val == val)):  # None or NaN
                            validated_emb.append(0.0)
                        elif isinstance(val, (int, float)):
                            # Ensure finite values
                            import math
                            if not math.isfinite(val):
                                validated_emb.append(0.0)
                            else:
                                validated_emb.append(float(val))
                        else:
                            # Invalid type, replace with 0.0
                            validated_emb.append(0.0)

                    results.append({
                        "embedding": validated_emb,
                        "model": "Qwen/Qwen3-Embedding-8B",
                        "dimensions": len(validated_emb),
                        "success": True,
                        "backend": "TEI"
                    })

                elapsed = (time.time() - start) * 1000
                print(f"✅ Embedded {len(texts)} texts in {elapsed:.1f}ms")

                return {
                    "results": results,
                    "batch_size": len(texts),
                    "model": "qwen3-embedding-8b",
                    "total_request_time_ms": elapsed,
                    "backend": "TEI"
                }
            else:
                return {
                    "error": f"TEI returned HTTP {response.status_code}",
                    "details": response.text
                }

        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

    @modal.web_endpoint(method="GET", label="health")
    def health(self):
        """Health check endpoint"""
        import requests

        try:
            # Check TEI health
            tei_health = requests.get("http://localhost:8080/health", timeout=2)
            tei_info = requests.get("http://localhost:8080/info", timeout=2)

            return {
                "status": "healthy" if tei_health.status_code == 200 else "unhealthy",
                "tei_info": tei_info.json() if tei_info.status_code == 200 else {},
                "backend": "TEI"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
