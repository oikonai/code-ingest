# Code Ingest MCP Server - Technical Documentation

**Version:** 2.0.0 (Minimal MCP implementation)
**Purpose:** Semantic code search via MCP for ingested repositories

## Overview

Code Ingest MCP Server - A minimal FastMCP server providing semantic code search over ingested repositories via Qdrant vector database. Designed for AI assistants to search code using natural language queries.

## Architecture

**Minimal Design Principles:**
- **4 Core Tools**: Collection management + semantic search (single and multi-collection)
- **2 Generic Resources**: Collection info + search tips
- **Config-Driven**: Collection names from shared YAML (synchronized with ingestion)
- **No Domain Logic**: No ARDA-specific or project-specific prompts/resources

## Environment Setup

### Required Variables

```bash
# Qdrant Vector Database
QDRANT_URL=https://xxxxx.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_jwt_token

# Cloudflare AI Gateway + DeepInfra
EMBEDDING_ENDPOINT=https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}
CLOUDFLARE_API_TOKEN=your_cloudflare_token
DEEPINFRA_API_KEY=your_deepinfra_key
EMBEDDING_MODEL=custom-deepinfra/Qwen/Qwen2.5-7B-Instruct-Embedding  # Optional
```

### Optional Variables

```bash
# Path to shared collections config (default: config/collections.yaml)
COLLECTIONS_CONFIG=config/collections.yaml

# GitHub token (for future features, not currently used)
GHCR_TOKEN=your_github_token
```

## Collections Configuration

**File:** `config/collections.yaml` (shared with ingestion pipeline)

**Purpose:** Single source of truth for collection names. Ingestion writes to these collections; MCP searches them.

**Structure:**

```yaml
collection_prefix: myproject  # Optional

language_collections:
  rust: myproject_code_rust
  typescript: myproject_code_typescript
  python: myproject_code_python
  # ...

service_collections:
  frontend: myproject_frontend
  backend: myproject_backend
  middleware: myproject_middleware
  # ...

concern_collections:
  api_contracts: myproject_api_contracts
  database_schemas: myproject_database_schemas
  config: myproject_config
  deployment: myproject_deployment

aliases:
  rust: myproject_code_rust
  ts: myproject_code_typescript
  backend: myproject_backend
  # ...

default_collection: myproject_code_rust
```

**Loading Logic:**
1. Check `COLLECTIONS_CONFIG` env var for path
2. If not set, use `config/collections.yaml` (relative to workspace root)
3. If file doesn't exist, discover collections from Qdrant (no schema, no aliases)

## Core Components

### 1. Collections Module (`src/collections.py`)

**Purpose:** Config-driven collection schema and aliases.

**Key Functions:**
- `resolve_collection_name(alias)` - Map alias to full name (e.g., "rust" → "myproject_code_rust")
- `get_collections_by_type(type)` - Get all language/service/concern collections
- `add_discovered_collection(name)` - Add Qdrant-discovered collections to schema

**Global Variables:**
- `COLLECTION_SCHEMA` - Dict of collection_name → {type, description}
- `COLLECTION_ALIASES` - Dict of alias → collection_name
- `DEFAULT_COLLECTION` - Default collection for search tools

### 2. Config Module (`src/config.py`)

**Purpose:** Load shared collections config from YAML.

**Key Functions:**
- `load_collections_config()` - Load YAML and return language/service/concern/aliases
- `build_collection_schema(config)` - Generate COLLECTION_SCHEMA from config
- `get_default_collection(config)` - Determine default collection for tools

### 3. Resources (`src/resources/resources.py`)

**2 Generic Resources:**

#### `vector://collections`
- Lists all available collections from Qdrant + schema
- Grouped by type (language, service, concern, unknown)
- Shows point counts and status

#### `vector://search-tips`
- Best practices for semantic search
- Query formulation tips
- Parameter tuning guidance (limit, score_threshold)
- No project-specific content

### 4. Tools

**Collection Tools** (`src/tools/collection.py`):
- `list_collections()` - List all collections with metadata
- `get_collection_info(collection_name)` - Detailed info for one collection

**Search Tools** (`src/tools/search.py`):
- `semantic_search(query, collection_name, limit, score_threshold)` - Single-collection search
- `cross_collection_search(query, collections, limit_per_collection, score_threshold)` - Multi-collection search

**Default Collection:**
- If `collection_name` is `None`, uses `DEFAULT_COLLECTION` from config
- Resolves aliases via `resolve_collection_name()` (e.g., "rust" → "myproject_code_rust")

### 5. Query Router (`src/query_router.py`)

**Purpose:** Infer collection from query keywords (optional helper).

**Logic:**
- Pattern match on keywords (frontend, backend, database, etc.)
- Return collection from config (e.g., service_collections['frontend'])
- Fallback to default_collection if no match

**Note:** Not required for core tools; just a helper for intelligent routing.

## MCP Integration

### Server Configuration

```json
{
  "mcpServers": {
    "code-ingest-mcp": {
      "command": "python",
      "args": ["/absolute/path/to/code-ingest/mcp/server.py"],
      "env": {
        "QDRANT_URL": "...",
        "QDRANT_API_KEY": "...",
        "EMBEDDING_ENDPOINT": "...",
        "CLOUDFLARE_API_TOKEN": "...",
        "DEEPINFRA_API_KEY": "..."
      }
    }
  }
}
```

