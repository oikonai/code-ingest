# I2P Documentation Maintenance Guide

> **For Developers:** How to maintain documentation in sync with code changes
> **Last Updated:** 2025-10-01

## Overview

The I2P system requires **comprehensive technical documentation** that stays synchronized with code changes. This guide explains the documentation structure, maintenance workflow, and standards.

## Documentation Philosophy

### Core Principles

1. **Code and Docs are Inseparable** - Every code change is a documentation change
2. **Outdated Docs are Worse Than No Docs** - Incorrect documentation misleads developers
3. **Documentation is Tested** - Examples must execute without errors
4. **Architecture is Explicit** - Design decisions are documented with rationale

### What Gets Documented

**ALWAYS document:**
- ✅ System architecture and component interactions
- ✅ Module dependencies and import paths
- ✅ DSPy signatures (inputs, outputs, reasoning)
- ✅ Data flows and transformations
- ✅ External service integrations
- ✅ Error handling strategies
- ✅ Performance characteristics
- ✅ Configuration requirements

**OPTIONAL:**
- ⚠️ Internal implementation details (only if complex)
- ⚠️ Temporary workarounds (flag as temporary)

## Documentation Structure

```
docs/
├── README.md                   # Documentation index and navigation
├── DOCUMENTATION_GUIDE.md      # This file (maintenance guide)
│
├── architecture/               # System-level documentation
│   ├── OVERVIEW.md             # High-level architecture, tech stack
│   ├── DEPENDENCIES.md         # Module dependency graph
│   ├── DATA_FLOW.md            # Request lifecycle, transformations
│   ├── DSPY_SIGNATURES.md      # All DSPy signatures reference
│   └── VECTOR_SEARCH.md        # Vector search architecture
│
├── modules/                    # Per-module technical docs
│   ├── core/
│   │   ├── PIPELINE.md         # I2PModularPipeline
│   │   ├── CLASSIFIER.md       # SystemBoundaryAnalyzer
│   │   ├── ANALYZER.md         # StrategicGapAnalyzer
│   │   ├── GENERATOR.md        # CodeNavigationIndexGenerator
│   │   ├── VECTOR_SEARCH.md    # VectorSearchManager
│   │   └── VALIDATION.md       # ValidatorManager
│   │
│   ├── training/
│   │   ├── GEPA.md             # GEPA module and training
│   │   ├── DATASETS.md         # Dataset formats
│   │   └── METRICS.md          # Training metrics
│   │
│   └── ingest/
│       ├── PIPELINE.md         # IngestionPipeline
│       ├── PARSERS.md          # Language parsers
│       ├── EMBEDDING.md        # Modal TEI service
│       └── VECTOR_CLIENT.md    # Qdrant client
│
├── api/                        # API reference
│   └── README.md               # Public API documentation
│
└── guides/                     # User guides
    ├── TRAINING.md             # Training GEPA models
    ├── INGESTION.md            # Ingesting codebases
    └── DEPLOYMENT.md           # Deployment guide
```

## Maintenance Workflow

### When You Change Code

**Step 1: Identify Documentation Impact**

Ask yourself:
- Does this change affect system architecture? → Update `docs/architecture/`
- Does this add/modify a module? → Update `docs/modules/{category}/`
- Does this change data flow? → Update `docs/architecture/DATA_FLOW.md`
- Does this add/remove dependencies? → Update `docs/architecture/DEPENDENCIES.md`
- Does this change DSPy signatures? → Update `docs/architecture/DSPY_SIGNATURES.md`
- Does this affect training? → Update `docs/modules/training/`

**Step 2: Update Documentation**

Use the appropriate template (see below) and update:
- "Last Updated" date
- Code examples
- Method signatures
- Performance characteristics
- Related documentation links

**Step 3: Verify Changes**

Before committing:
- ✅ Run code examples from documentation
- ✅ Check all internal links work
- ✅ Verify diagrams reflect current architecture
- ✅ Run `make health` to ensure system integrity

