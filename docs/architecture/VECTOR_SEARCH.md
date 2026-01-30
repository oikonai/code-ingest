# Vector Search Architecture

> **Last Updated:** 2026-01-30
> **Scope:** Multi-language semantic code search

## Overview

The vector search system enables semantic code retrieval across Rust, TypeScript, Solidity, and Documentation codebases using Qwen3-Embedding-8B (4096D) embeddings stored in Qdrant. It provides cross-language semantic search with enhanced ranking and deduplication.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Search Request                            │
│                 "authentication service"                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                 IngestionPipeline                           │
│          search_across_languages(query)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼──────────┐    ┌────────▼─────────┐
│ EmbeddingService │    │ QdrantClient     │
│ (Query Embedding)│    │ (Vector Search)  │
└──────────────────┘    └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼──────┐          ┌──────▼────────┐
            │ rust         │          │ typescript    │
            │ collection   │          │ collection    │
            └──────────────┘          └───────────────┘
                                              │
                                      ┌───────▼──────┐
                                      │ solidity     │
                                      │ collection   │
                                      └──────────────┘
                                              │
                                      ┌───────▼──────┐
                                      │ documentation│
                                      │ collection   │
                                      └──────────────┘
```

## Components

### 1. IngestionPipeline Search Interface

**File:** `modules/ingest/core/pipeline.py`
**Purpose:** Primary search interface for cross-language semantic search

```python
def search_across_languages(
    self,
    query: str,
    languages: Optional[List[str]] = None,
    limit: int = 5,
    score_threshold: float = 0.3
) -> Dict[str, List[Dict[str, Any]]]
```

**Parameters:**
- `query` - Natural language search query
- `languages` - List of collections to search (default: ['rust', 'typescript', 'solidity'])
- `limit` - Max results per language
- `score_threshold` - Minimum cosine similarity score (0.0-1.0)

**Returns:**
```python
{
    "rust": [
        {
            "score": 0.87,
            "payload": {
                "content": "pub fn authenticate(token: &str) -> Result<User> { ... }",
                "signature": "authenticate",
                "file_path": "api/src/auth.rs",
                "start_line": 45,
                "end_line": 78,
                "language": "rust",
                "chunk_type": "function_item",
                "repository": "my-backend",
                "component": "api"
            }
        },
        # ... more results
    ],
    "typescript": [ ... ],
    "solidity": [ ... ]
}
```

### 2. EmbeddingService

**File:** `modules/ingest/core/embedding_service.py`
**Purpose:** Generate query embeddings for semantic search

**Features:**
- Qwen3-Embedding-8B (4096D)
- Cloudflare AI Gateway + DeepInfra backend
- Modal TEI backend (alternative)
- Batch processing support
- Automatic retry on transient failures

### 3. QdrantVectorClient

**File:** `modules/ingest/services/vector_client.py`
**Purpose:** Vector database interface for search operations

**Search Method:**
```python
def search(
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    score_threshold: float = 0.3,
    filter_conditions: Optional[Dict] = None
) -> List[ScoredPoint]
```

**Features:**
- Cosine similarity search
- Metadata filtering
- Score thresholding
- Efficient batch operations

## Search Flow

### Step 1: Query Embedding
```
User Query: "authentication service"
    ↓
[EmbeddingService] Generate embedding
    ↓
Query Vector: [f32; 4096]
```

### Step 2: Multi-Collection Search
```
For each collection in [rust, typescript, solidity]:
    ┌─────────────────────────────────────┐
    │ Qdrant Search                       │
    │ - Vector: query_vector              │
    │ - Limit: 5                          │
    │ - Threshold: 0.3                    │
    │ - Metric: Cosine Similarity         │
    └─────────────────────────────────────┘
            ↓
    Results sorted by score (descending)
```

### Step 3: Result Aggregation
```
results_by_language = {
    "rust": [result1, result2, ...],
    "typescript": [result1, result2, ...],
    "solidity": [result1, result2, ...]
}
    ↓
[Optional] Deduplicate by chunk_hash
    ↓
[Optional] Enhanced ranking (recency, file type)
    ↓
