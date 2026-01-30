"""
NuExtract-2.0-8B Service on Modal

Deploys NuExtract-2.0-8B for structured information extraction from text/images.
Supports JSON-based extraction with custom templates.

Architecture:
- Uses vLLM for efficient inference (text mode)
- Runs on A100 GPU (multimodal 8B model)
- Persistent model caching via Modal Volume
- Web endpoint for HTTP requests
"""

import modal

APP_NAME = "nuextract-service"
app = modal.App(APP_NAME)

# Build image with vLLM and model dependencies
# Note: Qwen2.5-VL support requires vLLM >= 0.10.2 and transformers >= 4.50.0
nuextract_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.11.0",  # Latest with Qwen2.5-VL data parallel support
        "torch==2.8.0",  # Required by vLLM 0.11.0
        "transformers==4.57.1",  # Latest with full Qwen2.5-VL support
        "pillow==11.0.0",
        "requests==2.32.3",
    )
)

# Model storage volume
model_volume = modal.Volume.from_name("nuextract-models", create_if_missing=True)
MODEL_CACHE = "/models"

@app.cls(
    gpu="H100",  # A100 for multimodal 8B model
    image=nuextract_image,
    volumes={MODEL_CACHE: model_volume},
    container_idle_timeout=300,  # Scale down after 5 min idle
    timeout=3600,
    allow_concurrent_inputs=10,
    max_containers=1,  # Limit to 3 GPUs (10 GPU total / 3 services)
)
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

        # Initialize vLLM engine
        print("🚀 Loading model into vLLM...")
        self.llm = LLM(
            model=self.model_name,
            download_dir=MODEL_CACHE,
            trust_remote_code=True,
            dtype="bfloat16",
            max_model_len=8192,
            gpu_memory_utilization=0.9,
        )
        print("✅ NuExtract-2.0-8B ready!")

    @modal.web_endpoint(method="POST", label="extract")
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
                # Text-only mode
                prompt = f"""<|input|>
### Template:
```json
{template_str}
```

### Text:
{text}
<|output|>
"""
                # Prepare sampling parameters
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=2048,
                    top_p=0.95,
                )

                # Process with vLLM (text mode)
                outputs = self.llm.generate(prompt, sampling_params=sampling_params)
                output_text = outputs[0].outputs[0].text.strip()

            else:
                # Multimodal mode
                if image_url:
                    response = requests.get(image_url, timeout=30)
                    image = Image.open(BytesIO(response.content))
                elif image_base64:
                    if image_base64.startswith("data:"):
                        image_base64 = image_base64.split(",", 1)[1]
                    image_data = base64.b64decode(image_base64)
                    image = Image.open(BytesIO(image_data))

                # Convert to RGB if needed
                if image.mode != "RGB":
                    image = image.convert("RGB")

                prompt = f"""<|vision_start|><|image_pad|><|vision_end|><|input|>
### Template:
```json
{template_str}
```

Extract information from the image above.
<|output|>
"""

                # Prepare sampling parameters
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=2048,
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

            # Parse JSON output
            try:
                # Extract JSON from output (handle markdown code blocks)
                if "```json" in output_text:
                    json_str = output_text.split("```json")[1].split("```")[0].strip()
                elif "```" in output_text:
                    json_str = output_text.split("```")[1].split("```")[0].strip()
                else:
                    json_str = output_text

                extracted_data = json.loads(json_str)
            except json.JSONDecodeError:
                # Return raw output if JSON parsing fails
                extracted_data = {"raw_output": output_text}

            elapsed = (time.time() - start) * 1000

            print(f"✅ Extracted data in {elapsed:.1f}ms")

            return {
                "extracted_data": extracted_data,
                "model": self.model_name,
                "processing_time_ms": elapsed,
                "template": template,
                "success": True,
                "backend": "vLLM"
            }

        except Exception as e:
            return {
                "error": f"Extraction failed: {str(e)}",
                "success": False
            }

    @modal.web_endpoint(method="GET", label="nuextract-health")
    def health(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "model": "numind/NuExtract-2.0-8B",
            "parameters": "8B",
            "capabilities": ["text", "multimodal"],
            "backend": "vLLM"
        }