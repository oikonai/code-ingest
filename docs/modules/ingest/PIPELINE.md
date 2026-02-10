# Ingestion Pipeline

> **File:** `modules/ingest/core/pipeline.py`
> **Class:** `IngestionPipeline`
> **Purpose:** Orchestrate multi-language code ingestion into vector database
> **Last Updated:** 2025-10-01

## Overview

The `IngestionPipeline` is the main orchestrator for ingesting multi-language codebases (Rust, TypeScript, Solidity, Markdown documentation) into Qdrant vector database. It coordinates service initialization, file processing, checkpoint management, and cross-language search capabilities using Qwen3-Embedding-8B (4096D) embeddings via DeepInfra API.

## Architecture

```
IngestionPipeline (Orchestrator)
    ↓
    ├─ Configuration Management
    │   ├─ IngestionConfig (batch size, rate limits, timeouts)
    │   └─ RepositoryConfig (repo paths, IDs, languages)
    │
    ├─ Service Initialization
    │   ├─ EmbeddingService (DeepInfra API)
    │   ├─ QdrantVectorClient (Vector DB)
    │   ├─ StorageManager (Collection management)
    │   └─ CheckpointManager (Resume capability)
    │
    ├─ Language Parsers
    │   ├─ RustASTParser (.rs files)
    │   ├─ TypeScriptASTParser (.ts, .tsx, .js, .jsx)
    │   ├─ SolidityASTParser (.sol files)
    │   └─ DocumentationParser (.md files)
    │
    ├─ Processing Pipeline
    │   ├─ FileProcessor (File categorization + dispatch)
    │   └─ BatchProcessor (Embedding + storage)
    │
    └─ Cross-Language Search
        ├─ Query embedding generation
        └─ Multi-collection search
```

## Flow Diagram

```
Repository Path
    ↓
FileProcessor.categorize_files_by_language()
    ├─ Scan directory (skip node_modules, target, .git)
    ├─ Group by extension (.rs, .ts, .sol, .md)
    └─ Return {language: [files]}
    ↓
For Each Language:
    ↓
    Language-Specific Parser
        ├─ RustASTParser (tree-sitter-rust)
        ├─ TypeScriptASTParser (tree-sitter-typescript)
        ├─ SolidityASTParser (tree-sitter-solidity)
        └─ DocumentationParser (markdown sections)
        ↓
    Extract Code Chunks
        ├─ Functions, structs, classes, components
        ├─ Add metadata (file_path, language, business_domain)
        └─ Calculate complexity scores
        ↓
    BatchProcessor
        ├─ Batch chunks (100 per batch)
        ├─ Generate embeddings (DeepInfra API)
        └─ Retry failed batches (max 3x)
        ↓
    StorageManager
        ├─ Upsert to Qdrant collection
        ├─ Collection mapping: rust → {prefix}_code_rust (from config)
        └─ Save checkpoint every N files
        ↓
Aggregated Statistics
    ├─ Files by language
    ├─ Chunks by collection
    ├─ Business domains
    └─ Errors
```

## Debugging: Why "Total chunks: 0"?

If the ingest log shows **Total chunks: 0** and **Repositories: 4**, the pipeline ran but **no vectors were written**. The usual cause is **embedding failures** before any storage step.

### Failure path

1. **Pipeline** → `_ingest_repository_new()` per repo → **FileProcessor** (categorize + parse) → chunks produced.
2. **BatchProcessor.stream_chunks_to_storage()** batches chunks and calls **EmbeddingService.generate_embeddings(texts)** per batch.
3. If the embedding API fails (timeout, 500, rate limit), **generate_embeddings** returns **[]** after retries.
4. **BatchProcessor._process_code_batch_parallel()** then sees `not embeddings or len(embeddings) != len(valid_chunks)` and returns **0**; it never calls **StorageManager.store_code_vectors_multi_collection()**.
5. So **SurrealDB (or any vector backend) is never written to** when all batches fail at embedding.

Log messages that confirm this:

- `❌ Parallel batch N embedding failed` → embedding returned empty or length mismatch.
- `⚠️ Batch N failed (likely timeout), will retry` → batch will be retried; if all retries fail, that batch contributes 0 chunks.

### Code locations

