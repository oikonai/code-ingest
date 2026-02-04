# Code Ingestion System Development Guidelines

This document outlines the coding principles and best practices for the Code Ingestion System. These guidelines ensure maintainable, scalable, and robust implementations.

## 📏 File Length and Structure

- **Never allow a file to exceed 500 lines.**
- If a file approaches 400 lines, break it up immediately.
- Treat 1000 lines as unacceptable, even temporarily.
- Use folders and naming conventions to keep small files logically grouped.

*Example: Split large parsers into focused components like `modules/ingest/parsers/rust_parser.py`, `modules/ingest/parsers/typescript_parser.py`, etc.*

## 🔄 OOP First

- Every functionality should be in a dedicated class, struct, or protocol, even if it's small.
- Favor composition over inheritance, but always use object-oriented thinking.
- Code must be built for reuse, not just to "make it work."

*Example: The `IngestionPipeline`, `RustASTParser`, and `EmbeddingService` classes each handle specific responsibilities.*

## 🎯 Single Responsibility Principle

- Every file, class, and function should do one thing only.
- If it has multiple responsibilities, split it immediately.
- Each manager, parser, or service should be laser-focused on one concern.

*Example: `RustASTParser` only handles Rust AST parsing, `EmbeddingService` only handles embedding generation, `QdrantVectorClient` only handles vector database operations.*

## 🧩 Modular Design

- Code should connect like Lego - interchangeable, testable, and isolated.
- Ask: "Can I reuse this class in a different context?" If not, refactor it.
- Reduce tight coupling between components. Favor dependency injection or protocols.

*Example: Language parsers are designed to be interchangeable - all implement the same interface and can be swapped without changing the pipeline.*

## 🏗️ Manager and Coordinator Patterns

Use clear naming conventions for logic separation:
- **Pipeline orchestration** → `IngestionPipeline`
- **Service wrappers** → `EmbeddingService`, `QdrantVectorClient`
- **Processing logic** → `FileProcessor`, `BatchProcessor`
- Never mix orchestration and business logic directly.

*Example: `IngestionPipeline` coordinates between parsers, embedding service, and vector client without containing their logic.*

## 📐 Function and Class Size

- Keep functions under 30-40 lines.
- If a class is over 200 lines, assess splitting into smaller helper classes.

*Example: Break down complex parsing methods into focused helper methods like `_extract_function_chunks()`, `_parse_struct_definitions()`, etc.*

## 🏷️ Naming and Readability

- All class, method, and variable names must be descriptive and intention-revealing.
- Avoid vague names like `data`, `info`, `helper`, or `temp`.

*Example: Use `embedding_response` instead of `result`, `rust_ast_parser` instead of `parser`, `vector_points` instead of `data`.*

## 📈 Scalability Mindset

- Always code as if someone else will scale this.
- Include extension points (e.g., protocol conformance, dependency injection) from day one.

*Example: The `IngestionConfig` class is designed to be extensible - new repository configurations can be added without modifying existing code.*

## 🚫 Avoid God Classes

- Never let one file or class hold everything (e.g., massive Pipeline, Parser, or Service).
- Split into focused components (Orchestrator, Parsers, Services, Processors).

*Example: Instead of one massive `Ingestion` class, we have separate `IngestionPipeline`, `FileProcessor`, `BatchProcessor`, `EmbeddingService`, and `QdrantVectorClient` classes.*

## Ingestion-Specific Guidelines

### 🌳 Parser Design

- Each language parser should implement a consistent interface
- Use tree-sitter for robust AST parsing
- Extract metadata alongside code chunks (file path, line numbers, signature)
- Generate deterministic chunk hashes for deduplication

```python
class RustASTParser:
    def parse_file(self, file_path: Path, content: str) -> List[Dict]:
        """Parse Rust file and extract code chunks."""
        tree = self.parser.parse(content.encode('utf-8'))
        chunks = self._extract_chunks(tree.root_node, file_path, content)
        return [self._enrich_metadata(chunk) for chunk in chunks]
    
    def _extract_chunks(self, node, file_path, content):
        # Focused chunk extraction logic
        pass
    
    def _enrich_metadata(self, chunk):
        # Add metadata (hash, signature, etc.)
        pass
```

### 🔧 Service Integration

- Separate service clients from business logic
- Implement proper error handling and retry logic
- Use async patterns for I/O-bound operations
- Centralize service configuration

```python
class EmbeddingService:
    def __init__(self, config: IngestionConfig):
        self.config = config
        self.backend = self._initialize_backend()
        
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with retry logic."""
        try:
            return self.backend.embed(texts)
        except Exception as e:
            return self._retry_with_backoff(texts, e)
```

### 📊 Error Handling and Recovery

- Implement graceful degradation for file-level errors
- Use checkpoint system for resume capability
- Log errors with context (file path, line number, error type)
- Track statistics for failed operations

