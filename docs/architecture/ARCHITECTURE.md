# I2P Architecture Guide

> **Last Updated:** 2025-10-01
> **Purpose:** Comprehensive architecture navigation and decision guide
> **Audience:** Developers, architects, and contributors

## 🎯 What This Document Provides

This is the **master architecture guide** for the I2P Meta-Reasoning System. It serves as:

1. **Navigation Hub** - Quick access to all architecture documentation
2. **Decision Guide** - Architecture patterns and when to use them
3. **System Overview** - Complete understanding of how I2P works
4. **Onboarding** - Fast-track new developers to productivity

## 📚 Architecture Documentation Map

### Core Architecture Documents

| Document | Purpose | Read When... |
|----------|---------|-------------|
| **[OVERVIEW.md](./OVERVIEW.md)** | High-level system architecture, components, tech stack | Starting with I2P, understanding system design |
| **[DATA_FLOW.md](./DATA_FLOW.md)** | Complete request lifecycle and data transformations | Debugging issues, optimizing performance |
| **[DEPENDENCIES.md](./DEPENDENCIES.md)** | Module dependency graph and import structure | Adding modules, refactoring code |
| **[DSPY_SIGNATURES.md](./DSPY_SIGNATURES.md)** | All DSPy signature definitions and patterns | Writing DSPy modules, training models |
| **[VECTOR_SEARCH.md](./VECTOR_SEARCH.md)** | Vector search architecture with GEPA | Working with embeddings, search optimization |

## 🏗️ System Architecture at a Glance

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│              CLI → Pipeline → Output Formatting              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   REASONING LAYER                            │
│     Boundary Analysis → Gap Analysis → Navigation Index     │
│              (DSPy Modules + Vector Context)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                        │
│    Vector Search (GEPA) ← Qdrant DB ← Modal Embeddings     │
│             Ingestion Pipeline (Multi-Language)             │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Meta-Reasoning First** - Strategic analysis over direct code generation
2. **Vector-Enriched** - Every step enhanced with semantic code search
3. **Trained Query Generation** - GEPA learns optimal search patterns
4. **Multi-Language Support** - Rust, TypeScript, Solidity, Markdown
5. **Modular Pipeline** - Each stage is independently testable
6. **DSPy-Native** - Structured LLM interactions with optimization

## 🎭 Key Architectural Patterns

### 1. Pipeline Pattern

**Location:** `modules/core/pipeline.py`
**Purpose:** Orchestrate multi-step reasoning with context enrichment

```python
Issue → Boundary Analysis → Gap Analysis → Navigation Index → Output
         ↓                   ↓                ↓
    Vector Context      Vector Context   Vector Context
```

**When to Use:**
- Sequential processing with dependencies between steps
- Each step needs output from previous steps
- Context enrichment at each stage

