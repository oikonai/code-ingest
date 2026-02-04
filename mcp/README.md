# Code Ingest MCP Server

Semantic code search server for ingested repositories via Qdrant vector database. Provides natural language search across code collections using the Model Context Protocol (MCP).

## Overview

This MCP server enables AI assistants to search through ingested code repositories using natural language queries. It provides:

- **4 Core Tools**: Collection listing, semantic search (single and multi-collection)
- **2 Resources**: Collection information and search best practices
- **Config-Driven**: Collection names loaded from shared YAML (synchronized with ingestion pipeline)
- **Fast**: Query caching (30 minutes) and optimized embeddings via DeepInfra

## Features

### Core Tools

1. **`list_collections`** - List all available collections with metadata
2. **`get_collection_info`** - Get detailed information about a specific collection
3. **semantic_search** - Search a single collection using natural language
4. **cross_collection_search** - Search across multiple collections simultaneously

### Resources

- **`vector://collections`** - Dynamic resource listing all available collections
- **`vector://search-tips`** - Best practices for formulating search queries

### Config-Driven Collections

Collection names are defined in `config/collections.yaml` (shared with the ingestion pipeline) to ensure the MCP server searches exactly what was ingested. If the config file is not found, the server will discover collections from Qdrant automatically.

## Installation

### Prerequisites

- Python 3.11+
- Qdrant vector database (cloud or self-hosted)
- DeepInfra API key (for embeddings)

### Setup

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repo-url>
   cd code-ingest
   ```

2. **Install dependencies**:
   ```bash
   cd mcp
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   # - QDRANT_URL
   # - QDRANT_API_KEY
   # - DEEPINFRA_API_KEY
   ```

4. **Configure collections** (optional):
   
   If you want custom collection names, edit `../config/collections.yaml` (values are suffixes; prefix is applied automatically):
   ```yaml
   collection_prefix: myproject
   language_collections:
     rust: code_rust
     typescript: code_typescript
   # ...
   ```

5. **Test the server**:
   ```bash
   python server.py
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QDRANT_URL` | Yes | - | Qdrant instance URL |
| `QDRANT_API_KEY` | Yes | - | Qdrant API key |
| `DEEPINFRA_API_KEY` | Yes | - | DeepInfra API key (for embeddings) |
| `EMBEDDING_MODEL` | No | `Qwen/Qwen3-Embedding-8B-batch` | Embedding model |
| `EMBEDDING_ENDPOINT` | No | `https://api.deepinfra.com/v1/openai` | DeepInfra API base URL (optional override) |
| `COLLECTIONS_CONFIG` | No | `config/collections.yaml` | Path to collections config |

### Collections Config

The `config/collections.yaml` file defines collection names and aliases. This file is shared between the ingestion pipeline and MCP server. Set `collection_prefix` once; all other values are **suffixes** (e.g. `code_rust`, `frontend`). Full names are built as `{prefix}_{suffix}`.

```yaml
collection_prefix: myproject  # Customize for your org; leave empty for no prefix

language_collections:
  rust: code_rust
  typescript: code_typescript
  python: code_python
  # ...

service_collections:
  frontend: frontend
  backend: backend
  # ...

aliases:
  rust: code_rust
  ts: code_typescript
  # ...

default_collection: code_rust  # suffix
```

**Why share this config?** The ingestion pipeline writes to these collections; the MCP server searches them. Keeping them in sync prevents "collection not found" errors.

## Usage with Cursor IDE

### Add to Cursor Settings

Add to your Cursor MCP settings (`.cursor/settings.json` or global settings):

```json
{
  "mcpServers": {
    "code-ingest-mcp": {
      "command": "python",
      "args": ["/absolute/path/to/code-ingest/mcp/server.py"],
      "env": {
        "QDRANT_URL": "https://your-instance.qdrant.io",
        "QDRANT_API_KEY": "your_api_key",
        "DEEPINFRA_API_KEY": "your_deepinfra_api_key"
      }
    }
  }
}
```

Or use a dotenv file:

```json
{
  "mcpServers": {
    "code-ingest-mcp": {
      "command": "python",
      "args": ["/absolute/path/to/code-ingest/mcp/server.py"]
    }
  }
}
```

(Make sure `.env` is in the `mcp/` directory)

### Restart Cursor

After adding the MCP server, restart Cursor for it to load the new server.

## Example Queries

### Single Collection Search

```
Query: "Find authentication middleware that validates JWT tokens"
Collection: rust
Limit: 15
Threshold: 0.6
```

### Multi-Collection Search

```
Query: "How do we handle payment processing across the stack?"
Collections: [backend, frontend]
Limit per collection: 10
Threshold: 0.5
```

### Using Aliases

Collection aliases make queries shorter:
- `rust` → `{prefix}_code_rust` (e.g. `myproject_code_rust`)
- `ts` → `{prefix}_code_typescript`
- `backend` → `{prefix}_backend`

## Architecture

```
┌─────────────────────────────────────────────┐
│          Cursor IDE / AI Assistant          │
└─────────────────┬───────────────────────────┘
                  │ MCP Protocol
┌─────────────────▼───────────────────────────┐
│        Code Ingest MCP Server               │
│  ┌──────────────────────────────────────┐   │
│  │  4 Tools: list, get_info, search    │   │
│  │  2 Resources: collections, tips     │   │
│  └──────────────────────────────────────┘   │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐  ┌──────▼────────┐
│ Qdrant Vector  │  │   DeepInfra   │
│   Database     │  │  (embeddings) │
│ (code vectors) │  │               │
└────────────────┘  └───────────────┘
```

## Troubleshooting

### "No collections found"

**Cause:** Qdrant database is empty or not accessible.

**Solution:** Run the ingestion pipeline first to populate collections:
```bash
cd ..
make ingest
```

### "Collection not found: X"

**Cause:** Collection name in query doesn't match what's in Qdrant.

**Solution:** 
1. Check `config/collections.yaml` matches ingestion config
2. Use `list_collections` tool to see available collections
3. Use aliases from the config file

### "Embedding endpoint timeout"

**Cause:** DeepInfra API is slow or unavailable.

**Solution:**
1. Check DeepInfra API status at https://deepinfra.com/status
2. Verify `DEEPINFRA_API_KEY` is correct
3. Optionally override `EMBEDDING_ENDPOINT` if using a custom DeepInfra endpoint
4. Increase timeout in config (future feature)

### "YAML config not found"

**Cause:** `config/collections.yaml` doesn't exist or `COLLECTIONS_CONFIG` path is wrong.

**Solution:** Either create the file or let MCP discover collections from Qdrant (no config required).

## Development

### Running Locally

```bash
cd mcp
python server.py
```

### Testing Tools

Use the MCP inspector or curl to test tools:

```python
# Example: Test semantic_search
import asyncio
from server import semantic_search

result = asyncio.run(semantic_search(
    query="user authentication logic",
    collection_name="rust",
    limit=10,
    score_threshold=0.6
))
print(result)
```

## License

[Your License Here]

## Support

For issues or questions:
- GitHub Issues: [repo-url]/issues
- Documentation: `../docs/`
