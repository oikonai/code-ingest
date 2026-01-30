# Module Dependency Graph - Code Ingestion System

> **Auto-synced with codebase**
> **Last Updated:** 2026-01-30
> **Version:** 3.0.0-ingestion-only

## Complete Dependency Map

### Layer 1: Entry Points

```
Makefile (make ingest, make ingest-search, etc.)
├── python -c "from modules import IngestionPipeline; ..."
└── python modules/ingest/scripts/*.py
```

**GitHub Actions:**
```
.github/workflows/vector-ingestion.yml
├── modules/ingest/scripts/repo_cloner.py
├── modules/ingest/scripts/collection_manager.py
├── modules/ingest/scripts/repo_metadata.py
└── modules.ingest.IngestionPipeline
```

### Layer 2: Public API

```
modules/__init__.py
└── modules.ingest
    ├── IngestionPipeline
    ├── IngestionConfig
    ├── RepositoryConfig
    └── DEFAULT_REPOSITORIES
```

### Layer 3: Core Pipeline

```
modules/ingest/core/pipeline.py (IngestionPipeline)
├── modules/ingest/core/config → IngestionConfig, RepositoryConfig
├── modules/ingest/core/embedding_service → EmbeddingService
├── modules/ingest/services/vector_client → QdrantVectorClient
├── modules/ingest/core/file_processor → FileProcessor
├── modules/ingest/core/batch_processor → BatchProcessor
├── modules/ingest/core/storage_manager → StorageManager
├── modules/ingest/core/checkpoint_manager → CheckpointManager
└── External: Qdrant API, Embedding Service API
```

### Layer 4: Supporting Services

**EmbeddingService** (`modules/ingest/core/embedding_service.py`)
```
├── requests → HTTP client for API calls
├── asyncio, aiohttp → Async HTTP (warmup)
├── modules/ingest/core/config → IngestionConfig
└── External: Cloudflare AI Gateway OR Modal TEI endpoint
```

**QdrantVectorClient** (`modules/ingest/services/vector_client.py`)
```
├── qdrant_client → QdrantClient, models
├── uuid → UUID generation for point IDs
├── modules/ingest/core/config → IngestionConfig
└── External: Qdrant API (QDRANT_URL, QDRANT_API_KEY)
```

**FileProcessor** (`modules/ingest/core/file_processor.py`)
```
├── pathlib → Path operations
├── modules/ingest/parsers.rust_parser → RustASTParser
├── modules/ingest/parsers.typescript_parser → TypeScriptASTParser
├── modules/ingest/parsers.solidity_parser → SolidityASTParser
├── modules/ingest/parsers.documentation_parser → DocumentationParser
├── modules/ingest/parsers.yaml_parser → YAMLParser
├── modules/ingest/parsers.terraform_parser → TerraformParser
└── modules/ingest/core/config → IngestionConfig
```

### Layer 5: Language Parsers

**RustASTParser** (`modules/ingest/parsers/rust_parser.py`)
```
├── tree_sitter, tree_sitter_rust
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

**TypeScriptASTParser** (`modules/ingest/parsers/typescript_parser.py`)
```
├── tree_sitter, tree_sitter_typescript
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

**SolidityASTParser** (`modules/ingest/parsers/solidity_parser.py`)
```
├── tree_sitter, tree_sitter_solidity
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

**DocumentationParser** (`modules/ingest/parsers/documentation_parser.py`)
```
├── markdown → Markdown parsing
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