```python
class IngestionPipeline:
    def ingest_repositories(self, resume_from_checkpoint: bool = True):
        """Ingest with checkpoint resume support."""
        checkpoint = self._load_checkpoint() if resume_from_checkpoint else None
        
        for repo in self.repositories:
            if checkpoint and repo.name in checkpoint['completed_repos']:
                continue
                
            try:
                stats = self._ingest_repository(repo)
                self._save_checkpoint(repo.name, stats)
            except Exception as e:
                logger.error(f"Failed to ingest {repo.name}: {e}")
                continue  # Graceful degradation
```

### 🔄 Pipeline Architecture

- Use the pipeline pattern for multi-stage processing
- Each pipeline stage should be independently testable
- Implement proper data flow between stages
- Support both sequential and batch processing

```python
class IngestionPipeline:
    def __init__(self, config: IngestionConfig):
        self.file_processor = FileProcessor(config)
        self.batch_processor = BatchProcessor(config)
        self.embedding_service = EmbeddingService(config)
        self.vector_client = QdrantVectorClient(config)
        
    def _ingest_repository(self, repo: RepositoryConfig):
        # Stage 1: File discovery and parsing
        chunks = self.file_processor.process_repository(repo)
        
        # Stage 2: Batch embedding generation
        embeddings = self.batch_processor.generate_embeddings(chunks)
        
        # Stage 3: Vector storage
        self.vector_client.upsert_vectors(embeddings)
```

### 🎯 Configuration Management

- **Repository configurations** live in `config/repositories.yaml` (not hard-coded in Python)
- Centralize configuration in dedicated config files
- Use environment variables for sensitive information and overrides
- Validate configuration at startup
- Provide sensible defaults

**Repository configuration example (config/repositories.yaml):**
```yaml
repos_base_dir: ./repos

repositories:
  - id: my-service
    github_url: https://github.com/myorg/my-service
    repo_type: backend
    languages: [rust, yaml]
    components: [api, lib]
    priority: high
```

**Pipeline configuration example:**
```python
@dataclass
class IngestionConfig:
    """Configuration for ingestion pipeline."""
    repos_base_dir: str = "./repos"  # Loaded from repositories.yaml
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL"))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv("QDRANT_API_KEY"))
    deepinfra_api_key: str = field(default_factory=lambda: os.getenv("DEEPINFRA_API_KEY"))
    batch_size: int = 50
    score_threshold: float = 0.3
    
    def validate(self):
        """Validate required configuration."""
        if not self.qdrant_url or not self.qdrant_api_key:
            raise ValueError("Qdrant configuration required")
        if not self.deepinfra_api_key:
            raise ValueError("DeepInfra API key required for embeddings")
```

**Key principles:**
- Never hard-code repository lists in Python - use config/repositories.yaml
- Environment variable `REPOSITORIES_CONFIG` can override config file path
- Loader validates config schema and provides clear error messages

### Shared Collections Configuration (Ingest + MCP)

**File:** `config/collections.yaml`

**Purpose:** Single source of truth for collection names. The ingestion pipeline writes to these collections; the MCP server searches them. Keeping them in sync ensures search works correctly.

**Format:** Set `collection_prefix` once (e.g. `myproject`). All other values are **suffixes only**; loaders build full names as `{prefix}_{suffix}` (or just `suffix` when prefix is empty). This avoids repeating the prefix in every entry.

**Structure:**
```yaml
collection_prefix: myproject  # Optional; leave empty for no prefix

language_collections:
  rust: code_rust
  typescript: code_typescript
  # ...

service_collections:
  frontend: frontend
  backend: backend
  # ...

concern_collections:
  api_contracts: api_contracts
  database_schemas: database_schemas
  # ...

aliases:
  rust: code_rust
  ts: code_typescript
  # ...

default_collection: code_rust  # suffix
```

**Migration:** If you have an existing file with full names in every value (e.g. `rust: myproject_code_rust`), strip the prefix from each value and set `collection_prefix: myproject` at the top.

**Usage:**
- **Ingest:** `modules/ingest/core/config.py` loads this file to determine collection names when storing vectors
- **MCP:** `mcp/src/config.py` loads the same file to determine collection names when searching
- **Override:** Set `COLLECTIONS_CONFIG` env var to use a different path (both ingest and MCP respect this)

**Why shared config?** Without it, if you change collection names in one place, the other breaks. This config ensures what you ingest is what you can search.

## 🗄️ Vector Database Backends

The system supports two vector database backends via the `VECTOR_BACKEND` environment variable:

### Qdrant (Cloud/Remote)
- **Use when**: Cloud deployment, managed vector database
- **Configuration**: Set `VECTOR_BACKEND=qdrant`, `QDRANT_URL`, `QDRANT_API_KEY`
- **Client**: `modules/ingest/services/vector_client.py` (QdrantVectorClient)

### SurrealDB (Local/Docker)
- **Use when**: Local development, Docker Compose, self-hosted
- **Configuration**: Set `VECTOR_BACKEND=surrealdb`, `SURREALDB_URL`, `SURREALDB_NS`, `SURREALDB_DB`
- **Client**: `modules/ingest/services/surrealdb_vector_client.py` (SurrealDBVectorClient)
- **Docker**: See `docker/README.md` for Docker Compose setup