| Step | File | Symbol |
|------|------|--------|
| Per-repo ingest | `modules/ingest/core/pipeline.py` | `_ingest_repository_new()` |
| Batch + retry | `modules/ingest/core/batch_processor.py` | `stream_chunks_to_storage()`, `_process_code_batch_parallel()` |
| Embedding call | `modules/ingest/core/embedding_service.py` | `generate_embeddings()` |
| Storage (only if embedding succeeds) | `modules/ingest/core/storage_manager.py` | `store_code_vectors_multi_collection()` |
| Vector write | `modules/ingest/services/surrealdb_vector_client.py` | `upsert_vectors()` |

### What to fix

- **Embedding timeouts/errors:** Reduce `batch_size` (e.g. 20–30), increase `embedding_timeout`, or switch embedding model (e.g. non-batch model).
- **Verify SurrealDB is empty:** Run `scripts/inspect_surrealdb.py` (see repo root) to list tables and counts; 0 tables is expected when no batch ever succeeded.
- **Unit tests:** Use mocked embedding and storage to assert the flow without a live API or DB:
  - `make test-unit` (runs in Docker so project deps are available), or
  - `docker compose run --rm -v $(pwd)/tests:/app/tests:ro -v $(pwd)/modules:/app/modules:ro --entrypoint python ingest -m unittest tests.unit.test_batch_processor tests.unit.test_surrealdb_get_collections -v`
  - `tests/unit/test_batch_processor.py`: when embedding returns `[]`, storage is never called and stored count is 0.
  - `tests/unit/test_surrealdb_get_collections.py`: parsing of SurrealDB `INFO FOR DB` dict response.

### Next steps to get vectors stored

1. **Reduce batch size** so each embedding request is smaller and less likely to timeout: in `IngestionConfig` (or env) set `batch_size` to 20–30 (default is 50).
2. **Increase embedding timeout**: set `embedding_timeout` (e.g. 120 seconds) or `EMBEDDING_TIMEOUT` if exposed.
3. **Confirm embedding API**: call DeepInfra with a tiny batch (e.g. one string) from the same network as ingest (e.g. from inside the ingest container) to rule out connectivity or quota issues.
4. **Re-run ingest** after a change; then run `scripts/inspect_surrealdb.py` again to confirm tables and counts appear.

## Class Signature

```python
class IngestionPipeline:
    def __init__(
        self,
        config: Optional[IngestionConfig] = None,
        skip_vector_init: bool = False
    ):
        """
        Initialize ingestion pipeline with all services.

        Args:
            config: Optional configuration (uses defaults if not provided)
            skip_vector_init: Skip vector client initialization (for warmup-only mode)
        """
        self.config = config or IngestionConfig()

        # Core services
        self.checkpoint_manager = CheckpointManager(self.config.checkpoint_file)
        self.embedding_service = EmbeddingService(...)

        # Lazy-loaded services (properties)
        self._vector_client = None          # QdrantVectorClient
        self._storage_manager = None        # StorageManager
        self._batch_processor = None        # BatchProcessor
        self._file_processor = None         # FileProcessor

        # Language parsers (lightweight, immediate init)
        self.rust_parser = RustASTParser()
        self.typescript_parser = TypeScriptASTParser()
        self.solidity_parser = SolidityASTParser()
        self.documentation_parser = DocumentationParser()
```

## Configuration

### IngestionConfig

**File:** `modules/ingest/core/config.py`

```python
@dataclass
class IngestionConfig:
    # DeepInfra API endpoint (default: https://api.deepinfra.com/v1/openai)
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"

    # Checkpoint configuration
    checkpoint_file: Path = Path("./ingestion_checkpoint.json")

    # Batch processing
    batch_size: int = 25                # Chunks per embedding request (env: BATCH_SIZE). Use 50–100 with -batch model
    rate_limit: int = 4                 # Max concurrent requests (4 containers)
    max_batch_retries: int = 3          # Retry failed batches

    # Embedding configuration
    embedding_size: int = 4096          # Qwen3-Embedding-8B dimension

    # Timeouts (seconds)
    embedding_timeout: int = 120        # 2 minutes
    warmup_timeout: int = 120           # 2 minutes

    # Collection names by language (loaded from config/collections.yaml)
    collections: Dict[str, str] = {
        'rust': '{prefix}_code_rust',
        'typescript': '{prefix}_code_typescript',
        'javascript': '{prefix}_code_typescript',
        'jsx': '{prefix}_code_typescript',
        'tsx': '{prefix}_code_typescript',
        'solidity': '{prefix}_code_solidity',
        'documentation': '{prefix}_documentation',
        'mixed': '{prefix}_code_mixed'      # Cross-language search
    }

    # Business domain patterns (for classification)
    domain_patterns: Dict[str, List[str]] = {
        'finance': ['balance', 'transaction', 'payment', 'credit', 'loan'],
        'auth': ['auth', 'login', 'session', 'magic_link', 'token'],
        'ui': ['component', 'modal', 'form', 'button', 'layout', 'page'],
        'contracts': ['contract', 'solidity', 'ethereum', 'blockchain'],
        'trading': ['trading', 'marketplace', 'deal', 'investment'],
        'kyc': ['kyc', 'identity', 'verification', 'compliance'],
        'notifications': ['notification', 'email', 'alert', 'message']
    }

    # File processing
    skip_dirs: set = {
        'target', '.git', 'node_modules', '__pycache__',
        '.pytest_cache', 'dist', 'build', 'public'
    }
    max_file_size: int = 500_000        # 500KB max

    # Checkpoint frequencies
    rust_checkpoint_frequency: int = 10         # Every 10 files
    typescript_checkpoint_frequency: int = 10
    solidity_checkpoint_frequency: int = 50     # Per batch
    documentation_checkpoint_frequency: int = 5
```

