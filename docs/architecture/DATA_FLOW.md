# Code Ingestion Data Flow Architecture

> **Last Updated:** 2026-02-04
> **Scope:** Complete ingestion lifecycle and data transformations

## Overview

This document traces the complete journey of code through the ingestion system, from GitHub repository to searchable vector database, including all transformations, enrichments, and external service interactions.

## Ingestion Lifecycle

### Phase 1: Repository Selection & Cloning

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Input (Bash/Make)                                   │
│    $ make ingest [PRIORITY=high|medium|low|ALL]             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Repository Configuration Loading                         │
│    Source: config/repositories.yaml (or REPOSITORIES_CONFIG env) │
│    Loader: modules.ingest.core.repository_loader           │
│                                                             │
│    Only github_url required per repo (minimal entries).     │
│    Optional overlay files (merged when present):             │
│    - config/repositories-discovered.yaml (has_helm,         │
│      helm_path, languages, repo_type from disk scan)        │
│    - config/repositories-relationships.yaml                  │
│      (service_dependencies from YAML/Helm analysis)          │
│                                                             │
│    repositories:                                            │
│      - id: my-backend                                       │
│        github_url: https://github.com/myorg/my-backend      │
│        priority: high                                       │
│        languages: [rust, yaml, helm]                        │
│        components: [api, lib, db]                           │
│        ...                                                  │
│                                                             │
│    Loaded into: REPOSITORIES dict (modules.ingest.core.config) │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Priority Filtering                                       │
│    filtered_repos = [                                       │
│        repo for repo in REPOSITORIES                        │
│        if repo.priority >= min_priority                     │
│    ]                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. Git Clone (repo_cloner.py)                               │
│    $ git clone --depth 1 {github_url} {repos_base_dir}/{name} │
│                                                             │
│    Uses: GITHUB_TOKEN for authentication                    │
│    Base dir: {repos_base_dir} from config (default: ./repos) │
│    Output: {repos_base_dir}/{repo_name}/                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                [Ingestion Pipeline]
```

### Derived metadata (optional)

Two optional steps enrich repository config without editing `repositories.yaml`:

**Discovery (run after clone):** `make discover-repos` or `python modules/ingest/scripts/repo_discovery.py`. Scans each cloned repo on disk and writes `config/repositories-discovered.yaml` with `has_helm`, `helm_path`, `languages`, and `repo_type`. The loader merges this file when present; user-set values in base YAML are not overwritten. Override path: `REPOSITORIES_DISCOVERED_CONFIG`.

**Relationship derivation (run after ingest):** `make derive-dependencies` or `python modules/ingest/scripts/derive_dependencies.py`. Scans YAML/Helm files in each repo, runs `DependencyAnalyzer`, and writes `config/repositories-relationships.yaml` with per-repo `service_dependencies`. The loader merges it when present; if a repo already has `service_dependencies` in base YAML, that list is kept (user override wins). Override path: `REPOSITORIES_RELATIONSHIPS_CONFIG`.

Typical order: clone → (optional) discover-repos → ingest → (optional) derive-dependencies. On the next load, `REPOSITORIES` will include discovered and derived fields.

### Phase 2: Pipeline Initialization

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Environment Configuration                                │
│    load_dotenv()                                            │
│    - QDRANT_URL, QDRANT_API_KEY                             │
│    - DEEPINFRA_API_KEY                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Service Initialization                                   │
│    pipeline = IngestionPipeline()                           │
│                                                             │
│    Initializes:                                             │
│    - EmbeddingService (DeepInfra backend)                  │
│    - QdrantVectorClient (vector database connection)        │
│    - FileProcessor (with language parsers)                  │
│    - BatchProcessor (concurrent embedding)                  │
│    - CheckpointManager (resume support)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Service Warmup (Optional)                                │
│    pipeline.warmup_services()                               │
│                                                             │
│    - Verify DeepInfra API connectivity                      │
│    - Verify Qdrant connectivity                             │
│    - Initialize language parsers                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
            [Repository Processing]
```

### Phase 3: Repository Processing

```
┌─────────────────────────────────────────────────────────────┐
│ For each repository in filtered_repos:                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 1. Load Checkpoint (if exists)                              │
│    checkpoint = load("ingestion_checkpoint.json")           │
│    if checkpoint and resume_from_checkpoint:                │
│        skip_repos = checkpoint['completed_repos']           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. File Discovery                                           │
│    - Recursively scan repo directory                        │
│    - Filter by language extension (.rs, .ts, .sol, .md)     │
│    - Apply gitignore rules                                  │
│    - Exclude large binary files                             │
│                                                             │
│    Output: List[Path] of files to process                   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Language Detection                                       │
│    file_ext = file.suffix                                   │
│    parser = {                                               │
│        '.rs': RustASTParser,                                │
│        '.ts', '.tsx': TypeScriptASTParser,                  │
│        '.sol': SolidityASTParser,                           │
│        '.md': DocumentationParser,                          │
│        '.yaml', '.yml': YAMLParser,                         │
│        '.tf': TerraformParser                               │
│    }[file_ext]                                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                [File Processing]
```

