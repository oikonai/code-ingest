# Code Ingestion System Architecture Overview

> **Last Updated:** 2026-02-04
> **Version:** 3.0.0-ingestion-only
> **Maintainer:** Auto-synced with codebase changes

## Executive Summary

The Code Ingestion System is a production-ready pipeline for transforming GitHub repositories into searchable vector databases. It supports multi-language parsing (Rust, TypeScript, Solidity, Documentation), semantic embedding generation, and efficient vector storage in Qdrant.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Repositories                       │
│                 (your GitHub organization)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Repository Manager                         │
│            modules/ingest/scripts/repo_cloner.py            │
│                                                             │
│  - Priority-based cloning (high/medium/low/ALL)            │
│  - GitHub PAT authentication                                │
│  - Metadata capture (commits, branches)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 Ingestion Pipeline                          │
│              modules/ingest/core/pipeline.py                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   File       │→ │   Language   │→ │   Batch      │      │
│  │  Processor   │  │   Parsers    │  │  Processor   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│          ↓                ↓                  ↓              │
│  ┌────────────────────────────────────────────────────┐     │
│  │        Checkpoint Manager (Resume Support)         │     │
│  └────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼──────────┐            ┌─────────▼────────┐
│ Embedding Service│            │ Qdrant Vector DB │
│                  │            │                  │
│ DeepInfra API    │────────────│  rust            │
│ (OpenAI-compat)  │            │  typescript      │
│                  │            │  solidity        │
│ Qwen3-Embedding  │            │  documentation   │
│ -8B-batch        │            └──────────────────┘
└──────────────────┘
```

## Core Components

### 1. **Ingestion Pipeline** (`modules/ingest/core/pipeline.py`)

Main orchestrator for multi-language code ingestion into vector database.

**Responsibilities:**
- Repository-level ingestion coordination
- Service initialization (embedding, vector client)
- Progress tracking and checkpoint management
- Statistics collection and reporting

**Key Methods:**
- `ingest_repositories()` - Main entry point for batch ingestion
- `warmup_services()` - Pre-warm embedding service
- `search_across_languages()` - Cross-language semantic search

### 2. **Language Parsers** (`modules/ingest/parsers/`)

AST-based parsing for extracting meaningful code chunks.

**Supported Languages:**
- **Rust** (`rust_parser.py`) - Functions, structs, impls, traits, macros
- **TypeScript** (`typescript_parser.py`) - Components, functions, interfaces, types
- **Solidity** (`solidity_parser.py`) - Contracts, functions, events, interfaces
- **Documentation** (`documentation_parser.py`) - Markdown sections, headings
- **YAML** (`yaml_parser.py`) - CI/CD configs, Kubernetes manifests
- **Terraform** (`terraform_parser.py`) - Resource definitions, modules

**Common Features:**
- Tree-sitter based AST parsing
- Context-aware chunk extraction
- Metadata enrichment (file path, line numbers, signature)
- Hash-based deduplication

### 3. **Embedding Service** (`modules/ingest/core/embedding_service.py`)

Generates semantic embeddings for code chunks using DeepInfra's OpenAI-compatible API.

**Backend:**
- **DeepInfra API** - Qwen3-Embedding-8B-batch (4096D) via OpenAI-compatible endpoint

**Features:**
- Batch embedding generation
- Automatic retry on transient failures
- Rate limiting and concurrency control (4 concurrent requests)
- Embedding validation (dimension, NaN, None checks)

### 4. **Vector Storage** (`modules/ingest/services/vector_client.py`)

Qdrant vector database client for efficient storage and retrieval.

**Features:**
- Language-specific collections
- Metadata filtering
- Cosine similarity search
- Batch upsert operations

### 5. **Repository Management** (`modules/ingest/scripts/`)

Command-line scripts for repository and collection management.

**Tools:**
- `repo_cloner.py` - Clone GitHub repositories with priority filtering
- `collection_manager.py` - Manage Qdrant collections (cleanup, status)
- `stats_reporter.py` - Generate ingestion statistics reports
- `repo_metadata.py` - Capture repository commit metadata
- `search_test.py` - Test vector search functionality

## Data Flow

### Complete Ingestion Lifecycle

```
GitHub Repo Selection (Priority Filter)
    ↓
[Clone] git clone with PAT authentication
    ↓
[File Discovery] Recursively scan for supported file types
    ↓
[Parsing] Language-specific AST extraction
    ↓
[Chunking] Context-aware code chunk generation
    ↓
[Embedding] Batch embedding via API (4096D vectors)
    ↓
[Upsert] Store in Qdrant with metadata
    ↓
[Checkpoint] Save progress for resume capability
    ↓
[Statistics] Generate ingestion metrics report
```

### Vector Search Flow

```
User Query String
    ↓
[Embedding] Generate query embedding (4096D)
    ↓
[Search] Query Qdrant collections (score > 0.3)
    ↓
[Ranking] Enhanced ranking (similarity + recency + file type)
    ↓
