# I2P Technical Documentation

> **Comprehensive technical reference for the I2P Meta-Reasoning System**
> **Last Updated:** 2025-10-01
> **Maintained automatically with code changes**

## 📚 Documentation Structure

### 🏗️ Architecture

High-level system design, data flows, and architectural decisions.

- **[ARCHITECTURE.md](./architecture/ARCHITECTURE.md)** - 🆕 Master architecture guide and navigation hub
- **[OVERVIEW.md](./architecture/OVERVIEW.md)** - System architecture, components, tech stack
- **[DEPENDENCIES.md](./architecture/DEPENDENCIES.md)** - Complete module dependency graph
- **[DATA_FLOW.md](./architecture/DATA_FLOW.md)** - Request lifecycle and data transformations
- **[DSPY_SIGNATURES.md](./architecture/DSPY_SIGNATURES.md)** - DSPy signature reference
- **[VECTOR_SEARCH.md](./architecture/VECTOR_SEARCH.md)** - Vector search architecture

### 🔧 Core Modules

Technical documentation for core pipeline components.

- **[PIPELINE.md](./modules/core/PIPELINE.md)** - `I2PModularPipeline` orchestrator
- **[CLASSIFIER.md](./modules/core/CLASSIFIER.md)** - `SystemBoundaryAnalyzer`
- **[ANALYZER.md](./modules/core/ANALYZER.md)** - `StrategicGapAnalyzer`
- **[GENERATOR.md](./modules/core/GENERATOR.md)** - `CodeNavigationIndexGenerator`
- **[VECTOR_SEARCH.md](./modules/core/VECTOR_SEARCH.md)** - `VectorSearchManager`
- **[VALIDATION.md](./modules/core/VALIDATION.md)** - `ValidatorManager`

### 🤖 Training System

GEPA model training, dataset management, and optimization.

- **[GEPA.md](./modules/training/GEPA.md)** - GEPA query generation and training *(Coming soon)*
- **[DATASETS.md](./modules/training/DATASETS.md)** - Dataset formats and management *(Coming soon)*
- **[METRICS.md](./modules/training/METRICS.md)** - Training metrics and evaluation *(Coming soon)*

### 🗄️ Ingestion Pipeline

Multi-language code ingestion and vector storage.

- **[PIPELINE.md](./modules/ingest/PIPELINE.md)** - `IngestionPipeline` orchestrator
- **[PARSERS.md](./modules/ingest/PARSERS.md)** - Language-specific AST parsers
- **[EMBEDDING.md](./modules/ingest/EMBEDDING.md)** - Modal TEI service integration *(Coming soon)*
- **[VECTOR_CLIENT.md](./modules/ingest/VECTOR_CLIENT.md)** - Qdrant client *(Coming soon)*

### 🔌 API Reference

Public API documentation for external integrations.

- **[README.md](./api/README.md)** - API overview and endpoints *(Coming soon)*

### 📖 Guides

Step-by-step guides for common tasks.

- **[TRAINING.md](./guides/TRAINING.md)** - Training GEPA models
- **[INGESTION.md](./guides/INGESTION.md)** - Ingesting new codebases *(Coming soon)*
- **[DEPLOYMENT.md](./guides/DEPLOYMENT.md)** - Deployment and configuration *(Coming soon)*

## 🚀 Quick Navigation

### By Use Case

**Want to understand the system?**
→ Start with [Architecture Guide](./architecture/ARCHITECTURE.md) or [Architecture Overview](./architecture/OVERVIEW.md)

**Adding a new module?**
→ Check [Dependencies](./architecture/DEPENDENCIES.md) and [CLAUDE.md](../CLAUDE.md)

**Training GEPA models?**
→ See [GEPA Documentation](./modules/training/GEPA.md)

**Ingesting code?**
→ See [Ingestion Pipeline](./modules/ingest/PIPELINE.md)

**Troubleshooting?**
→ Check module-specific docs + `make health`

### By Component

| Component | Documentation | Source Code |
|-----------|--------------|-------------|
| **Pipeline** | [PIPELINE.md](./modules/core/PIPELINE.md) | `modules/core/pipeline.py` |
| **Boundary Analyzer** | [CLASSIFIER.md](./modules/core/CLASSIFIER.md) | `modules/core/classifier.py` |
| **Gap Analyzer** | [ANALYZER.md](./modules/core/ANALYZER.md) | `modules/core/analyzer.py` |
| **Navigation Generator** | [GENERATOR.md](./modules/core/GENERATOR.md) | `modules/core/generator.py` |
| **Vector Search** | [VECTOR_SEARCH.md](./modules/core/VECTOR_SEARCH.md) | `modules/core/vector_search.py` |
| **GEPA Module** | [GEPA.md](./modules/training/GEPA.md) | `modules/core/gepa.py`, `modules/training/gepa_trainer.py` |
| **Ingestion** | [PIPELINE.md](./modules/ingest/PIPELINE.md) | `modules/ingest/core/pipeline.py` |
| **Parsers** | [PARSERS.md](./modules/ingest/PARSERS.md) | `modules/ingest/parsers/*.py` |
| **Embeddings** | [EMBEDDING.md](./modules/ingest/EMBEDDING.md) | `modules/ingest/core/embedding_service.py` |

