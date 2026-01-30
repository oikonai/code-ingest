# Modal Services Documentation

> **Last Updated:** 2025-11-03
> **File Reference:** `modules/ingest/services/`

## Overview

I2P uses Modal.com for serverless ML model deployments. This provides GPU-accelerated inference without infrastructure management, with automatic scaling and cost optimization.

## Services Architecture

### 1. TEI Embedding Service (Qwen3-Embedding-8B)

**Purpose:** Generate high-quality embeddings for semantic search

- **File:** `modules/ingest/services/tei_service.py`
- **Client:** `modules/ingest/services/modal_client.py`
- **Model:** Qwen/Qwen3-Embedding-8B
- **Parameters:** 8 billion (8B)
- **Architecture:** Transformer encoder (embedding-optimized)
- **Output Dimensions:** 8,192
- **Context Window:** 32,768 tokens (auto-truncate)
- **Precision:** float16 (FP16)
- **GPU:** NVIDIA A100 (80GB)
- **Backend:** HuggingFace TEI 1.7.2

**Use Cases:**
- Code chunk embedding for vector search
- Documentation semantic indexing
- Query embedding for retrieval

**API Example:**
```python
from modules.ingest.services.modal_client import ModalEmbeddingClient

client = ModalEmbeddingClient(
    modal_endpoint=os.getenv('MODAL_ENDPOINT')
)

response = client.create_embedding(
    text="fn main() { println!(\"Hello\"); }",
    chunk_id="rust-001"
)

if response.success:
    embedding = response.embedding  # 4096D vector
    print(f"Dimensions: {response.dimensions}")
```

### 2. DeepSeek-OCR Service (3B)

**Purpose:** Convert document images to text/markdown

- **File:** `modules/ingest/services/deepseek_ocr_service.py`
- **Client:** `modules/ingest/services/deepseek_ocr_client.py`
- **Model:** deepseek-ai/DeepSeek-OCR
- **Parameters:** 3 billion (3B)
- **Architecture:** Vision Transformer with OCR head
- **Precision:** float16 (FP16)
- **GPU:** NVIDIA A10G
- **Input:** Images (URL or base64), PDFs
- **Output:** Extracted text/markdown with grounding annotations
- **Backend:** Transformers 4.46.3

**Use Cases:**
- Document digitization
- Diagram text extraction
- Screenshot OCR
- PDF page processing

**API Example:**
```python
from modules.ingest.services.deepseek_ocr_client import DeepSeekOCRClient

client = DeepSeekOCRClient(
    modal_endpoint=os.getenv('DEEPSEEK_OCR_ENDPOINT')
)

response = client.process_image(
    image_url="https://example.com/document.png",
    prompt="<image>\n<|grounding|>Convert to markdown",
    mode="large"  # Options: tiny, small, base, large
)

if response.success:
    text = response.text
    print(f"Extracted: {text}")
```

### 3. NuExtract Service (8B)

**Purpose:** Structured information extraction from text/images using JSON templates

- **File:** `modules/ingest/services/nuextract_service.py`
- **Client:** `modules/ingest/services/nuextract_client.py`
- **Model:** numind/NuExtract-2.0-8B
- **Architecture:** Qwen2.5-VL (Vision-Language multimodal)
- **Parameters:** 8 billion (8B)
- **Context Window:** 8,192 tokens
- **Precision:** bfloat16 (Brain Floating Point 16-bit)
- **GPU:** NVIDIA A100 (80GB)
- **Input:** Text or images + JSON template
- **Output:** Structured JSON data matching template schema
- **Backend:** vLLM 0.11.0 (multimodal support)

**Performance:**
- **Latency:** ~0.9-1.5s per extraction (warm)
- **Cold Start:** ~60-90s (first request)
- **Concurrent:** Up to 10 requests per container
- **Containers:** Max 3 containers

**Use Cases:**
- Issue/ticket parsing from text or screenshots
- Contract data extraction
- Form data extraction
- Structured code documentation extraction
- Any text-to-JSON conversion task

**API Example:**
```python
from modules.ingest.services.nuextract_client import NuExtractClient

client = NuExtractClient(
    modal_endpoint=os.getenv('NUEXTRACT_ENDPOINT')
)

# Extract from text
template = {
    "issue_type": "",
    "severity": "",
    "affected_component": "",
    "description": "",
    "action_items": []
}

response = client.extract_from_text(
    text="Critical bug in auth module causing crashes. High severity. Affects login component. Need to: 1) Rollback changes 2) Add error handling 3) Deploy hotfix",
    template=template,
    temperature=0.0  # 0.0 for deterministic extraction
)

if response.success:
    data = response.extracted_data
    print(f"Type: {data['issue_type']}")  # "Bug"
    print(f"Severity: {data['severity']}")  # "High"
    print(f"Component: {data['affected_component']}")  # "Login component"
    print(f"Action Items: {data['action_items']}")  # ["Rollback changes", ...]
    print(f"Processing time: {response.processing_time_ms:.1f}ms")  # ~900ms

# Extract from image
response = client.extract_from_image(
    image_url="https://example.com/issue-screenshot.png",
    template=template
)

# Or from base64
response = client.extract_from_image(
    image_base64="data:image/png;base64,iVBORw0KGgo...",
    template=template
)
```

**Template Design Guidelines:**
- Use empty strings `""` for text fields
- Use empty arrays `[]` for list fields
- Use `0` for numeric fields
- Use `{}` for nested objects
- Temperature 0.0 ensures deterministic extraction

## Deployment

### Prerequisites

1. **Modal CLI Installation:**
```bash
pip install modal
```

2. **Modal Authentication:**
```bash
modal token set
# Or set in .env:
# MODAL_TOKEN_ID=ak-...
# MODAL_TOKEN_SECRET=as-...
```

