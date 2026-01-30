"""
NuExtract-2.0-8B Service on Modal

Deploys NuExtract-2.0-8B for structured information extraction from text/images.
Supports JSON-based extraction with custom templates.

Architecture:
- Uses vLLM for efficient inference (text mode)
- Runs on H100 GPU (multimodal 8B model)
- Persistent model caching via Modal Volume
- Web endpoint for HTTP requests
"""

# ============================================================================
# CRITICAL: Force vLLM v0 engine BEFORE any imports
# vLLM v1 has bugs with multimodal models - must use v0
# ============================================================================
import os
os.environ["VLLM_USE_V1"] = "0"  # Disable buggy v1 engine

import modal

APP_NAME = "nuextract-service"
app = modal.App(APP_NAME)

# Build image with vLLM nightly (same as DeepSeek OCR)
# vLLM 0.11.0 has bugs with V0/V1 engine switching - use nightly instead
nuextract_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        # Vision/Image processing
        "pillow",
        "requests",
    )
    .run_commands(
        # Install vLLM nightly with proper indices (matches DeepSeek OCR setup)
        "pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly --extra-index-url https://download.pytorch.org/whl/cu129"
    )
    # Set engine environment variable in image
    .env({
        "VLLM_USE_V1": "0",  # Force v0 engine (v1 has multimodal bugs)
        "TORCH_COMPILE": "0",  # Disable unsupported torch.compile
    })
)

# Model storage volume
model_volume = modal.Volume.from_name("nuextract-models", create_if_missing=True)
MODEL_CACHE = "/models"