## 📋 Documentation Standards

All technical documentation follows these standards (enforced by [CLAUDE.md](../CLAUDE.md)):

### Required Sections

1. **Header** - File reference, class name, last updated date
2. **Overview** - Brief purpose and context
3. **Class Signature** - Complete parameter definitions
4. **Methods** - All public methods with parameters/returns/raises
5. **Usage Examples** - Working code examples
6. **Error Handling** - Expected exceptions
7. **Performance Notes** - Typical execution times
8. **Related Documentation** - Links to related docs

### Example Structure

```markdown
# Module Name

> **File:** `modules/category/filename.py`
> **Class:** `ClassName`
> **Last Updated:** YYYY-MM-DD

## Overview
[Description]

## Class Signature
[Full class definition]

## Methods
[Method documentation]

## Usage Examples
[Code examples]

## Related Documentation
[Links]
```

## 🔄 Keeping Documentation in Sync

**Critical:** Documentation must stay synchronized with code changes.

### When Code Changes

**ALWAYS update documentation when:**
- Adding/removing modules
- Changing DSPy signatures
- Modifying data flows
- Adding dependencies
- Changing architecture
- Adding external services
- Modifying training process

See [CLAUDE.md - Documentation Sync](../CLAUDE.md#documentation-sync-requirements) for complete requirements.

### Verification Checklist

Before committing:
- ✅ Module docs reflect actual implementation
- ✅ Examples execute without errors
- ✅ Dependency graph is updated
- ✅ Breaking changes documented
- ✅ Performance characteristics accurate

## 🛠️ Contributing to Documentation

### Adding New Documentation

1. **Choose appropriate location:**
   - Architecture changes → `docs/architecture/`
   - Module docs → `docs/modules/{core|training|ingest}/`
   - Guides → `docs/guides/`

2. **Follow template structure** (see above)

3. **Update this README** with new links

4. **Link related documentation** bidirectionally

### Updating Existing Documentation

1. **Update "Last Updated" date**
2. **Verify examples still work**
3. **Check related docs** for impact
4. **Update dependency graph** if needed

## 📊 Documentation Coverage

| Module | Status | Last Updated |
|--------|--------|--------------|
| **Architecture** | **6/6 Complete** |  |
| ├─ Architecture Guide | ✅ Complete | 2025-10-01 |
| ├─ Overview | ✅ Complete | 2025-10-01 |
| ├─ Dependencies | ✅ Complete | 2025-10-01 |
| ├─ Data Flow | ✅ Complete | 2025-10-01 |
| ├─ DSPy Signatures | ✅ Complete | 2025-10-01 |
| └─ Vector Search | ✅ Complete | 2025-10-01 |
| **Core Modules** | **5/6 Complete** |  |
| ├─ Pipeline | ✅ Complete | 2025-10-01 |
| ├─ Classifier | ✅ Complete | 2025-10-01 |
| ├─ Analyzer | ✅ Complete | 2025-10-01 |
| ├─ Generator | ✅ Complete | 2025-10-01 |
| ├─ Vector Search | ✅ See Architecture | 2025-10-01 |
| └─ Validation | ✅ Complete | 2025-10-01 |
| **Training** | **1/3 Complete** |  |
| ├─ GEPA | ✅ Complete | 2025-10-01 |
| ├─ Datasets | 🔄 Coming soon | - |
| └─ Metrics | 🔄 Coming soon | - |
| **Ingestion** | **2/4 Complete** |  |
| ├─ Pipeline | ✅ Complete | 2025-10-01 |
| ├─ Parsers | ✅ Complete | 2025-10-01 |
| ├─ Embeddings | 🔄 Coming soon | - |
| └─ Vector Client | 🔄 Coming soon | - |
| **Guides** | **1/3 Complete** |  |
| ├─ Training | ✅ Complete | 2025-10-01 |
| ├─ Ingestion | 🔄 Coming soon | - |
| └─ Deployment | 🔄 Coming soon | - |
| **Meta-Documentation** | **2/2 Complete** |  |
| ├─ Documentation Guide | ✅ Complete | 2025-10-01 |
| └─ Index (README) | ✅ Complete | 2025-10-01 |

**Overall Progress:** 17/25 files (68% complete)
**High-Priority Complete:** 6/6 architecture docs ✅, 5/5 core module docs ✅, 2/4 ingestion docs ✅, 1/3 guides ✅

## 🔗 External Resources

- **[Main README](../README.md)** - User-facing documentation
- **[CLAUDE.md](../CLAUDE.md)** - Development guidelines
- **[DSPy Docs](https://dspy-docs.vercel.app/)** - DSPy framework documentation
- **[Qdrant Docs](https://qdrant.tech/documentation/)** - Vector database documentation
- **[Modal Docs](https://modal.com/docs)** - Serverless platform documentation

---

**Questions or suggestions?** File an issue or update documentation directly (following [CLAUDE.md](../CLAUDE.md) guidelines).