### Phase 4: File Processing (Per File)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. File Read                                                │
│    content = file.read_text(encoding='utf-8')               │
│    - Handle encoding errors gracefully                      │
│    - Skip empty files                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. AST Parsing (tree-sitter)                                │
│    tree = parser.parse(content.encode('utf-8'))             │
│    root_node = tree.root_node                               │
│                                                             │
│    - Build syntax tree                                      │
│    - Extract node types (function, struct, class, etc.)     │
│    - Capture source ranges (start_byte, end_byte)           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Chunk Extraction (Language-Specific)                     │
│                                                             │
│    Rust:                                                    │
│    - function_item → function definitions                   │
│    - struct_item → struct definitions                       │
│    - impl_item → trait implementations                      │
│    - macro_definition → macro definitions                   │
│                                                             │
│    TypeScript:                                              │
│    - function_declaration → functions                       │
│    - class_declaration → classes                            │
│    - interface_declaration → interfaces                     │
│    - type_alias_declaration → type definitions              │
│                                                             │
│    Solidity:                                                │
│    - contract_declaration → contracts                       │
│    - function_definition → functions                        │
│    - event_definition → events                              │
│    - interface_declaration → interfaces                     │
│                                                             │
│    Documentation:                                           │
│    - heading sections → markdown sections                   │
│    - Intelligent grouping (6k-12k chars)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. Chunk Metadata Enrichment                                │
│    chunk = {                                                │
│        'content': str,           # Code/text content        │
│        'signature': str,          # Function/struct name    │
│        'file_path': str,          # Relative path           │
│        'start_line': int,         # Line number start       │
│        'end_line': int,           # Line number end         │
│        'language': str,           # rust/typescript/etc     │
│        'chunk_type': str,         # function/struct/etc     │
│        'chunk_hash': str,         # SHA256 for dedup        │
│        'repository': str,         # Repo name               │
│        'component': str,          # api/core/etc            │
│        'timestamp': str           # Ingestion time          │
│    }                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                [Batch Processing]
```

### Phase 5: Batch Embedding & Storage

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Batch Collection                                         │
│    batch_size = 50  # Configurable                          │
│    batches = chunk_list(chunks, batch_size)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │   For each batch:       │
        └────────────┬────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Embedding Generation (EmbeddingService)                  │
│                                                             │
│    Backend: DeepInfra API (OpenAI-compatible)              │
│    ┌─────────────────────────────────────────┐             │
│    │ Request:                                │             │
│    │   POST https://api.deepinfra.com/v1/openai/embeddings │
│    │   Headers:                               │             │
│    │     Authorization: Bearer {DEEPINFRA_API_KEY} │        │
│    │   Body:                                  │             │
│    │   {                                     │             │
│    │     "input": ["code chunk 1", ...],    │             │
│    │     "model": "Qwen/Qwen3-Embedding-8B-batch" │        │
│    │   }                                     │             │
│    │                                         │             │
│    │ Response:                               │             │
│    │   {                                     │             │
│    │     "data": [                           │             │
│    │       {"embedding": [f32; 4096]},       │             │
│    │       ...                               │             │
│    │     ]                                   │             │
│    │   }                                     │             │
│    └─────────────────────────────────────────┘             │
│                                                             │
│    Features:                                                │
│    - Rate limiting: 4 concurrent requests                  │
│    - Retry logic: Exponential backoff (max 3 retries)      │
│    - Validation: Dimension, NaN, None checks                │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Vector Point Construction                                │
│    points = [                                               │
│        PointStruct(                                         │
│            id=uuid4(),                                      │
│            vector=embedding,  # 4096D float array           │
│            payload={                                        │
│                'content': chunk['content'],                 │
│                'signature': chunk['signature'],             │
│                'file_path': chunk['file_path'],             │
│                'start_line': chunk['start_line'],           │
│                'end_line': chunk['end_line'],               │
│                'language': chunk['language'],               │
│                'chunk_type': chunk['chunk_type'],           │
│                'chunk_hash': chunk['chunk_hash'],           │
│                'repository': chunk['repository'],           │
│                'component': chunk['component'],             │
│                'timestamp': chunk['timestamp']              │
│            }                                                │
│        )                                                    │
│        for chunk, embedding in zip(chunks, embeddings)      │
│    ]                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. Qdrant Upsert (QdrantVectorClient)                      │
│    collection_name = chunk['language']  # rust/typescript  │
│    client.upsert(                                           │
│        collection_name=collection_name,                     │
│        points=points,                                       │
│        wait=True                                            │
│    )                                                        │
│                                                             │
│    - Language-specific collections                          │
│    - Automatic collection creation if not exists            │
│    - Vector index updated automatically                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 5. Statistics Collection                                    │
│    stats = {                                                │
│        'total_files': int,                                  │
│        'total_chunks': int,                                 │
│        'embeddings_generated': int,                         │
│        'vectors_stored': int,                               │
│        'processing_time': float,                            │
│        'errors': List[str]                                  │
│    }                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 6. Checkpoint Save                                          │
│    checkpoint = {                                           │
│        'completed_repos': List[str],                        │
│        'timestamp': str,                                    │
│        'stats': stats                                       │
│    }                                                        │
│    save("ingestion_checkpoint.json", checkpoint)            │
└────────────────────────────────────────────────────────────┘
```