**Step 4: Commit Together**

Commit code changes and documentation updates **in the same commit**:

```bash
git add modules/core/pipeline.py docs/modules/core/PIPELINE.md
git commit -m "feat(pipeline): add GEPA integration

- Add GEPAQueryGenerator to VectorSearchManager
- Update pipeline to use optimized queries
- Document GEPA integration in PIPELINE.md

Closes #123"
```

## Documentation Templates

### Module Documentation Template

```markdown
# Module Name

> **File:** `modules/category/filename.py`
> **Class:** `ClassName`
> **Last Updated:** YYYY-MM-DD

## Overview

Brief description of module purpose and context within the system.

## Class Signature

\`\`\`python
class ClassName:
    def __init__(
        self,
        param1: Type,
        param2: Type = default
    ):
        """
        Initialize the class.

        Args:
            param1: Description of param1
            param2: Description of param2 (default: default)
        """
\`\`\`

## Methods

### `method_name(param1: Type, param2: Type) -> ReturnType`

Description of what the method does.

**Parameters:**
- `param1` (Type): Description
- `param2` (Type): Description

**Returns:**
- `ReturnType`: Description of return value

**Raises:**
- `ExceptionType`: When this exception occurs

**Example:**
\`\`\`python
obj = ClassName(param1=value1)
result = obj.method_name(param1, param2)
print(result)
\`\`\`

## Usage Examples

### Basic Usage

\`\`\`python
# Example demonstrating typical usage
from modules.category.filename import ClassName

instance = ClassName(param1=value)
result = instance.method()
\`\`\`

### Advanced Usage

\`\`\`python
# Example demonstrating advanced scenarios
\`\`\`

## Error Handling

Common errors and how to handle them:

\`\`\`python
try:
    result = instance.method()
except SpecificError as e:
    # Handle error
    logging.error(f"Failed: {e}")
\`\`\`

## Performance Characteristics

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| method1() | ~100ms | Depends on X |
| method2() | ~5s | LLM call |

## Configuration

Environment variables or configuration required:

\`\`\`bash
REQUIRED_VAR=value
OPTIONAL_VAR=value
\`\`\`

## Related Documentation

- [Related Module 1](./RELATED1.md)
- [Related Module 2](./RELATED2.md)
- [Architecture Overview](../../architecture/OVERVIEW.md)

---

**Note:** This documentation is auto-synced with code changes. Update when modifying `modules/category/filename.py`.
```

### Architecture Documentation Template

```markdown
# Architecture Component

> **Last Updated:** YYYY-MM-DD
> **Scope:** System-level architecture

## Overview

High-level description of this architectural component.

## Architecture Diagram

\`\`\`
[ASCII diagram or reference to image]
\`\`\`

## Components

### Component 1

**Purpose:** Description
**Implementation:** `module/path.py`
**Dependencies:** Other components

### Component 2

...

## Data Flow

\`\`\`
Step 1 → Step 2 → Step 3
\`\`\`

Detailed description of data transformations at each step.

## Design Decisions

### Decision: [Decision Title]

**Problem:** What problem did this solve?
**Solution:** What approach was chosen?
**Rationale:** Why this approach?
**Trade-offs:** What are the pros/cons?
**Alternatives Considered:** What other options were evaluated?

## Performance Characteristics

Typical performance metrics for this component.

## Related Documentation

Links to related architecture and module docs.
```

## Synchronization Triggers

### Trigger Matrix

| Code Change Type | Documentation to Update |
|------------------|------------------------|
| **New module added** | Create `docs/modules/{category}/{MODULE}.md`, update `docs/architecture/DEPENDENCIES.md`, update `docs/README.md` |
| **Module deleted** | Remove module doc, update dependency graph, update README |
| **Method signature changed** | Update module doc, update examples |
| **DSPy signature changed** | Update `DSPY_SIGNATURES.md`, update module doc |
| **New dependency added** | Update `DEPENDENCIES.md`, update module doc |
| **Data flow changed** | Update `DATA_FLOW.md`, update module doc |
| **External service added** | Update `OVERVIEW.md`, create/update service doc |
| **Architecture decision** | Update `OVERVIEW.md`, document decision rationale |
| **Performance change** | Update performance sections in relevant docs |
| **Training process changed** | Update training docs, update GEPA doc |
| **Error handling changed** | Update error handling sections |

