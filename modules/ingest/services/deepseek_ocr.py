"""
DeepSeek-OCR Single GPU Service (1:1 Endpoint-to-GPU)

Single endpoint for validation and benchmarking.
After validating performance, deploy 5 separate endpoints for parallel processing.

Architecture:
- 1 Modal endpoint → 1 H100 GPU → max_containers=1
- Client-side load balancing across multiple endpoints
- Predictable performance without cold starts

Target Performance:
- 3-5 pages/second per H100 (sequential processing)
- ~200-350ms latency per page
- 72GB GPU memory utilization (90% of 80GB)

Usage:
    # Deploy single endpoint
    modal deploy modules/ingest/services/deepseek_ocr_single.py

    # Test with benchmark script
    python benchmark_ocr_single.py
"""

# ============================================================================
# CRITICAL: Force vLLM v0 engine BEFORE any imports
# Must be at top of file to prevent v1 engine initialization bugs
# ============================================================================
import os
#os.environ["VLLM_USE_V1"] = "0"  # Disable buggy v1 engine
os.environ["TORCH_COMPILE"] = "0"  # Disable unsupported torch.compile

import modal

APP_NAME = "deepseek-ocr-single"
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
    # Set engine environment variables in image
    .env({
        "VLLM_USE_V1": "0",
        "TORCH_COMPILE": "0",
    })
)

# Model storage volume
model_volume = modal.Volume.from_name("deepseek-ocr-vllm-models", create_if_missing=True)
MODEL_CACHE = "/models"

