"""
DeepSeek-OCR Service on Modal (Official vLLM Upstream Integration)

Uses the official upstream vLLM integration (built-in as of vLLM nightly).
Reference: https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-OCR.html

Performance (vLLM nightly with built-in support):
- Hardware: NVIDIA H100 GPU (80GB HBM3)
- Throughput: ~3-5 pages/second per H100 (sequential processing)
- Latency: ~200-350ms per page (faster than A100)
- Memory: 72GB utilization (90% of 80GB)
- Continuous batching: Up to 100 concurrent user requests
"""

import os
import modal

APP_NAME = "deepseek-ocr"
app = modal.App(APP_NAME)

# Build image with vLLM nightly (includes DeepSeek-OCR support)
vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "poppler-utils")
    .pip_install(
        # Vision/PDF processing
        "pillow",
        "pdf2image",
        "pypdfium2",
        "PyMuPDF",  # fitz for PDF processing

        # API and utils
        "fastapi",
        "requests",
        "tqdm",
        "numpy",
    )
    .run_commands(
        # Install vLLM nightly with BOTH indices (from GitHub issue #28030)
        # Must include PyTorch CUDA wheels index for proper dependency resolution
        "pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly --extra-index-url https://download.pytorch.org/whl/cu129"
    )
)

# Model storage volume
model_volume = modal.Volume.from_name("deepseek-ocr-vllm-models", create_if_missing=True)
MODEL_CACHE = "/models"