## Quality Standards

### Documentation Quality Checklist

**Before marking documentation complete:**

- [ ] **Accuracy**: All code examples execute without errors
- [ ] **Completeness**: All public methods documented
- [ ] **Clarity**: Technical terms defined, acronyms explained
- [ ] **Currency**: "Last Updated" date is current
- [ ] **Consistency**: Follows template structure
- [ ] **Connectivity**: All internal links work
- [ ] **Context**: Related documentation linked
- [ ] **Compliance**: Follows CLAUDE.md standards

### Common Documentation Issues

**❌ Don't:**
- Document private/internal methods (use code comments)
- Include outdated examples
- Use vague descriptions ("handles stuff", "processes data")
- Forget to update "Last Updated" date
- Break internal links
- Copy-paste without customizing to context

**✅ Do:**
- Focus on public API and integration points
- Test all code examples
- Use specific, descriptive language
- Update date on every change
- Verify all links
- Customize documentation for each module

## Review Process

### Code Review Documentation Checks

**Reviewer checklist:**

1. **Documentation Updated?**
   - [ ] Relevant docs modified in same commit
   - [ ] New modules have documentation
   - [ ] Deleted code has docs removed

2. **Accuracy**
   - [ ] Code examples match actual implementation
   - [ ] Method signatures are correct
   - [ ] Error handling documented

3. **Completeness**
   - [ ] All new public methods documented
   - [ ] Breaking changes highlighted
   - [ ] Migration guide provided (if needed)

4. **Quality**
   - [ ] Follows template structure
   - [ ] Links work
   - [ ] Performance notes updated
   - [ ] Examples tested

### Documentation-Only Changes

Small documentation fixes (typos, clarifications) can be committed separately:

```bash
git commit -m "docs(pipeline): clarify vector search integration

Fix typo in usage example and clarify GEPA query generation flow."
```

## Automated Tooling

### Future Enhancements

Planned automation to enforce documentation sync:

1. **Pre-commit Hook** - Verify documentation modified when code changes
2. **CI Documentation Build** - Test all code examples execute
3. **Link Checker** - Verify all internal/external links
4. **Coverage Report** - Track documentation coverage by module
5. **Staleness Detector** - Flag docs older than code

### Current Manual Process

For now, documentation sync relies on:
- Developer discipline (following CLAUDE.md)
- Code review verification
- This maintenance guide

## Troubleshooting

### "I don't know what to document"

**Start with:**
1. Read the module code
2. Identify public API (class, methods, exceptions)
3. Write usage examples
4. Document error handling
5. Add performance notes

**Reference existing docs** for structure inspiration.

### "My documentation is getting too long"

**Split by concern:**
- Keep overview concise (1-2 paragraphs)
- Move detailed examples to separate section
- Link to related docs instead of repeating
- Consider splitting large modules into smaller ones (CLAUDE.md guideline)

### "Code changed but docs are unclear how"

**Update strategy:**
1. Read the diff to understand what changed
2. Find corresponding documentation sections
3. Update signatures, examples, and notes
4. Test updated examples
5. Update "Last Updated" date

## Resources

- **[CLAUDE.md](../CLAUDE.md)** - Development guidelines (includes doc sync requirements)
- **[docs/README.md](./README.md)** - Documentation index
- **[docs/architecture/](./architecture/)** - Architecture documentation
- **[docs/modules/](./modules/)** - Module documentation

---

**Questions?** Refer to [CLAUDE.md - Documentation Sync](../CLAUDE.md#documentation-sync-requirements) or open an issue.