[Deduplication] Remove duplicates by chunk_hash
    ↓
[Formatting] Return top N unique results with metadata
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Parsing | **tree-sitter** | Fast, robust AST parsing for all languages |
| Embeddings | **Qwen3-Embedding-8B-batch** | State-of-the-art code embeddings (4096D) |
| Vector Database | **Qdrant Cloud** | Scalable vector storage and similarity search |
| Embedding Backend | **DeepInfra API** | OpenAI-compatible API for embedding generation |
| Language Support | **Rust, TypeScript, Solidity, Markdown, YAML, Terraform** | Comprehensive language coverage |

## External Dependencies

### Required Services

1. **Qdrant** (`QDRANT_URL`, `QDRANT_API_KEY`)
   - Collections: rust, typescript, solidity, documentation
   - 4096-dimensional vectors (cosine similarity)
   - Cloud or self-hosted deployment

2. **Embedding Service**
   - **DeepInfra API** (`DEEPINFRA_API_KEY`)
     - Provider: DeepInfra
     - Model: Qwen/Qwen3-Embedding-8B-batch (4096D)
     - OpenAI-compatible API endpoint
     - Minimal cold starts, instant availability
     - Rate limit: 4 concurrent requests

3. **GitHub** (Optional, for private repos)
   - Personal Access Token (`GITHUB_TOKEN`)
   - Required for cloning private repositories

## Critical Architectural Decisions

### 1. Language-Specific Collections
**Decision:** Separate Qdrant collections per language
**Rationale:** Language-specific semantic search provides better relevance
**Trade-off:** More storage overhead vs. higher precision

### 2. AST-Based Parsing
**Decision:** Use tree-sitter for all language parsing
**Rationale:** Robust, fast, and supports incremental parsing
**Trade-off:** Parser setup complexity vs. parsing quality

### 3. Checkpoint Resume
**Decision:** Save progress after each repository
**Rationale:** Long ingestion jobs can be interrupted (network, API limits)
**Trade-off:** Checkpoint overhead vs. resume capability

### 4. Batch Embedding
**Decision:** Process embeddings in concurrent batches
**Rationale:** Maximize throughput while respecting API rate limits
**Trade-off:** Memory usage vs. processing speed

### 5. Documentation Separation
**Decision:** Store documentation in separate collection
**Rationale:** Prevent documentation patterns from contaminating code search
**Trade-off:** Additional collection management vs. search quality

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Embedding Generation | Varies | Depends on DeepInfra API rate limits and batch size |
| Ingestion Throughput | Varies | Depends on repo size, language mix |
| Vector Collections | 50K+ chunks | Across rust/typescript/solidity/documentation |
| Search Latency | <200ms | Per query, excluding embedding generation |
| Score Threshold | 0.3 | Cosine similarity cutoff |
| Chunk Size (Code) | 500 tokens | With 50 token overlap |
| Chunk Size (Docs) | 6k-12k chars | Intelligent section grouping |

## Scalability

### Current Limits
- **Concurrent ingestion**: Sequential (one repo at a time)
- **Vector storage**: Unlimited (Qdrant Cloud scales automatically)
- **Embedding generation**: 4 concurrent requests (rate-limited via semaphore)
- **API rate limits**: Managed by retry logic and backoff

### Scaling Strategies
1. **Horizontal**: Multiple ingestion workers (requires coordination)
2. **Vertical**: Increase DeepInfra API rate limit (adjust `rate_limit` parameter)
3. **Caching**: Deduplicate chunks before embedding generation
4. **Batch size**: Tune batch size for optimal throughput/memory balance

## Monitoring and Observability

### Health Checks
- `make health` - Pipeline + vector search connectivity
- `make vector-status` - Collection stats (points, indexed vectors)

### Statistics
- Per-repository ingestion metrics
- Collection-level vector counts
- Embedding service performance
- Search quality metrics

### Logging
- Pipeline steps with timestamps
- Embedding service request/retry counts
- Vector upsert validation failures
- Parser errors and skipped files

## Security Considerations

### Secrets Management
- All API keys via environment variables (`.env`)
- No secrets in codebase or version control
- DeepInfra API key for embedding generation

### Data Privacy
- Code chunks stored in Qdrant (consider data location)
- Embeddings generated on controlled infrastructure
- GitHub PAT with minimal scope (repo read-only)

### Access Control
- Qdrant API key authentication
- DeepInfra API key authentication
- GitHub PAT for repository access

## Related Documentation

- [Ingestion Pipeline Details](../modules/ingest/PIPELINE.md)
- [Language Parser Documentation](../modules/ingest/PARSERS.md)
- [Module Dependency Graph](./DEPENDENCIES.md)
- [Data Flow Details](./DATA_FLOW.md)
- [Vector Search Architecture](./VECTOR_SEARCH.md)

---

**Note:** This document is automatically maintained. When making architectural changes, update this file to reflect the new structure.