**Documentation:** [OVERVIEW.md](./OVERVIEW.md#core-components), [modules/core/PIPELINE.md](../modules/core/PIPELINE.md)

### 2. Vector-First Context Retrieval

**Location:** `modules/core/vector_search.py`
**Purpose:** Semantic code search with trained query optimization

```python
Issue + Analysis → GEPA → Optimized Queries → Embeddings → Qdrant → Contexts
```

**When to Use:**
- Finding relevant code without exact string matches
- Discovering implementation patterns
- Context enrichment for LLM reasoning

**Documentation:** [VECTOR_SEARCH.md](./VECTOR_SEARCH.md)

### 3. DSPy Module Pattern

**Location:** All `modules/core/*.py` analyzers
**Purpose:** Structured LLM interactions with trainable components

```python
class CustomSignature(dspy.Signature):
    """Clear docstring explaining purpose"""
    input_field: str = dspy.InputField(desc="...")
    output_field: str = dspy.OutputField(desc="...")

class CustomModule(dspy.Module):
    def __init__(self):
        self.reasoning = dspy.ChainOfThought(CustomSignature)
    
    def forward(self, input_field):
        return self.reasoning(input_field=input_field)
```

**When to Use:**
- Any LLM interaction requiring structured outputs
- Components that benefit from few-shot optimization
- Composable reasoning chains

**Documentation:** [DSPY_SIGNATURES.md](./DSPY_SIGNATURES.md)

### 4. GEPA Training Pattern

**Location:** `modules/training/gepa_trainer.py`
**Purpose:** Train query generation with BootstrapFewShot

```python
Trainset → BootstrapFewShot → Optimized Model → trained_model.json
              ↓
     Semantic Similarity Metric
```

**When to Use:**
- Improving search query quality
- Learning domain-specific patterns
- Optimization with vector search feedback

**Documentation:** [modules/training/GEPA.md](../modules/training/GEPA.md)

### 5. Multi-Language Ingestion

**Location:** `modules/ingest/core/pipeline.py`
**Purpose:** Parse, chunk, embed, and store code from multiple languages

```python
Code Files → AST Parser → Semantic Chunks → Embeddings → Qdrant Collections
               ↓            ↓                  ↓
           tree-sitter   500 tokens        4096D vectors
```

**When to Use:**
- Adding new codebase to vector database
- Refreshing embeddings after code changes
- Supporting new programming languages

**Documentation:** [modules/ingest/PIPELINE.md](../modules/ingest/PIPELINE.md)

## 🔑 Critical Architectural Decisions

### Decision 1: Meta-Reasoning Over Direct Code Generation

**Problem:** AI agents need strategic context, not just code snippets

**Solution:** Three-stage analysis (Boundary → Gap → Navigation) provides:
- System understanding
- "Have/Need/Missing" framework
- Specific implementation guidance

**Rationale:**
- Better strategic decisions by agents
- Avoids premature implementation
- Provides architectural context

**Trade-offs:**
- Slower than direct code generation
- Requires more LLM reasoning tokens
- Higher API costs per issue

**Alternatives Considered:**
- Direct code generation (rejected: lacks strategic thinking)
- RAG only (rejected: no strategic analysis)

**Documentation:** [OVERVIEW.md - Critical Architectural Decisions](./OVERVIEW.md#critical-architectural-decisions)

### Decision 2: Per-Step Model Optimization

**Problem:** Different tasks require different model strengths

**Solution:** Optimal model per pipeline step:
- **Grok-4-fast**: Boundary analysis (fast, 2M context)
- **o4-mini**: Gap analysis (reasoning, 200K context)
- **Claude Sonnet 4.5**: Navigation (code understanding, 1M context)

**Rationale:**
- Optimize for task requirements
- Balance speed, quality, cost
- Leverage model-specific strengths

**Trade-offs:**
- Increased API complexity
- Multiple API keys required
- More configuration

**Alternatives Considered:**
- Single model for all steps (rejected: suboptimal quality)
- Always use most capable model (rejected: too expensive/slow)

**Documentation:** [DSPY_SIGNATURES.md - Model Configuration](./DSPY_SIGNATURES.md#model-configuration-per-signature)

### Decision 3: GEPA Trained Query Generation

**Problem:** Generic search queries miss codebase-specific patterns

**Solution:** Train DSPy module to generate optimized queries using:
- BootstrapFewShot optimization
- Semantic similarity metric
- Codebase context enrichment

**Rationale:**
- 2-3x better search precision
- Learns actual type/struct names
- Adapts to codebase idioms

**Trade-offs:**
- Training overhead (5-15 min)
- Requires training dataset
- Model updates needed as codebase evolves

**Alternatives Considered:**
- Hand-crafted query templates (rejected: not adaptive)
- Embeddings-only (rejected: no query optimization)
- RAG without training (rejected: lower precision)

**Documentation:** [VECTOR_SEARCH.md - GEPA-Enhanced Search](./VECTOR_SEARCH.md#2-gepa-enhanced-search)

### Decision 4: Multi-Language Separate Collections

**Problem:** Different languages have different semantics

**Solution:** Separate Qdrant collections per language:
- `arda_code_rust`
- `arda_code_typescript`
- `arda_code_solidity`
- `arda_documentation`

**Rationale:**
- Language-specific semantic search
- Better relevance ranking
- Easier collection management

**Trade-offs:**
- More storage overhead
- Multiple searches required
- Collection management complexity

**Alternatives Considered:**
- Single collection with language filter (rejected: worse relevance)
- Per-repo collections (rejected: harder to search across repos)

**Documentation:** [VECTOR_SEARCH.md - Collections](./VECTOR_SEARCH.md#collections)

### Decision 5: Validation Skipping with Vector Search

**Problem:** Strict output validation slows pipeline

**Solution:** Skip validation when vector search is enabled because:
- Semantic similarity provides implicit quality assurance
- Vector contexts ground LLM reasoning
- Faster processing without validation overhead

**Rationale:**
- Vector search adds context quality
- LLM reasoning is more grounded
- Faster pipeline execution

**Trade-offs:**
- Less explicit quality checks
- Assumes vector search quality
- Harder to debug bad outputs

**Alternatives Considered:**
- Always validate (rejected: too slow)
- Never validate (rejected: no quality assurance)

**Documentation:** [OVERVIEW.md - Validation Strategy](./OVERVIEW.md#critical-architectural-decisions)

## 🚀 Component Interaction Flows

### Complete Processing Flow

```
1. CLI Entry (i2p_cli.py)
   ↓
2. Pipeline Initialization
   - Load GEPA model (if exists)
   - Initialize vector search
   - Configure DSPy LM
   ↓
3. STEP 1: Boundary Analysis
   - Fetch vector context (15 chunks)
   - SystemBoundaryAnalyzer.forward()
   - Output: 8 fields (issue_type, complexity, etc.)
   ↓
4. STEP 2: Gap Analysis
   - Fetch docs-priority context (25 chunks)
   - StrategicGapAnalyzer.forward()
   - Output: 9 fields (current_state, target_state, etc.)
   ↓
5. STEP 3: Navigation Index
   - Fetch GEPA-optimized context (50 chunks)
   - CodeNavigationIndexGenerator.forward()
   - Output: 9 fields (implementation_areas, hints, etc.)
   ↓
6. Result Assembly
   - Aggregate step outputs
   - Add meta-reasoning summary
   - Add pipeline metadata
   ↓
7. Output Formatting
   - Format as agent/markdown/json
   - Write to file
   - Display confirmation
```

**Documentation:** [DATA_FLOW.md - Complete Request Lifecycle](./DATA_FLOW.md#request-lifecycle)

### Vector Search Flow (GEPA)

```
1. Issue + Boundary Analysis
   ↓
2. GEPA Query Generation
   - Load trained_model.json
   - ChainOfThought reasoning
   - Output: 3-7 optimized queries
   ↓
3. For Each Query:
   a. Generate embedding (Modal TEI)
      - Qwen3-Embedding-8B (4096D)
      - Timeout: 120s (cold start)
      - Retry: 5x with backoff
   
   b. Search Qdrant collections
      - rust, typescript, solidity
      - Score threshold: 0.3
      - Limit: 25 per query
   
   c. Collect results
   ↓
4. Deduplication
   - Remove duplicates by chunk_hash
   - Keep highest score
   ↓
5. Ranking & Return
   - Sort by score descending
   - Return top N unique contexts
```

**Documentation:** [VECTOR_SEARCH.md - Search Strategies](./VECTOR_SEARCH.md#search-strategies)

### Training Flow (GEPA)

```
1. Dataset Preparation
   - Load training examples (93 total)
   - Split: 74 train / 9 val / 10 test
   - Enrich with vector context
   ↓
2. Model Configuration
   - Configure DSPy LM (Claude/GPT/Grok)
   - Set temperature: 0.1-0.3
   ↓
3. BootstrapFewShot Optimization
   - Generate few-shot examples
   - Metric: Semantic similarity (cosine)
   - Max bootstrapped demos: 8-40
   ↓
4. Evaluation
   - Test on validation set
   - Calculate accuracy & similarity
   ↓
5. Model Persistence
   - Save to trained_model.json
   - Include DSPy program state
```

**Documentation:** [modules/training/GEPA.md](../modules/training/GEPA.md)

## 📊 System Characteristics

### Performance Profile

| Component | Typical Time | Factors |
|-----------|-------------|---------|
| **CLI Initialization** | <100ms | Env loading, arg parsing |
| **Pipeline Setup** | 200-500ms | Component init, GEPA load |
| **Boundary Analysis** | 2-10s | LLM call, vector search |
| **Gap Analysis** | 5-30s | Extended reasoning (o4) |
| **Navigation Index** | 3-15s | Code understanding (Claude) |
| **Vector Search (GEPA)** | 500ms-2s | 3-7 queries, deduplication |
| **Embedding Generation** | 50-100ms | Per query (warm) |
| **GEPA Training** | 5-15 min | 93 examples, optimization |
| **Complete Pipeline** | **10-45s** | Varies by model, complexity |

**Documentation:** [OVERVIEW.md - Performance Characteristics](./OVERVIEW.md#performance-characteristics)

### Scale Characteristics

| Metric | Current | Scalability Notes |
|--------|---------|------------------|
| **Vector Collections** | 50K+ chunks | Unlimited (Qdrant Cloud) |
| **Concurrent Pipelines** | 1 | Sequential processing |
| **Embedding Throughput** | 180/sec | 4 Modal containers × 45/sec |
| **Training Dataset** | 93 examples | Expandable with dataset generator |
| **Supported Languages** | 4 | Extensible with new parsers |
| **Qdrant Collections** | 4 | Add per language/repo |

**Documentation:** [OVERVIEW.md - Scalability](./OVERVIEW.md#scalability)

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Vector Search Precision** | >0.7 | GEPA vs baseline |
| **Pipeline Success Rate** | >95% | Issues processed without errors |
| **GEPA Training Accuracy** | >0.8 | Semantic similarity score |
| **Context Relevance** | >0.3 | Score threshold for results |
| **Code Coverage** | 50K+ | Chunks across all languages |

## 🔧 Extension Points

### Adding New Reasoning Steps

**Pattern:** Extend pipeline with new DSPy module

```python
# 1. Define signature
class MyCustomAnalysis(dspy.Signature):
    """Description"""
    input_field: str = dspy.InputField(desc="...")
    output_field: str = dspy.OutputField(desc="...")

# 2. Create module
class MyCustomAnalyzer(dspy.Module):
    def __init__(self, vector_search_manager=None):
        self.reasoning = dspy.ChainOfThought(MyCustomAnalysis)
        self.vector_search = vector_search_manager
    
    def forward(self, input_field):
        # Fetch vector context
        contexts = self.vector_search.search_for_context(input_field)
        
        # Run reasoning
        return self.reasoning(
            input_field=input_field,
            context=contexts
        )

# 3. Integrate into pipeline
class I2PModularPipeline:
    def __init__(self):
        # ...
        self.custom_analyzer = MyCustomAnalyzer(self.vector_search)
    
    def process(self, issue):
        # ...
        custom_result = self.custom_analyzer(issue)
        # ...
```

**Documentation Required:**
- Update `docs/architecture/DSPY_SIGNATURES.md` with new signature
- Create `docs/modules/core/MY_ANALYZER.md` module doc
- Update `docs/architecture/DATA_FLOW.md` with new step
- Update `docs/architecture/DEPENDENCIES.md` with imports

### Adding New Programming Languages

**Pattern:** Implement language parser + ingestion

```python
# 1. Create parser (modules/ingest/parsers/mylang_parser.py)
class MyLangASTParser:
    def __init__(self):
        self.parser = tree_sitter.Parser()
        self.parser.set_language(tree_sitter_mylang.language())
    
    def extract_chunks(self, source_code: str) -> List[Dict]:
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        # Extract semantic chunks
        return chunks

# 2. Register in FileProcessor
PARSERS = {
    'rust': RustASTParser,
    'typescript': TypeScriptASTParser,
    'solidity': SolidityASTParser,
    'mylang': MyLangASTParser  # Add here
}

# 3. Create Qdrant collection
collection_name = f"arda_code_mylang"

# 4. Add to VectorSearchManager collections list
```

**Documentation Required:**
- Create `docs/modules/ingest/parsers/MYLANG.md`
- Update `docs/modules/ingest/PARSERS.md` with new language
- Update `docs/architecture/OVERVIEW.md` supported languages
- Update README.md with new language support

### Training New GEPA Models

**Pattern:** Dataset generation + optimization + evaluation

```python
# 1. Generate dataset (optional)
make generate-dataset NUM_EXAMPLES=100 OUTPUT=custom_dataset.json

# 2. Prepare dataset
dataset_manager = DatasetManager()
dataset_manager.load_from_file('custom_dataset.json')
trainset, valset, testset = dataset_manager.get_splits()

# 3. Configure optimizer
optimizer = dspy.BootstrapFewShot(
    metric=gepa_metric,
    max_bootstrapped_demos=40,
    max_labeled_demos=8
)

# 4. Train
trained_model = optimizer.compile(
    student=GEPAModule(),
    trainset=trainset
)

# 5. Evaluate
for example in testset:
    prediction = trained_model(**example.inputs())
    score = gepa_metric(example, prediction)

# 6. Save
trained_model.save('trained_model.json')
```

**Documentation Required:**
- Update `docs/modules/training/GEPA.md` with new dataset
- Document any metric changes in `docs/modules/training/GEPA.md`
- Update training guide `docs/guides/TRAINING.md`

## 🐛 Debugging Architecture

### Common Issues & Resolution

| Issue | Likely Cause | Check | Resolution |
|-------|-------------|-------|------------|
| **Empty vector contexts** | GEPA/search failure | `make vector-status` | Verify Qdrant connectivity, check GEPA model |
| **Slow pipeline** | Wrong model config | Review model selection | Use optimal models flag |
| **Low search relevance** | Score threshold too high | Check vector search logs | Lower threshold to 0.3 |
| **Training fails** | Insufficient examples | Check dataset size | Need 20+ training examples |
| **LLM API errors** | Rate limiting | Check OpenRouter logs | Reduce concurrency |
| **Cold start timeout** | Modal embedding service | Check Modal health | Increase timeout to 120s |

### Architecture-Level Debugging

**Step 1: Component Health**
```bash
make health           # Pipeline + vector search
make vector-status    # Qdrant collections
make modal-health     # Embedding service
```

**Step 2: Flow Tracing**
```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Trace data flow
pipeline = I2PModularPipeline(enable_vectorization=True)
result = pipeline.process(issue)  # Check logs for each step
```

**Step 3: Component Isolation**
```python
# Test individual components
vector_search = VectorSearchManager()
contexts = vector_search.search_for_context("test query", limit=5)
print(f"Found {len(contexts)} contexts")

# Test boundary analyzer
boundary = SystemBoundaryAnalyzer(vector_search)
result = boundary(issue="test issue")
print(result)
```

**Documentation:** [DATA_FLOW.md - Error Handling](./DATA_FLOW.md#error-handling-in-data-flow)

## 📖 Learning Path

### For New Developers

**Week 1: System Understanding**
1. Read [OVERVIEW.md](./OVERVIEW.md) - High-level architecture
2. Read [DATA_FLOW.md](./DATA_FLOW.md) - Request lifecycle
3. Run `make demo` - See system in action
4. Read [DSPY_SIGNATURES.md](./DSPY_SIGNATURES.md) - Understanding signatures

**Week 2: Deep Dive**
1. Read [modules/core/PIPELINE.md](../modules/core/PIPELINE.md) - Pipeline internals
2. Read [VECTOR_SEARCH.md](./VECTOR_SEARCH.md) - Search architecture
3. Read [modules/training/GEPA.md](../modules/training/GEPA.md) - Training system
4. Read [DEPENDENCIES.md](./DEPENDENCIES.md) - Module structure

**Week 3: Hands-On**
1. Follow [guides/TRAINING.md](../guides/TRAINING.md) - Train GEPA model
2. Modify a DSPy signature - Learn optimization
3. Add vector search to a new component
4. Write a new analyzer module

### For Contributors

**Before Contributing:**
1. Read [CLAUDE.md](../../CLAUDE.md) - Development guidelines
2. Review [ARCHITECTURE.md](./ARCHITECTURE.md) (this doc) - Understand patterns
3. Check [DEPENDENCIES.md](./DEPENDENCIES.md) - Understand module structure
4. Read relevant module docs in `docs/modules/`

**When Adding Features:**
1. Follow architectural patterns documented here
2. Update architecture docs if design changes
3. Add module documentation following templates
4. Test thoroughly with `make health` and `make test`

## 🔗 Related Resources

### Internal Documentation
- [CLAUDE.md](../../CLAUDE.md) - Development guidelines
- [README.md](../../README.md) - User-facing documentation
- [docs/README.md](../README.md) - Documentation index
- [modules/](../modules/) - Module-specific documentation
- [guides/](../guides/) - User guides

### External Resources
- [DSPy Documentation](https://dspy-docs.vercel.app/) - DSPy framework
- [Qdrant Documentation](https://qdrant.tech/documentation/) - Vector database
- [Modal Documentation](https://modal.com/docs) - Serverless platform
- [OpenRouter Documentation](https://openrouter.ai/docs) - LLM gateway

---

**This is a living document.** Update this architecture guide when:
- Adding new architectural patterns
- Making major design decisions
- Changing system flows
- Adding new components
- Discovering common issues

**Last Updated:** 2025-10-01
**Maintainer:** Auto-synced with codebase changes