### Repository Configuration

**Repository configurations are now loaded from YAML file:**

- **Config file:** `config/repositories.yaml` (or path from `REPOSITORIES_CONFIG` env var)
- **Loader module:** `modules.ingest.core.repository_loader`
- **Loaded into:** `REPOSITORIES` dict in `modules.ingest.core.config`

**RepoConfig** (New format):
```python
@dataclass
class RepoConfig:
    github_url: str                      # GitHub repository URL
    repo_type: RepoType                  # Type enum (FRONTEND, BACKEND, etc.)
    languages: List[Language]            # List of languages in repo
    components: List[str]                # Key directories to index
    has_helm: bool = False              # Contains Helm charts
    helm_path: Optional[str] = None     # Path to Helm charts
    service_dependencies: List[str]      # Service dependencies
    exposes_apis: bool = False          # Exposes APIs
    api_base_path: Optional[str] = None # API base path
    priority: str = PRIORITY_MEDIUM      # Priority (high|medium|low)
```

**Example YAML configuration:**
```yaml
repos_base_dir: ./repos

repositories:
  - id: my-backend
    github_url: https://github.com/myorg/my-backend
    repo_type: backend
    languages:
      - rust
      - yaml
      - helm
    components:
      - api
      - lib
      - db
    has_helm: true
    helm_path: helm/
    priority: high
```

**Minimal entries:** Only `github_url` is required per repository. Omitted fields are defaulted: `id` = repo name from URL, `repo_type` = backend, `languages` = [rust, yaml], `components` = [.], `priority` = medium. Use minimal entries when learning about a new repo.

**Optional discovery:** After cloning, run `make discover-repos` (or `python modules/ingest/scripts/repo_discovery.py`). This scans each cloned repo and writes `config/repositories-discovered.yaml` with `has_helm`, `helm_path`, `languages`, and `repo_type`. The loader merges this file when present: for each repo id, overlay only the keys present in the discovered file (user-set values in base YAML are not overwritten). Discovery module: `modules/ingest/core/repo_discovery.py` (`RepoDiscovery.discover()`). Override path via `REPOSITORIES_DISCOVERED_CONFIG`.

**RepositoryConfig** (Legacy format for backward compatibility):
```python
@dataclass
class RepositoryConfig:
    path: str               # Path to repository
    repo_id: str            # Unique identifier
    primary_language: str   # Main language (rust, typescript, solidity)
    description: str        # Repository description
```

## Methods

### `warmup_services(skip_vector_setup: bool = False) -> bool`

Pre-warm all services before ingestion to avoid cold start delays.

**Parameters:**
- `skip_vector_setup` (bool): Skip Qdrant collection setup (for embedding-only warmup)

**Returns:**
- `bool`: True if warmup successful

**Process:**
1. **Setup Qdrant Collections** (unless skipped):
   - Create collections if they don't exist
   - Configure vector dimensions (4096)
   - Set distance metric (cosine)
2. **Warmup DeepInfra Embedding Service**:
   - Send test request to DeepInfra API
   - Verify API connectivity
   - Minimal latency (serverless)

**Example:**
```python
pipeline = IngestionPipeline()

# Full warmup (Qdrant + Modal)
if pipeline.warmup_services():
    print("✅ All services ready")
else:
    print("❌ Warmup failed")

# Embedding-only warmup (skip Qdrant setup)
if pipeline.warmup_services(skip_vector_setup=True):
    print("✅ Embedding service ready")
```