**YAMLParser** (`modules/ingest/parsers/yaml_parser.py`)
```
├── yaml → YAML parsing
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

**TerraformParser** (`modules/ingest/parsers/terraform_parser.py`)
```
├── hcl2 → HCL2 parsing (Terraform syntax)
├── hashlib → chunk_hash generation
└── modules/ingest/core/config → IngestionConfig
```

### Layer 6: Management Scripts

**Repository Cloner** (`modules/ingest/scripts/repo_cloner.py`)
```
├── subprocess → git clone execution
├── modules/ingest/core/config → REPOSITORIES
└── External: GitHub API (via git CLI)
```

**Collection Manager** (`modules/ingest/scripts/collection_manager.py`)
```
├── modules/ingest/services/vector_client → QdrantVectorClient
├── modules/ingest/core/config → IngestionConfig
└── External: Qdrant API
```

**Stats Reporter** (`modules/ingest/scripts/stats_reporter.py`)
```
├── modules/ingest/services/vector_client → QdrantVectorClient
├── modules/ingest/core/config → IngestionConfig
└── External: Qdrant API
```

**Repository Metadata** (`modules/ingest/scripts/repo_metadata.py`)
```
├── subprocess → git log/show execution
├── modules/ingest/core/config → REPOSITORIES
└── External: Git repository state
```

**Search Test** (`modules/ingest/scripts/search_test.py`)
```
├── modules.ingest → IngestionPipeline
└── External: Qdrant API (via IngestionPipeline)
```

## Import Dependency Tree

```
modules/__init__.py
└── modules.ingest
    └── modules/ingest/core/pipeline.py
        ├── modules/ingest/core/config.py
        │
        ├── modules/ingest/core/embedding_service.py
        │   ├── requests
        │   └── External: Cloudflare AI Gateway / Modal TEI
        │
        ├── modules/ingest/services/vector_client.py
        │   ├── qdrant_client
        │   └── External: Qdrant API
        │
        ├── modules/ingest/core/file_processor.py
        │   ├── modules/ingest/parsers/rust_parser.py
        │   │   └── tree_sitter, tree_sitter_rust
        │   ├── modules/ingest/parsers/typescript_parser.py
        │   │   └── tree_sitter, tree_sitter_typescript
        │   ├── modules/ingest/parsers/solidity_parser.py
        │   │   └── tree_sitter, tree_sitter_solidity
        │   ├── modules/ingest/parsers/documentation_parser.py
        │   │   └── markdown
        │   ├── modules/ingest/parsers/yaml_parser.py
        │   │   └── yaml
        │   └── modules/ingest/parsers/terraform_parser.py
        │       └── hcl2
        │
        ├── modules/ingest/core/batch_processor.py
        ├── modules/ingest/core/storage_manager.py
        └── modules/ingest/core/checkpoint_manager.py
```

## External Package Dependencies

### Core Pipeline
```python
python-dotenv>=1.0.0     # Environment variable management
```

### Vector Search
```python
qdrant-client>=1.7.0     # Qdrant vector database client
numpy>=1.24.0            # Array operations for vectors
```

### Parsing
```python
tree-sitter>=0.21.0      # AST parsing core
tree-sitter-rust         # Rust grammar
tree-sitter-typescript   # TypeScript grammar
tree-sitter-solidity     # Solidity grammar (custom)
markdown>=3.5.0          # Markdown parsing
beautifulsoup4>=4.12.0   # HTML parsing in markdown
```

### Embedding Service
```python
requests>=2.31.0         # HTTP client for embedding APIs
aiohttp>=3.9.0           # Async HTTP for warmup
modal>=0.65.0            # Modal platform (if using Modal TEI)
```

### Development
```python
pytest>=7.4.0            # Testing framework
black>=23.0.0            # Code formatting
mypy>=1.5.0              # Type checking
```

## Circular Dependency Prevention

### No Circular Dependencies

The ingestion system has a clean, hierarchical dependency structure:
- **Scripts** → **Pipeline** → **Services/Parsers** → **Config**
- No module depends on modules higher in the hierarchy
- All external dependencies are at the leaf nodes

### Lazy Initialization Pattern

Used to reduce startup time and memory footprint:

```python
# modules/ingest/core/pipeline.py
@property
def vector_client(self):
    if self._vector_client is None:
        self._vector_client = QdrantVectorClient()
    return self._vector_client
```

## Dependency Injection Points

### Pipeline Construction
```python
# Makefile controls dependency injection
pipeline = IngestionPipeline(
    skip_vector_init=False,  # Control vector client initialization
    config=IngestionConfig()  # Custom configuration
)
```

### Service Injection
```python
# Pipeline injects services into processors
file_processor = FileProcessor(
    embedding_service=self.embedding_service,
    vector_client=self.vector_client
)
```

## Version Compatibility Matrix

| Module | Python | Qdrant | Modal | Tree-sitter |
|--------|--------|--------|-------|-------------|
| ingest/* | 3.11+ | 1.7.0+ | 0.65+ | 0.21.0+ |
| parsers/* | 3.11+ | N/A | N/A | 0.21.0+ |
| services/* | 3.11+ | 1.7.0+ | 0.65+ | N/A |
| scripts/* | 3.11+ | 1.7.0+ | N/A | N/A |

## Breaking Changes Log

### v3.0.0-ingestion-only (Current)
- **Breaking:** Removed `modules/core`, `modules/training`, `modules/cli`
- **Breaking:** Top-level `modules/__init__.py` now only exports `IngestionPipeline` and config
- **Migration:** Import from `modules.ingest` directly instead of top-level `modules`

### v2.0.0-meta-reasoning (Previous)
- Integrated I2P meta-reasoning with ingestion pipeline
- Added DSPy-based query generation (GEPA)
- Created cross-system dependencies (now removed)

### v1.5.0
- Added multi-language parser support
- Implemented checkpoint resume capability
- Separated embedding service backends

---

**Note:** When adding new parsers or services, update this document to maintain the dependency graph.