**Backend Abstraction**: Both backends implement the same `VectorBackend` protocol defined in `modules/ingest/core/vector_backend.py`, allowing seamless switching between cloud and local deployments.

## 🐳 Docker Compose Local Setup

For local development with Docker:

1. Configure environment: `cp .env.example .env` and set `VECTOR_BACKEND=surrealdb`
2. Start services: `docker compose up`
3. Check health: `curl http://localhost:8001/health`

See `docker/README.md` for complete Docker Compose documentation.

## 🚀 Implementation Checklist

Before submitting any ingestion system code, ensure:

- [ ] Each file is under 500 lines
- [ ] Classes have single, clear responsibilities
- [ ] Language parsers use tree-sitter for AST parsing
- [ ] Error handling is implemented for service failures
- [ ] Checkpoint system supports resume capability
- [ ] Configuration is externalized and validated
- [ ] Code is testable with mock data and integration tests
- [ ] Vector backend abstraction is used (not direct Qdrant/SurrealDB imports)
- [ ] **Documentation is updated in `docs/` to reflect code changes**

## 📚 Documentation Sync Requirements

**CRITICAL: All code changes MUST be reflected in technical documentation.**

### Documentation Structure

```
docs/
├── architecture/         # System architecture and design
│   ├── OVERVIEW.md      # High-level architecture, tech stack
│   ├── DEPENDENCIES.md  # Module dependency graph
│   ├── DATA_FLOW.md     # Ingestion lifecycle, data transformations
│   └── VECTOR_SEARCH.md # Vector search architecture
│
├── modules/             # Per-module technical docs
│   └── ingest/
│       ├── PIPELINE.md  # IngestionPipeline
│       └── PARSERS.md   # Language parsers
│
└── api/                 # API reference docs (if applicable)
    └── README.md        # Public API documentation
```

### When to Update Documentation

**ALWAYS update documentation when you:**

1. **Add a new parser** → Update `docs/modules/ingest/PARSERS.md`
   - Document chunk extraction logic
   - Include usage examples
   - Link to parser source file

2. **Add/remove dependencies** → Update `docs/architecture/DEPENDENCIES.md`
   - Add to dependency graph
   - Document import paths
   - Note version compatibility

3. **Modify data flow** → Update `docs/architecture/DATA_FLOW.md`
   - Update ingestion lifecycle diagrams
   - Document new data transformations
   - Update performance characteristics

4. **Change architecture** → Update `docs/architecture/OVERVIEW.md`
   - Update high-level diagrams
   - Document architectural decisions
   - Update component descriptions

5. **Add external service** → Update `docs/architecture/OVERVIEW.md` + relevant module docs
   - Document API endpoints
   - Add authentication requirements
   - Document error handling

6. **Modify ingestion process** → Update `docs/modules/ingest/PIPELINE.md`
   - Document new processing steps
   - Update configuration options
   - Update performance metrics

### Documentation Standards

**All technical documentation MUST include:**

- **Last Updated:** Date of last modification
- **File Reference:** Actual file path in codebase
- **Class Signatures:** Complete parameter lists with types
- **Usage Examples:** Working code examples
- **Error Handling:** Expected exceptions and recovery
- **Performance Notes:** Typical execution times, bottlenecks
- **Related Docs:** Links to dependent/related documentation

**Example Template:**

```markdown
# Module Name

> **File:** `modules/ingest/category/filename.py`
> **Class:** `ClassName`
> **Last Updated:** YYYY-MM-DD

## Overview
[Brief description of purpose]

## Class Signature
[Complete class definition with parameters]

## Methods
[Each method with parameters, returns, raises]

## Usage Examples
[Working code examples]

## Related Documentation
[Links to related docs]
```

### Automation Checklist

**Before committing code changes:**

1. ✅ Update relevant module documentation in `docs/modules/ingest/`
2. ✅ Update dependency graph if imports changed
3. ✅ Update data flow if processing steps changed
4. ✅ Update architecture overview if design changed
5. ✅ Run `make health` to verify system integrity
6. ✅ Update README.md if user-facing features changed

### Documentation Review Process

**During code review, verify:**

- [ ] Documentation reflects actual code implementation
- [ ] Examples in docs execute without errors
- [ ] Dependency graph is updated
- [ ] Breaking changes are clearly documented
- [ ] Performance characteristics are accurate
- [ ] Error handling is documented

## 🤝 Contributing

1. Follow the guidelines in this document
2. Ensure all files remain under 500 lines
3. Use single responsibility principle
4. Add comprehensive tests for new features
5. Maintain security best practices
6. Update documentation before committing

## 📚 Additional Resources

- [System Architecture](./docs/architecture/OVERVIEW.md) - High-level system design
- [Module Documentation](./docs/modules/ingest/) - Per-module technical docs
- [Data Flow](./docs/architecture/DATA_FLOW.md) - Ingestion lifecycle
- [Dependencies](./docs/architecture/DEPENDENCIES.md) - Module dependency graph

---

**Remember:** Code and documentation must stay in sync. Outdated documentation is worse than no documentation. Every code change is a documentation change.