**Performance:**
- **Cold Start**: 30-60 seconds (Modal container warmup)
- **Warm Start**: <5 seconds (containers already hot)

### `ingest_repositories(repositories: Optional[List[RepositoryConfig]] = None, resume_from_checkpoint: bool = True) -> Dict[str, Any]`

Ingest multiple repositories with language-specific processing and checkpoint support.

**Parameters:**
- `repositories` (List[RepositoryConfig]): List of repositories to ingest (uses `DEFAULT_REPOSITORIES` if None)
- `resume_from_checkpoint` (bool): Resume from saved checkpoint if exists

**Returns:**
- `Dict[str, Any]`: Comprehensive ingestion statistics

**Process:**
1. **Warmup Services** (if not already warm)
2. **Check for Checkpoint** (if resume enabled):
   - Load checkpoint from `ingestion_checkpoint.json`
   - Resume from last processed file
3. **For Each Repository**:
   - Verify repository path exists
   - Call `_ingest_repository()` for processing
   - Aggregate statistics
4. **Clear Checkpoint** on successful completion
5. **Return Statistics**

**Example:**
```python
pipeline = IngestionPipeline()

# Ingest default repositories
stats = pipeline.ingest_repositories()

print(f"Processed {stats['repositories_processed']} repositories")
print(f"Files by language: {stats['files_by_language']}")
print(f"Chunks by collection: {stats['chunks_by_collection']}")

# Ingest custom repository
custom_repos = [
    RepositoryConfig(
        path='./repos/my-project',
        repo_id='my-project',
        primary_language='typescript',
        description='My custom project'
    )
]

stats = pipeline.ingest_repositories(repositories=custom_repos)
```

**Return Format:**
```python
{
    'repositories_processed': 2,
    'files_by_language': {
        'rust': 245,
        'typescript': 189,
        'solidity': 23,
        'documentation': 45
    },
    'chunks_by_collection': {
        '{prefix}_code_rust': 18234,
        '{prefix}_code_typescript': 24567,
        '{prefix}_code_solidity': 3456,
        '{prefix}_documentation': 567
    },
    'business_domains': {
        'finance': 12345,
        'auth': 5678,
        'ui': 8901,
        'contracts': 2345
    },
    'errors': [
        'Failed to parse file: backend/broken.rs',
        'Embedding generation failed for batch 23'
    ]
}
```

**Performance:**
- **Small Repository** (<100 files): 2-5 minutes
- **Medium Repository** (100-500 files): 10-30 minutes
- **Large Repository** (500+ files): 30-90 minutes

### `search_across_languages(query: str, languages: Optional[List[str]] = None, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]`

Search for code across multiple language collections.

**Parameters:**
- `query` (str): Search query text
- `languages` (List[str]): Languages to search (searches all if None)
- `limit` (int): Maximum results per language

**Returns:**
- `Dict[str, List[Dict]]`: Results grouped by language

**Process:**
1. **Generate Query Embedding** via DeepInfra API
2. **Search Each Language Collection**:
   - Map language to collection name
   - Execute vector search with cosine similarity
   - Filter by score threshold (0.3)
3. **Return Grouped Results**

**Example:**
```python
pipeline = IngestionPipeline()

# Search all languages
results = pipeline.search_across_languages(
    query="loan approval implementation",
    limit=10
)

for language, matches in results.items():
    print(f"\n{language} results:")
    for match in matches:
        print(f"  Score: {match['score']:.3f}")
        print(f"  File: {match['metadata']['file_path']}")
        print(f"  Function: {match['metadata']['item_name']}")

# Search specific languages
results = pipeline.search_across_languages(
    query="ZK proof verification",
    languages=['rust', 'solidity'],
    limit=5
)
```

**Return Format:**
```python
{
    'rust': [
        {
            'score': 0.87,
            'metadata': {
                'file_path': 'backend/loan_service.rs',
                'item_name': 'approve_loan',
                'item_type': 'function',
                'language': 'rust',
                'business_domain': 'finance',
                'repo_id': 'my-backend'
            },
            'content': 'pub fn approve_loan(loan_id: LoanId) -> Result<...> { ... }'
        }
    ],
    'solidity': [
        {
            'score': 0.82,
            'metadata': {
                'file_path': 'contracts/verifier.sol',
                'item_name': 'verifyProof',
                'item_type': 'function',
                'language': 'solidity'
            },
            'content': 'function verifyProof(...) public returns (bool) { ... }'
        }
    ]
}
```