### Tool Usage

**List collections:**
```python
list_collections()
# Returns: {"collections_by_type": {...}, "count": N, "server": "code-ingest-mcp"}
```

**Get collection info:**
```python
get_collection_info("rust")  # Uses alias resolution
# Returns: {"name": "myproject_code_rust", "points_count": 12345, ...}
```

**Semantic search:**
```python
semantic_search(
    query="JWT authentication middleware",
    collection_name="rust",  # or alias like "backend"
    limit=15,
    score_threshold=0.6
)
# Returns: {"results": [...], "count": N, "query": "...", "collection": "...", ...}
```

**Cross-collection search:**
```python
cross_collection_search(
    query="payment processing logic",
    collections=["backend", "frontend"],  # Aliases work
    limit_per_collection=10,
    score_threshold=0.5
)
# Returns: {"results_by_collection": {"backend": [...], "frontend": [...]}, ...}
```

## Removed Features (from v1.x)

**Removed for minimal implementation:**
- ❌ Prompts (12 ARDA-specific prompts)
- ❌ Domain tools (get_auth_systems, get_stack_overview, get_deployed_services)
- ❌ Metadata tools (list_resources, list_prompts, get_prompt)
- ❌ Code quality tools (code_quality_check, detect_code_smells, etc.)
- ❌ Analytics tools (get_prompt_usage_stats, etc.)
- ❌ GitHub integration (get_cached_repo_structures)
- ❌ 8 ARDA-specific resources (dashboard, api-catalog, patterns, stats, dependencies, changelog, metrics, architecture)

**What remains:**
- ✅ 4 core tools (collection + search)
- ✅ 2 generic resources (collections + search-tips)
- ✅ Config-driven collections (no hardcoded ARDA names)
- ✅ Query caching (30 minutes)

## Performance

### Query Caching
- **TTL:** 30 minutes per query
- **Key:** `query + collection_name + params (limit, threshold)`
- **Storage:** In-memory LRU cache (max 1000 entries)

### Embedding Generation
- **Service:** Cloudflare AI Gateway → DeepInfra
- **Model:** Qwen2.5-7B-Instruct-Embedding (4096 dimensions)
- **Warmup:** Pre-warm endpoint on server startup (30s timeout)

### Search Performance
- **Collection Selection:** Specific collection (e.g., "rust") faster than cross-collection
- **Limit:** Lower limit = faster (10-20 recommended)
- **Threshold:** Higher threshold = fewer results = faster

## Development

### Adding New Collections

1. Update `config/collections.yaml`:
   ```yaml
   language_collections:
     go: myproject_code_go  # New language
   ```

2. Ingest code to that collection (ingestion pipeline will use same config)

3. MCP server auto-loads new collection on next startup (no code changes)

### Adding Prompts (Future)

To add project-specific prompts:
1. Add prompt functions to `src/prompts/prompts.py`
2. Register with `@mcp.prompt()` decorator
3. Update `register_prompts()` to include new prompts

### Adding Domain Tools (Future)

To add project-specific domain tools:
1. Create new module in `src/tools/`
2. Define tools with `@mcp.tool()` decorator
3. Register in `server.py` lifespan

## Troubleshooting

### Collections Not Loading

**Symptom:** MCP finds 0 collections

**Cause:** Qdrant is empty or `QDRANT_URL` is wrong

**Fix:** Run ingestion pipeline first (`make ingest` in repo root)

### Collection Name Mismatch

**Symptom:** "Collection not found: X"

**Cause:** `config/collections.yaml` doesn't match ingestion config

**Fix:** Ensure both ingestion and MCP use same `COLLECTIONS_CONFIG` path

### Alias Not Resolving

**Symptom:** Alias like "rust" doesn't work

**Cause:** Alias not in `config/collections.yaml`

**Fix:** Add alias to config file under `aliases:` section

## File Structure

```
mcp/
├── server.py              # FastMCP server entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── README.md             # User documentation
├── CLAUDE.md             # Technical documentation (this file)
└── src/
    ├── __init__.py
    ├── config.py         # Collections config loader
    ├── collections.py    # Config-driven schema and aliases
    ├── cache.py          # Query cache implementation
    ├── query_router.py   # Optional keyword-based routing
    ├── response_formatter.py  # Result formatting
    ├── prompts/
    │   └── prompts.py    # Empty (no prompts in minimal server)
    ├── resources/
    │   └── resources.py  # 2 generic resources
    ├── tools/
    │   ├── collection.py # Collection management tools
    │   └── search.py     # Semantic search tools
    ├── tracking/
    │   └── prompt_tracker.py  # Analytics (unused)
    └── utils/
        ├── code_analysis.py   # Code helpers
        └── github.py          # GitHub helpers (unused)
```

## Summary

**Minimal MCP Server = 4 tools + 2 resources + config-driven collections.**

No ARDA-specific logic. No prompts. No domain tools. Just semantic search over ingested code, with collection names shared via `config/collections.yaml` to keep ingestion and search in sync.

**To customize:** Edit `config/collections.yaml` and re-run both ingestion and MCP server. No code changes needed.