Return top N results per language
```

## Vector Storage Schema

### Collections

| Collection | Purpose | Chunk Types |
|-----------|---------|-------------|
| `rust` | Rust code | function_item, struct_item, impl_item, macro_definition |
| `typescript` | TypeScript/JSX | function_declaration, class_declaration, interface_declaration |
| `solidity` | Solidity contracts | contract_declaration, function_definition, event_definition |
| `documentation` | Markdown docs | heading_section, documentation_block |

### Point Structure

```python
PointStruct(
    id=UUID,
    vector=[f32; 4096],  # Qwen3-Embedding-8B
    payload={
        "content": str,           # Code/text content
        "signature": str,          # Function/struct name
        "file_path": str,          # Relative file path
        "start_line": int,         # Start line number
        "end_line": int,           # End line number
        "language": str,           # rust/typescript/solidity/documentation
        "chunk_type": str,         # function_item/class_declaration/etc
        "chunk_hash": str,         # SHA256 for deduplication
        "repository": str,         # Source repository name
        "component": str,          # api/core/contracts/etc
        "timestamp": str           # Ingestion timestamp
    }
)
```

## Search Features

### 1. Cross-Language Search
Search across multiple programming languages simultaneously:
```python
results = pipeline.search_across_languages(
    query="JWT token validation",
    languages=["rust", "typescript"]
)
```

### 2. Score Thresholding
Filter results by minimum cosine similarity:
```python
results = pipeline.search_across_languages(
    query="payment processing",
    score_threshold=0.5  # Only return scores >= 0.5
)
```

### 3. Metadata Filtering
Filter by repository, component, or other metadata (via QdrantVectorClient):
```python
results = vector_client.search(
    collection_name="rust",
    query_vector=query_vector,
    filter_conditions={
        "repository": "my-backend",
        "component": "api"
    }
)
```

### 4. Deduplication
Prevent duplicate results based on content hash:
```python
# Automatic deduplication by chunk_hash
unique_results = deduplicate_by_hash(results)
```

### 5. Enhanced Ranking
Boost results based on additional signals:
- **File type relevance** - Prefer implementation files over tests
- **Recency** - Boost recently modified files
- **Component importance** - Boost core components over utilities

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Search Latency | <200ms | Including query embedding generation |
| Query Embedding | ~20-50ms | Per query, varies by backend |
| Vector Search | ~5-10ms | Per collection, Qdrant HNSW index |
| Result Limit | Configurable | Default 5 per language |
| Score Threshold | 0.3 (default) | Cosine similarity cutoff |
| Collections | 4 | rust, typescript, solidity, documentation |

## Usage Examples

### Basic Search
```bash
# Via Makefile
make ingest-search QUERY='authentication service'

# Via Python
from modules import IngestionPipeline

pipeline = IngestionPipeline()
results = pipeline.search_across_languages(
    query="authentication service",
    limit=10
)

for language, chunks in results.items():
    print(f"\n{language.upper()} Results:")
    for chunk in chunks:
        print(f"  - {chunk['payload']['signature']} ({chunk['score']:.2f})")
        print(f"    {chunk['payload']['file_path']}:{chunk['payload']['start_line']}")
```

### Language-Specific Search
```python
# Search only Rust code
results = pipeline.search_across_languages(
    query="loan approval logic",
    languages=["rust"]
)

# Search only TypeScript
results = pipeline.search_across_languages(
    query="React authentication component",
    languages=["typescript"]
)
```

### High-Precision Search
```python
# Increase score threshold for higher precision
results = pipeline.search_across_languages(
    query="zero-knowledge proof verification",
    score_threshold=0.6,  # Stricter matching
    limit=3
)
```

## Search Quality

### Factors Affecting Quality

1. **Query Formulation**
   - More specific queries → better results
   - Include technical terms (e.g., "JWT", "async", "smart contract")
   - Use natural language ("how to authenticate users")

2. **Embedding Model**
   - Qwen3-Embedding-8B trained on code
   - 4096D provides high semantic resolution
   - Better than generic text embeddings for code

3. **Score Threshold**
   - Lower (0.2-0.3) → higher recall, more false positives
   - Higher (0.5-0.7) → higher precision, may miss relevant results
   - Default 0.3 balances precision/recall

4. **Collection Coverage**
   - More ingested code → better search coverage
   - Regular re-ingestion captures new code
   - Prune stale repositories to improve relevance

### Testing Search Quality

```bash
# Run search quality tests
python modules/ingest/scripts/search_test.py \
    --query "authentication service" \
    --limit 10 \
    --format detailed

# Generate statistics
make stats-report
```

## Troubleshooting

### No Results Returned
- Check score_threshold (try lowering to 0.2)
- Verify collections are populated: `make vector-status`
- Test with broader query terms
- Ensure embedding service is accessible

### Poor Result Quality
- Increase score_threshold for precision
- Use more specific query terms
- Check if relevant code is ingested
- Review ingestion logs for errors

### Slow Search Performance
- Check Qdrant network latency
- Verify embedding service health: `make modal-health`
- Consider reducing result limit
- Check if vector indices are built: `make index-check`

## Related Documentation

- [Ingestion Pipeline](../modules/ingest/PIPELINE.md)
- [Data Flow](./DATA_FLOW.md)
- [Overview](./OVERVIEW.md)

---

**Note:** Vector search quality improves with more ingested code and regular re-ingestion to capture repository updates.