@app.cls(
    gpu="H100",
    image=vllm_image,
    volumes={MODEL_CACHE: model_volume},
    scaledown_window=300,
    timeout=3600,
    max_containers=5,
)
@modal.concurrent(max_inputs=256)
class DeepSeekOCRVLLMService:
    """DeepSeek-OCR service using official vLLM upstream integration"""

    @modal.enter()
    def load_model(self):
        """Load DeepSeek-OCR model with official vLLM API"""
        from pathlib import Path

        # Set cache directories
        os.environ["HF_HOME"] = MODEL_CACHE
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE
        os.environ["HF_DATASETS_CACHE"] = MODEL_CACHE

        print("📦 Loading DeepSeek-OCR with official vLLM upstream integration...")

        # Import official vLLM components (built-in support)
        from vllm import LLM, SamplingParams
        from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor
        from PIL import Image

        self.model_name = "deepseek-ai/DeepSeek-OCR"
        model_cache_path = Path(MODEL_CACHE) / "models--deepseek-ai--DeepSeek-OCR"

        # Initialize vLLM engine (official upstream API)
        # Optimized for H100 throughput with batching
        os.environ["TORCH_COMPILE"] = "0"  # Disable unsupported torch.compile
        os.environ["VLLM_USE_V1"] = "0"  # Disable v1 engine (has bugs with concurrent multimodal requests)

        self.llm = LLM(
            model=self.model_name,
            enable_prefix_caching=False,
            mm_processor_cache_gb=0,
            logits_processors=[NGramPerReqLogitsProcessor],
            trust_remote_code=True,
            max_model_len=8192,
            max_num_seqs=100,
            max_num_batched_tokens=100000,  # Enable aggressive batching for H100
            tensor_parallel_size=1,
            gpu_memory_utilization=0.9,
            download_dir=MODEL_CACHE,
        )

        # Sampling parameters (deterministic for OCR)
        # Reduced max_tokens from 8192 to 2048 - typical pages are much shorter
        self.sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=2048,  # Reduced from 8192 - huge latency win
            # NGram logit processor args (passed to NGramPerReqLogitsProcessor)
            extra_args=dict(
                ngram_size=30,
                window_size=60,  # Reduced from 90 for speed
                whitelist_token_ids={128821, 128822},  # <td>, </td>
            ),
            skip_special_tokens=False,
            include_stop_str_in_output=True,
        )

        # Commit cache if fresh download
        if not model_cache_path.exists() or len(list(model_cache_path.glob("*"))) < 5:
            print("💾 Committing model to volume...")
            model_volume.commit()

        print("✅ DeepSeek-OCR vLLM ready (official upstream)!")
        print(f"   Hardware: NVIDIA H100 GPU (80GB HBM3)")
        print(f"   Backend: vLLM nightly with built-in DeepSeek-OCR")
        print(f"   Max concurrent: 100 user requests")
        print(f"   GPU utilization: 90%")
        print(f"   Expected: 3-5 pages/sec (sequential per GPU)")

    @modal.fastapi_endpoint(method="POST", label="ocr-process")
    def process_image(self, request: dict):
        """
        Process image/PDF using official vLLM upstream API

        Request: {
            "pdf_base64": "base64...",  # Base64 PDF
            "prompt": "<image>\\n<|grounding|>Convert to markdown",
            "page_num": null  # Process all pages if null
        }

        Response: {
            "text": "extracted text",
            "model": "deepseek-ai/DeepSeek-OCR",
            "backend": "vllm-official",
            "processing_time_ms": 123.4,
            "pages_processed": 10,
            "throughput_pages_per_sec": 81.3,
            "success": true
        }
        """
        import time
        import base64
        from PIL import Image
        from io import BytesIO

        start = time.time()

        # Extract parameters
        pdf_base64 = request.get("pdf_base64")
        prompt = request.get("prompt", "<image>\n<|grounding|>Convert the document to markdown.")
        page_num = request.get("page_num")

        try:
            if not pdf_base64:
                return {"error": "pdf_base64 required", "success": False}

            # Decode PDF
            pdf_data = base64.b64decode(pdf_base64)

            # Convert PDF to images using PyMuPDF (fitz)
            import fitz
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

            # Process specific page or all pages
            if page_num is not None:
                if page_num < 1 or page_num > pdf_document.page_count:
                    return {
                        "error": f"Invalid page_num: {page_num} (PDF has {pdf_document.page_count} pages)",
                        "success": False
                    }
                page_indices = [page_num - 1]
            else:
                page_indices = list(range(pdf_document.page_count))

            num_pages = len(page_indices)
            print(f"📄 Processing {num_pages} page(s) with official vLLM API...")

            # Convert pages to PIL images
            # Using 108 DPI (zoom=1.5) instead of 144 DPI - faster with minimal quality loss
            images = []
            for page_num_idx in page_indices:
                page = pdf_document[page_num_idx]
                zoom = 1.5  # 108 DPI (reduced from 144 DPI for speed)
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                img_data = pixmap.tobytes("png")
                img = Image.open(BytesIO(img_data)).convert("RGB")
                images.append(img)

            pdf_document.close()

            # Prepare batch inputs (official API format)
            model_inputs = []
            for img in images:
                model_inputs.append({
                    "prompt": prompt,
                    "multi_modal_data": {"image": img}
                })

            print(f"⚡ Running vLLM inference on {num_pages} pages...")

            # Run vLLM inference (continuous batching)
            outputs = self.llm.generate(model_inputs, self.sampling_params)

            # Extract results
            all_results = []
            for output in outputs:
                text = output.outputs[0].text if output.outputs else ""
                all_results.append(text)

            # Combine results
            if len(all_results) > 1:
                extracted_text = "\n\n---PAGE BREAK---\n\n".join(all_results)
            else:
                extracted_text = all_results[0] if all_results else ""

            elapsed = (time.time() - start) * 1000
            throughput = num_pages / (elapsed / 1000) if elapsed > 0 else 0

            print(f"✅ Processed {num_pages} pages in {elapsed:.1f}ms")
            print(f"📈 Throughput: {throughput:.2f} pages/sec")

            return {
                "text": extracted_text,
                "model": self.model_name,
                "backend": "vllm-official-upstream",
                "processing_time_ms": elapsed,
                "pages_processed": num_pages,
                "throughput_pages_per_sec": throughput,
                "success": True,
            }

        except Exception as e:
            import traceback
            return {
                "error": f"Processing failed: {str(e)}",
                "traceback": traceback.format_exc(),
                "success": False,
                "backend": "vllm-official-upstream"
            }

    @modal.fastapi_endpoint(method="GET", label="ocr-health")
    def health(self):
        """Health check"""
        return {
            "status": "healthy",
            "model": "deepseek-ai/DeepSeek-OCR",
            "hardware": "NVIDIA H100 (80GB HBM3)",
            "backend": "vllm-official-upstream",
            "parameters": "3B",
            "max_concurrent": 100,
            "gpu_utilization": 0.9,
            "expected_throughput": "3-5 pages/sec per GPU (sequential)",
            "note": "Use client-side parallelization to utilize multiple GPUs"
        }