## Vector Search Flow

### Query Processing

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Query Input                                         │
│    $ make ingest-search QUERY='authentication service'      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Query Embedding Generation                               │
│    query_embedding = embedding_service.embed([query])       │
│    # Shape: [4096] float array                              │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Qdrant Search (Multi-Collection)                         │
│    collections = ['rust', 'typescript', 'solidity']         │
│    results = {}                                             │
│    for collection in collections:                           │
│        results[collection] = client.search(                 │
│            collection_name=collection,                      │
│            query_vector=query_embedding,                    │
│            limit=10,                                        │
│            score_threshold=0.3                              │
│        )                                                    │
│                                                             │
│    Each result:                                             │
│    {                                                        │
│        'id': UUID,                                          │
│        'score': float,  # Cosine similarity                 │
│        'payload': {     # Chunk metadata                    │
│            'content': str,                                  │
│            'signature': str,                                │
│            'file_path': str,                                │
│            'start_line': int,                               │
│            'end_line': int,                                 │
│            'language': str,                                 │
│            ...                                              │
│        }                                                    │
│    }                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. Result Aggregation & Ranking                             │
│    all_results = flatten(results)                           │
│    sorted_results = sort_by_score(all_results)              │
│    unique_results = deduplicate_by_hash(sorted_results)     │
│                                                             │
│    Enhanced ranking (optional):                             │
│    - Boost by file type relevance                           │
│    - Boost by recency                                       │
│    - Boost by component importance                          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 5. Result Formatting                                        │
│    formatted_results = [                                    │
│        {                                                    │
│            'rank': int,                                     │
│            'score': float,                                  │
│            'file': file_path,                               │
│            'lines': f"{start_line}-{end_line}",             │
│            'signature': signature,                          │
│            'content': content[:500],  # Truncated           │
│            'language': language                             │
│        }                                                    │
│        for result in unique_results[:limit]                 │
│    ]                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                [Display Results]
```

## Data Transformations Summary

### Repository → File List
- **Input:** Repository path
- **Output:** List of file paths filtered by language
- **Transformation:** Recursive directory scan + gitignore filtering

### File → Code Chunks
- **Input:** File content (UTF-8 text)
- **Output:** List of code chunks with metadata
- **Transformation:** AST parsing + node extraction + metadata enrichment

### Code Chunks → Embeddings
- **Input:** List of code chunk strings
- **Output:** 4096D float vectors
- **Transformation:** Qwen3-Embedding-8B model inference

### Embeddings → Vector Points
- **Input:** Embeddings + metadata
- **Output:** Qdrant point structures
- **Transformation:** UUID generation + payload construction

### Query String → Search Results
- **Input:** Text query
- **Output:** Ranked, deduplicated results
- **Transformation:** Query embedding + cosine similarity search + ranking

## Performance Characteristics

| Stage | Throughput | Latency | Notes |
|-------|-----------|---------|-------|
| Repository Cloning | Varies | Network-bound | Depends on repo size |
| File Discovery | ~1000 files/sec | <1s | Filesystem I/O |
| AST Parsing | ~50-100 files/sec | Varies | Language-dependent |
| Chunk Extraction | ~500 chunks/sec | <10ms/chunk | In-memory operation |
| Embedding Generation | Varies | Varies | DeepInfra API rate limits, 4 concurrent requests |
| Vector Upsert | ~100-500/sec | <5ms/batch | Network + index update |
| Search Query | ~5-10ms | <200ms total | Including embedding gen |

## Error Handling & Recovery

### File Processing Errors
- **Skip gracefully** - Log error, continue to next file
- **Preserve stats** - Track failed files in statistics
- **No pipeline halt** - Single file failure doesn't stop repo ingestion

### Embedding Service Errors
- **Retry logic** - Exponential backoff (3 retries)
- **Batch splitting** - Split large batches if service errors
- **Fallback** - Continue with remaining chunks if some fail

### Vector Storage Errors
- **Transient retry** - Retry on network errors
- **Partial success** - Continue if some points succeed
- **Checkpoint save** - Save progress before failing

### Checkpoint Resume
- **Crash recovery** - Resume from last completed repository
- **State preservation** - Checkpoint includes completed repos + stats
- **Idempotent** - Re-running ingestion overwrites existing vectors

---

**Note:** All data transformations preserve metadata integrity through the pipeline, ensuring traceability from vector back to source code.