@app.cls(
    gpu="H100",  # H100 for multimodal 8B model
    image=nuextract_image,
    volumes={MODEL_CACHE: model_volume},
    scaledown_window=300,  # Keep warm for 5 minutes (newer Modal API)
    timeout=300,  # 5 minute timeout (reasonable for extraction workloads)
    max_containers=3,  # Limit to 3 GPUs (10 GPU total / 3 services)
)
@modal.concurrent(max_inputs=80)  # Let vLLM handle batching internally
class NuExtractService:
    """NuExtract service for structured information extraction"""

    @modal.enter()
    def load_model(self):
        """Download model and initialize vLLM engine"""
        import os
        from pathlib import Path
        from huggingface_hub import snapshot_download
        from vllm import LLM

        self.model_name = "numind/NuExtract-2.0-8B"
        model_cache_path = f"{MODEL_CACHE}/models--numind--NuExtract-2.0-8B"

        # Download model if not cached
        if not Path(model_cache_path).exists():
            print(f"⬇️ Downloading {self.model_name} (8B params)...")
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

        # Initialize vLLM engine with conservative configuration
        # Use vLLM defaults for batching (auto-calculated from available memory)
        # Only override essential params + prefix caching for template reuse
        print("🚀 Loading model into vLLM...")
        self.llm = LLM(
            model=self.model_name,
            download_dir=MODEL_CACHE,
            trust_remote_code=True,
            dtype="bfloat16",
            max_model_len=8192,
            gpu_memory_utilization=0.85,          # Safer for multimodal (images need headroom)
            enable_prefix_caching=True,           # Reuse template prefixes across requests
        )
        print("✅ NuExtract-2.0-8B vLLM v0 engine ready!")
        print("=" * 80)
        print(f"🔧 Configuration:")
        print(f"   - Engine: vLLM v0 (VLLM_USE_V1=0)")
        print(f"   - GPU memory: 85% utilization")
        print(f"   - Prefix caching: Enabled")
        print(f"   - Context window: 8192 tokens")
        print(f"   - Max output: 4096 tokens (SEC-optimized)")
        print("=" * 80)

    @modal.fastapi_endpoint(method="POST", label="extract")
    def extract(self, request: dict):
        """
        Extract structured information using JSON template

        Request: {
            "text": "The contract was signed on 2024-01-15...",  # OR
            "image_url": "https://...",  # For multimodal mode
            "image_base64": "data:image/png;base64,...",  # For multimodal mode
            "template": {
                "date": "",
                "parties": [],
                "amount": 0
            },
            "temperature": 0.0  # optional, default 0.0 for precise extraction
        }
        Response: {
            "extracted_data": { /* JSON matching template */ },
            "model": "numind/NuExtract-2.0-8B",
            "success": true
        }
        """
        import time
        import json
        import base64
        import requests
        from io import BytesIO
        from PIL import Image
        from vllm import SamplingParams

        start = time.time()

        # Extract request parameters
        text = request.get("text")
        image_url = request.get("image_url")
        image_base64 = request.get("image_base64")
        template = request.get("template")
        temperature = request.get("temperature", 0.0)

        if not template:
            return {"error": "No template provided", "success": False}

        if not text and not image_url and not image_base64:
            return {"error": "No text or image provided", "success": False}

        try:
            # Build prompt with template
            template_str = json.dumps(template, indent=2)

            if text:
                # Text-only mode with strict JSON-only output enforcement
                prompt = f"""<|input|>
You are an extraction engine.
You MUST respond with a single JSON object that matches the template exactly.
Do NOT include any explanations, markdown, or extra text, ONLY JSON.

### Template:
```json
{template_str}
```

### Text:
{text}
<|output|>
"""
                # Prepare sampling parameters
                # Higher token limit for SEC documents (complex financial tables)
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=4096,  # Increased for complex tables and financial data
                    top_p=0.95,
                )

                # Process with vLLM (text mode)
                outputs = self.llm.generate(prompt, sampling_params=sampling_params)
                output_text = outputs[0].outputs[0].text.strip()

            else:
                # Multimodal mode with comprehensive image validation
                image, img_error = self._load_and_validate_image(image_url, image_base64)
                if img_error:
                    return img_error

                # Multimodal mode with strict JSON-only output enforcement
                prompt = f"""<|vision_start|><|image_pad|><|vision_end|><|input|>
You are an extraction engine.
You MUST respond with a single JSON object that matches the template exactly.
Do NOT include any explanations, markdown, or extra text, ONLY JSON.

### Template:
```json
{template_str}
```

Extract information from the image above.
<|output|>
"""

                # Prepare sampling parameters
                # Higher token limit for SEC documents (complex financial tables)
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=4096,  # Increased for complex tables and financial data
                    top_p=0.95,
                )

                # Process with vLLM (multimodal mode)
                outputs = self.llm.generate(
                    {
                        "prompt": prompt,
                        "multi_modal_data": {"image": image},
                    },
                    sampling_params=sampling_params,
                )
                output_text = outputs[0].outputs[0].text.strip()

            # Parse JSON output with robust multi-stage fallback
            extracted_data, parse_error = self._extract_json(output_text)

            elapsed = (time.time() - start) * 1000

            print(f"✅ Extracted data in {elapsed:.1f}ms")

            result = {
                "extracted_data": extracted_data,
                "model": self.model_name,
                "processing_time_ms": elapsed,
                "template": template,
                "success": True,
                "backend": "vLLM"
            }

            # Add parse error as warning if present (non-fatal)
            if parse_error:
                result["_parse_warning"] = parse_error
                result["_raw_output"] = output_text[:500]  # Truncated for debugging

            return result

        except Exception as e:
            import traceback
            error_msg = f"Extraction failed: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())

            return {
                "error": error_msg,
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "success": False
            }

    def _load_and_validate_image(self, image_url: str = None, image_base64: str = None):
        """
        Load and validate image with size limits and format checks.

        For SEC documents, we use higher resolution limits to preserve
        table and financial data quality.

        Returns:
            (image, error_dict) tuple. error_dict is None on success.
        """
        from PIL import Image
        from io import BytesIO
        import requests
        import base64

        # Higher resolution for SEC documents (tables, fine print)
        MAX_SIZE = 2048  # Increased from 1536 for financial document quality

        try:
            # Load image
            if image_url:
                try:
                    response = requests.get(image_url, timeout=10, stream=True)
                    response.raise_for_status()

                    # Check content length if available
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB limit
                        return None, {
                            "error": f"Image too large: {int(content_length) / 1024 / 1024:.1f}MB (max 50MB)",
                            "error_type": "ImageTooLargeError",
                            "success": False,
                        }

                    image = Image.open(BytesIO(response.content))

                except requests.RequestException as e:
                    return None, {
                        "error": f"Failed to fetch image: {e}",
                        "error_type": "ImageFetchError",
                        "success": False,
                    }

            elif image_base64:
                # Handle data URL format
                if image_base64.startswith("data:"):
                    image_base64 = image_base64.split(",", 1)[1]

                try:
                    image_data = base64.b64decode(image_base64)
                    image = Image.open(BytesIO(image_data))
                except Exception as e:
                    return None, {
                        "error": f"Failed to decode image: {e}",
                        "error_type": "ImageDecodeError",
                        "success": False,
                    }

            # Convert to RGB (required for most models)
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Resize if too large (preserves aspect ratio)
            if max(image.size) > MAX_SIZE:
                original_size = image.size
                image.thumbnail((MAX_SIZE, MAX_SIZE))
                print(f"ℹ️  Resized image from {original_size} to {image.size} (max {MAX_SIZE}px)")

            return image, None

        except Exception as e:
            return None, {
                "error": f"Image processing failed: {e}",
                "error_type": type(e).__name__,
                "success": False,
            }

    def _extract_json(self, output_text: str):
        """
        Robust JSON extraction with multi-stage fallback chain.

        Returns:
            (extracted_dict, error_string) tuple. error_string is None on success.
        """
        import json
        import re

        # Stage 1: Try direct JSON parse (fast path)
        try:
            return json.loads(output_text), None
        except json.JSONDecodeError:
            pass

        # Stage 2: Strip code fences if present
        fenced = output_text
        if "```json" in fenced:
            fenced = fenced.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in fenced:
            fenced = fenced.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            return json.loads(fenced), None
        except json.JSONDecodeError:
            pass

        # Stage 3: Regex extraction of first {...} block
        match = re.search(r"\{.*\}", output_text, re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError as e:
                # Failed all parsing attempts
                return {
                    "raw_output": output_text,
                    "_extraction_failed": True,
                }, f"JSONDecodeError: {str(e)}"

        # Stage 4: Complete failure - return raw output
        return {
            "raw_output": output_text,
            "_extraction_failed": True,
        }, "No valid JSON object found in model output"

    @modal.fastapi_endpoint(method="GET", label="nuextract-health")
    def health(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "model": "numind/NuExtract-2.0-8B",
            "parameters": "8B",
            "capabilities": ["text", "multimodal"],
            "backend": "vLLM"
        }