@app.cls(
    gpu="H100",
    image=vllm_image,
    volumes={MODEL_CACHE: model_volume},
    scaledown_window=300,  # Keep warm for 5 minutes
    timeout=3600,
    max_containers=1,  # Single container for testing
)
@modal.concurrent(max_inputs=32)  # Moderate concurrency for single GPU
class DeepSeekOCRSingleGPU:
    """DeepSeek-OCR service on single H100 GPU for validation"""

    @modal.enter()
    def load_model(self):
        """Load DeepSeek-OCR model with official vLLM API (v0 engine)"""
        from pathlib import Path

        # Set cache directories
        os.environ["HF_HOME"] = MODEL_CACHE
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE
        os.environ["HF_DATASETS_CACHE"] = MODEL_CACHE

        print("=" * 80)
        print("📦 Loading DeepSeek-OCR with vLLM v0 engine...")
        print("=" * 80)

        # Import official vLLM components (built-in support)
        from vllm import LLM, SamplingParams
        from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor
        from PIL import Image

        self.model_name = "deepseek-ai/DeepSeek-OCR"
        model_cache_path = Path(MODEL_CACHE) / "models--deepseek-ai--DeepSeek-OCR"

        # Initialize vLLM engine (v0 engine forced at file top)
        # Optimized for H100 throughput with batching
        self.llm = LLM(
            model=self.model_name,
            enable_prefix_caching=False,
            mm_processor_cache_gb=0,
            logits_processors=[NGramPerReqLogitsProcessor],
            trust_remote_code=True,
            max_model_len=8192,
            max_num_seqs=100,  # Support batching up to 100 pages
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

        print("=" * 80)
        print("✅ DeepSeek-OCR vLLM v0 engine ready!")
        print("=" * 80)
        print(f"🔧 Configuration:")
        print(f"   - Hardware: NVIDIA H100 GPU (80GB HBM3)")
        print(f"   - Engine: vLLM v0 (VLLM_USE_V1=0)")
        print(f"   - Backend: vLLM nightly with built-in DeepSeek-OCR")
        print(f"   - Max batch size: 100 pages")
        print(f"   - GPU utilization: 90%")
        print(f"   - Max tokens: 2048 per page")
        print(f"📊 Expected Performance:")
        print(f"   - Sequential: 3-5 pages/sec")
        print(f"   - Latency: 200-350ms per page")
        print(f"   - Batch mode: ~10-15 pages/sec (100 page batch)")
        print("=" * 80)

    @modal.method()
    def process_pdf(self, pdf_base64: str, prompt: str = None, page_num: int = None):
        """
        Process PDF using official vLLM upstream API

        Args:
            pdf_base64: Base64-encoded PDF
            prompt: OCR prompt (default: markdown conversion)
            page_num: Specific page number (1-indexed), None for all pages

        Returns:
            dict with text, processing stats, and success status
        """
        import time
        import base64
        from PIL import Image
        from io import BytesIO

        start = time.time()

        if prompt is None:
            prompt = "<image>\n<|grounding|>Convert the document to markdown."

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
            print(f"\n{'='*80}")
            print(f"📄 Processing {num_pages} page(s) with vLLM v0 engine")
            print(f"{'='*80}")

            # Convert pages to PIL images
            # Using 108 DPI (zoom=1.5) instead of 144 DPI - faster with minimal quality loss
            image_start = time.time()
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
            image_time = (time.time() - image_start) * 1000
            print(f"🖼️  Image conversion: {image_time:.1f}ms ({image_time/num_pages:.1f}ms per page)")

            # Prepare batch inputs (official API format)
            model_inputs = []
            for img in images:
                model_inputs.append({
                    "prompt": prompt,
                    "multi_modal_data": {"image": img}
                })

            # Run vLLM inference (continuous batching)
            print(f"⚡ Running vLLM inference on {num_pages} pages...")
            inference_start = time.time()
            outputs = self.llm.generate(model_inputs, self.sampling_params)
            inference_time = (time.time() - inference_start) * 1000

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

            print(f"{'='*80}")
            print(f"✅ Processing Complete")
            print(f"{'='*80}")
            print(f"📊 Performance Metrics:")
            print(f"   - Total time: {elapsed:.1f}ms")
            print(f"   - Image conversion: {image_time:.1f}ms ({image_time/elapsed*100:.1f}%)")
            print(f"   - vLLM inference: {inference_time:.1f}ms ({inference_time/elapsed*100:.1f}%)")
            print(f"   - Throughput: {throughput:.2f} pages/sec")
            print(f"   - Per-page latency: {elapsed/num_pages:.1f}ms")
            print(f"{'='*80}\n")

            return {
                "text": extracted_text,
                "model": self.model_name,
                "backend": "vllm-v0-engine",
                "processing_time_ms": elapsed,
                "image_conversion_ms": image_time,
                "inference_time_ms": inference_time,
                "pages_processed": num_pages,
                "throughput_pages_per_sec": throughput,
                "per_page_latency_ms": elapsed / num_pages,
                "success": True,
            }

        except Exception as e:
            import traceback
            error_msg = f"Processing failed: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())
            return {
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "success": False,
                "backend": "vllm-v0-engine"
            }

    @modal.method()
    def health_check(self):
        """Health check for monitoring"""
        return {
            "status": "healthy",
            "model": "deepseek-ai/DeepSeek-OCR",
            "hardware": "NVIDIA H100 (80GB HBM3)",
            "backend": "vllm-v0-engine",
            "engine": "v0 (VLLM_USE_V1=0)",
            "parameters": "3B",
            "max_batch_size": 100,
            "gpu_utilization": 0.9,
            "expected_throughput": "3-5 pages/sec (sequential), 10-15 pages/sec (batch)",
            "deployment": "single-gpu-1to1"
        }


@app.local_entrypoint()
def main():
    """Test single GPU endpoint locally"""
    import base64

    # Test with a simple PDF (you'll need to provide one)
    print("🧪 Testing DeepSeek-OCR Single GPU Endpoint")
    print("=" * 80)

    # Load test PDF
    test_pdf_path = "test.pdf"  # Replace with actual test PDF

    try:
        with open(test_pdf_path, "rb") as f:
            pdf_bytes = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode()

        print(f"📄 Loaded test PDF: {test_pdf_path}")

        # Run health check
        service = DeepSeekOCRSingleGPU()
        health = service.health_check.remote()
        print(f"✅ Health check: {health}")

        # Process PDF
        print("\n⚡ Processing PDF...")
        result = service.process_pdf.remote(pdf_base64)

        if result["success"]:
            print(f"\n✅ Success!")
            print(f"📊 Pages processed: {result['pages_processed']}")
            print(f"⏱️  Total time: {result['processing_time_ms']:.1f}ms")
            print(f"📈 Throughput: {result['throughput_pages_per_sec']:.2f} pages/sec")
            print(f"\n📝 Extracted text (first 500 chars):")
            print(result['text'][:500])
        else:
            print(f"\n❌ Failed: {result.get('error')}")

    except FileNotFoundError:
        print(f"❌ Test PDF not found: {test_pdf_path}")
        print("   Create a test PDF or update test_pdf_path in main()")