**Performance:**
- **Query Embedding**: 50-100ms
- **Single Collection Search**: 100-200ms
- **Multi-Language Search**: 300-500ms (4 collections)

## Lazy Loading Strategy

### Why Lazy Loading?

**Problem:** Initializing Qdrant client requires credentials and network connection. In warmup-only mode, we only need the DeepInfra API embedding service.

**Solution:** Lazy-load heavy services via properties.

**Implementation:**
```python
@property
def vector_client(self) -> QdrantVectorClient:
    """Lazy-load vector client on first access."""
    if self._vector_client is None:
        if self._skip_vector_init:
            raise RuntimeError("Vector client access not allowed in warmup-only mode")
        self._vector_client = QdrantVectorClient()
    return self._vector_client

@property
def storage_manager(self) -> StorageManager:
    """Lazy-load storage manager on first access."""
    if self._storage_manager is None:
        self._storage_manager = StorageManager(
            vector_client=self.vector_client,  # Triggers lazy load
            embedding_size=self.config.embedding_size
        )
    return self._storage_manager
```

**Benefits:**
- Faster initialization in warmup-only mode
- Deferred credential validation
- Memory efficiency (load only what's needed)

## Checkpoint Management

### Purpose

Resume ingestion from last successful point if interrupted (network failure, OOM, etc.).

### Checkpoint Format

**File:** `ingestion_checkpoint.json`

```json
{
    "repo_id": "my-backend",
    "language": "rust",
    "last_processed_file": "backend/loan_service.rs",
    "files_processed": 123,
    "chunks_processed": 8945,
    "timestamp": "2025-10-01T12:34:56Z"
}
```

### Usage

```python
# Enable resume (default)
pipeline.ingest_repositories(resume_from_checkpoint=True)

# Disable resume (start fresh)
pipeline.ingest_repositories(resume_from_checkpoint=False)

# Check for existing checkpoint
checkpoint_info = pipeline.checkpoint_manager.get_checkpoint_info()
if checkpoint_info:
    print(f"Found checkpoint: {checkpoint_info['repo_id']} / {checkpoint_info['language']}")
    print(f"Files processed: {checkpoint_info['files_processed']}")

# Clear checkpoint manually
pipeline.checkpoint_manager.clear_checkpoint()
```

### Checkpoint Frequency

**Configurable per language:**
- Rust: Every 10 files
- TypeScript: Every 10 files
- Solidity: Every 50 files (batch processing)
- Documentation: Every 5 files

**Why different frequencies?**
- Rust files are large (100-500 lines) → save often
- Solidity files are small (50-200 lines) → batch processing
- Documentation files are small → save often for visibility

## Usage Examples

### Basic Ingestion

```python
from modules.ingest.core.pipeline import IngestionPipeline

# Initialize with defaults
pipeline = IngestionPipeline()

# Ingest default repositories
stats = pipeline.ingest_repositories()

# Print summary
print(f"✅ Ingested {stats['repositories_processed']} repositories")
print(f"📊 Total chunks: {sum(stats['chunks_by_collection'].values())}")
```

### Custom Configuration

```python
from modules.ingest.core.pipeline import IngestionPipeline
from modules.ingest.core.config import IngestionConfig

# Custom configuration
config = IngestionConfig(
    batch_size=50,              # Smaller batches
    rate_limit=2,               # Fewer concurrent requests
    embedding_timeout=180,      # 3 minute timeout
    max_file_size=1_000_000     # 1MB max file size
)

pipeline = IngestionPipeline(config=config)
stats = pipeline.ingest_repositories()
```

### Warmup-Only Mode

```python
# Initialize without vector client (warmup-only)
pipeline = IngestionPipeline(skip_vector_init=True)

# Warmup DeepInfra API embedding service only
if pipeline.warmup_services(skip_vector_setup=True):
    print("✅ Embedding service ready")
```

### Custom Repositories

```python
from modules.ingest.core.config import RepositoryConfig

custom_repos = [
    RepositoryConfig(
        path='./repos/my-rust-project',
        repo_id='my-rust-project',
        primary_language='rust',
        description='My custom Rust project'
    ),
    RepositoryConfig(
        path='./repos/my-ts-project',
        repo_id='my-ts-project',
        primary_language='typescript',
        description='My TypeScript project'
    )
]

pipeline = IngestionPipeline()
stats = pipeline.ingest_repositories(repositories=custom_repos)
```

### Search After Ingestion

```python
pipeline = IngestionPipeline()

# Ingest repositories
pipeline.ingest_repositories()

# Search for code
results = pipeline.search_across_languages(
    query="authentication implementation",
    languages=['rust', 'typescript'],
    limit=10
)

# Process results
for language, matches in results.items():
    print(f"\n{language.upper()} Results:")
    for match in matches:
        metadata = match['metadata']
        print(f"  📁 {metadata['file_path']}:{metadata['item_name']}")
        print(f"     Score: {match['score']:.3f} | Domain: {metadata['business_domain']}")
```

### Resume from Checkpoint

```python
pipeline = IngestionPipeline()

# First run (interrupted)
try:
    pipeline.ingest_repositories()
except KeyboardInterrupt:
    print("⚠️ Ingestion interrupted, checkpoint saved")

# Second run (resume)
pipeline2 = IngestionPipeline()
stats = pipeline2.ingest_repositories(resume_from_checkpoint=True)
# Will resume from last processed file
```

## Error Handling

### Service Warmup Failures

```python
pipeline = IngestionPipeline()

if not pipeline.warmup_services():
    logger.error("❌ Service warmup failed")
    # Check:
    # 1. DeepInfra API key is valid
    # 2. Qdrant credentials are valid
    # 3. Network connectivity
    exit(1)
```

### Repository Not Found

```python
# Pipeline logs warning and skips missing repositories
stats = pipeline.ingest_repositories()

# Check errors
if stats.get('errors'):
    print(f"⚠️ {len(stats['errors'])} errors occurred:")
    for error in stats['errors']:
        print(f"  - {error}")
```

### Embedding Generation Failures

**Automatic Retry:** BatchProcessor retries failed batches up to 3 times

```python
# Check error details in stats
if 'Embedding generation failed' in stats['errors']:
    # Possible causes:
    # 1. DeepInfra API timeout or rate limit
    # 2. Network issues
    # 3. Invalid text encoding
    # 4. Service overload
```

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Embedding Generation** | API rate limited | DeepInfra API throughput |
| **Batch Processing** | 100 chunks/batch | Optimized for throughput |
| **Cold Start** | Minimal | Serverless API |
| **Warm Start** | <5s | API already available |
| **File Categorization** | 1000 files/sec | Lightweight file scanning |
| **Checkpoint Save** | <10ms | JSON write |
| **Vector Upsert** | 200-500 chunks/sec | Qdrant batch upsert |

**Optimization Tips:**
- Increase `batch_size` for higher throughput (max 200)
- Adjust `rate_limit` based on DeepInfra API rate limits
- Decrease checkpoint frequency to reduce I/O overhead

## Monitoring

### Progress Logging

**During Ingestion:**
```
🚀 Initializing ingestion pipeline...
✅ Ingestion pipeline initialized
🔥 Warming up services...
✅ All services ready
🏢 Starting repository ingestion
📂 Processing repository: my-backend
📝 Processing 245 rust files in my-backend
  ⏳ Processing file 1/245: backend/main.rs
  ⏳ Processing file 10/245: backend/loan_service.rs (checkpoint saved)
  ...
📝 Processing 189 typescript files in my-backend
✅ Repository ingestion complete

============================================================
📊 Ingestion Statistics:
============================================================
  Repositories: 2
  Files by language:
    rust: 245
    typescript: 189
    solidity: 23
    documentation: 45
  Chunks by collection:
    {prefix}_code_rust: 18234
    {prefix}_code_typescript: 24567
    {prefix}_code_solidity: 3456
    {prefix}_documentation: 567
  Business domains:
    finance: 12345
    auth: 5678
    ui: 8901
    contracts: 2345
============================================================
```

### Health Checks

```bash
# Check vector database status
make vector-status

# Check DeepInfra API health
make warmup-services

# Test search functionality
python -c "
from modules.ingest.core.pipeline import IngestionPipeline
pipeline = IngestionPipeline()
results = pipeline.search_across_languages('test query', limit=1)
print(f'Search working: {len(results) > 0}')
"
```

## Related Documentation

- [Language Parsers](./PARSERS.md) - AST parsing for Rust, TypeScript, Solidity
- [Embedding Service](../../architecture/OVERVIEW.md) - DeepInfra API integration
- [Vector Client](./VECTOR_CLIENT.md) - Qdrant client
- [Vector Search Architecture](../../architecture/VECTOR_SEARCH.md) - Search system
- [Configuration](./CONFIG.md) - Configuration options *(Coming soon)*

---

**Note:** This document is auto-synced with code. Update when modifying `modules/ingest/core/pipeline.py`.