3. **Environment Variables:**
```bash
# Add to .env
MODAL_TOKEN_ID=ak-your-token-id
MODAL_TOKEN_SECRET=as-your-token-secret
```

### Deploy All Services

```bash
# Deploy all three services
python modules/ingest/deploy/modal_deploy_all.py
```

This will:
1. ✅ Check Modal CLI and authentication
2. 🚀 Deploy each service to Modal
3. 📍 Display endpoint URLs
4. 🧪 Run health checks

### Deploy Individual Service

```bash
# Deploy only embedding service
modal deploy modules/ingest/services/tei_service.py

# Deploy only OCR service
modal deploy modules/ingest/services/deepseek_ocr_service.py

# Deploy only extraction service
modal deploy modules/ingest/services/nuextract_service.py
```

### Configure Endpoints

After deployment, copy the endpoint URLs to `.env`:

```bash
# .env
MODAL_ENDPOINT=https://your-org--embed.modal.run
DEEPSEEK_OCR_ENDPOINT=https://your-org--process-image.modal.run
NUEXTRACT_ENDPOINT=https://your-org--extract.modal.run
```

## Performance Characteristics

### TEI Embedding Service
- **Cold Start:** ~30-60s (first request after idle)
- **Warm Request:** 50-200ms per batch
- **Batch Size:** Up to 256 requests
- **Max Tokens:** 32,768 per request
- **Scale Down:** 5 minutes idle

### DeepSeek-OCR Service
- **Cold Start:** ~60-90s (model loading)
- **Warm Request:** 500ms-2s per image
- **Max Resolution:** Limited by GPU memory
- **Scale Down:** 5 minutes idle
- **Concurrent:** Up to 10 requests

### NuExtract Service
- **Cold Start:** ~60-90s (multimodal model)
- **Warm Request:** ~0.9-1.5s per extraction (tested average: 0.94s)
- **Max Tokens:** 8,192 context
- **Temperature:** 0.0 recommended for deterministic extraction
- **Scale Down:** 5 minutes idle
- **Concurrent:** 10 requests per container

## Error Handling

All clients implement:
- ✅ **Rate limiting** (10 req/s default)
- ✅ **Retry logic** (3 attempts with exponential backoff)
- ✅ **Cold start detection** (extended timeouts)
- ✅ **Validation** (input/output validation)
- ✅ **Performance tracking** (metrics collection)

**Example Error Handling:**
```python
response = client.process_image(image_url=url)

if not response.success:
    print(f"Error: {response.error_message}")
    # Handle specific errors
    if "timeout" in response.error_message.lower():
        # Retry with longer timeout
        pass
    elif "rate limit" in response.error_message.lower():
        # Wait and retry
        pass
```

## Cost Optimization

### Automatic Scale Down
All services scale to zero after 5 minutes of inactivity:
- No cost when idle
- Automatic startup on next request
- Cold start penalty (30-90s)

### Batch Processing
Use batch endpoints for efficiency:
```python
# Embedding service batching
batch_result = embedding_client.create_batch_embeddings(
    requests=embedding_requests,
    batch_size=50  # Process 50 at once
)
```

### Persistent Model Caching
Models are cached in Modal Volumes:
- First deployment: Downloads model (~5-15GB)
- Subsequent deployments: Uses cached model
- No repeated downloads

## Monitoring

### Health Checks
```python
import requests

# Check service health
response = requests.get(
    "https://yourapp--tei-embedding-service-health.modal.run"
)
print(response.json())
```

### Performance Stats
```python
# Get client performance metrics
stats = client.get_performance_stats()

print(f"Total Requests: {stats['total_requests']}")
print(f"Success Rate: {stats['success_rate']:.2%}")
print(f"Avg Processing: {stats['average_processing_time_ms']:.1f}ms")
print(f"Cold Starts: {stats['cold_starts']}")
```

## Troubleshooting

### Service Not Responding
```bash
# Check deployment status
modal app list

# View logs
modal app logs tei-embedding-service
modal app logs deepseek-ocr-service
modal app logs nuextract-service
```

### Cold Start Issues
- **Symptom:** First request times out
- **Solution:** Increase timeout for first request (90-120s)
- **Prevention:** Keep services warm with periodic requests

### Model Download Failures
- **Symptom:** Deployment fails during model download
- **Solution:** Redeploy (model will be cached on success)
- **Check:** Ensure Modal Volume has sufficient space

### Endpoint Configuration
- **Symptom:** Client can't connect to service
- **Solution:** Verify endpoint URLs in `.env` match deployment output
- **Check:** Use `/health` endpoint to test connectivity

## Architecture Benefits

### Why Modal?
1. ✅ **No Infrastructure Management** - Serverless GPU access
2. ✅ **Auto-Scaling** - Scale to zero when idle
3. ✅ **Cost-Effective** - Pay per second of compute
4. ✅ **Fast Deployment** - Deploy in minutes
5. ✅ **Persistent Storage** - Modal Volumes for model caching

### Why Multiple Services?
1. 🎯 **Separation of Concerns** - Each model has specific purpose
2. 🚀 **Independent Scaling** - Services scale independently
3. 💰 **Cost Optimization** - Only pay for what you use
4. 🔧 **Easy Updates** - Deploy services independently
5. 🧪 **Testing** - Test services in isolation

## Related Documentation

- [Modal.com Documentation](https://modal.com/docs)
- [vLLM Documentation](https://docs.vllm.ai/)
- [TEI Documentation](https://huggingface.co/docs/text-embeddings-inference)
- [I2P Architecture](./architecture/OVERVIEW.md)

---

**Remember:** Always test services after deployment and configure endpoint URLs in `.env` before using clients.
