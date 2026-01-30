# Arda Vector Database MCP Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0+-green.svg)](https://github.com/gofastmcp/fastmcp)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.7+-purple.svg)](https://qdrant.tech/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Semantic Code Search MCP Server** - A FastMCP server providing semantic code search capabilities through Qdrant vector database integration. Designed for Cursor IDE and other MCP-compatible AI coding assistants.

## 🎯 What is Arda Vector Database?

Arda Vector Database is an MCP (Model Context Protocol) server that provides read-only semantic search across the **Arda Credit platform** codebase (Rust backend, TypeScript frontend, and Solidity smart contracts) using natural language queries.

### Key Features

- **⭐ Smart Search** - NEW: Intelligent query routing to best tool
- **⭐ Specialized Tools** - NEW: 5 tools for common patterns (auth, stack, services, location, dependencies)
- **⚡ Caching** - NEW: 30-minute cache, < 500ms responses
- **🔍 Semantic Code Search** - Natural language queries across multiple programming languages
- **🎯 Domain-Specific Prompts** - Pre-built search templates for Arda Credit features
- **📚 MCP Resources** - Static documentation and search best practices
- **🔄 Batch Search** - Query multiple aspects efficiently (up to 100 results)
- **🌐 Cross-Collection Search** - Full-stack exploration (backend, frontend, contracts)
- **🗄️ Multi-Language Support** - Rust, TypeScript, Solidity, Python, YAML, Terraform
- **📊 Collection Management** - Health monitoring and statistics for vector collections
- **🚀 High Performance** - Embeddings via Cloudflare AI gateway (4096-dimensional vectors)
- **🔒 Read-Only Operations** - Safe integration without ingestion capabilities

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Qdrant Cloud](https://cloud.qdrant.io/) account or local Qdrant instance
- Embedding endpoint (Cloudflare AI gateway)
- Cursor IDE or MCP-compatible coding assistant

### Installation

```bash
# Clone the repository
git clone https://github.com/ardaglobal/arda-mcp.git
cd arda-mcp

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials:
# QDRANT_URL=https://xxxxx.gcp.cloud.qdrant.io
# QDRANT_API_KEY=your_qdrant_api_key
# EMBEDDING_ENDPOINT=https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat
# CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
# DEEPINFRA_API_KEY=your_deepinfra_api_key
```

### Running the Server

```bash
# Start the MCP server
python server.py

# Or with explicit environment
QDRANT_URL=https://your-qdrant.io QDRANT_API_KEY=your-key CLOUDFLARE_API_TOKEN=your-token python server.py
```

### MCP Integration

#### Cursor IDE Configuration

Add to your MCP settings (typically `~/.cursor/mcp.json` or project-specific `.mcp.json`):

```json
{
  "mcpServers": {
    "arda-vector-db": {
      "command": "python",
      "args": ["/path/to/arda-mcp/server.py"],
      "env": {
        "QDRANT_URL": "https://xxxxx.gcp.cloud.qdrant.io",
        "QDRANT_API_KEY": "your_qdrant_api_key",
        "EMBEDDING_ENDPOINT": "https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat",
        "CLOUDFLARE_API_TOKEN": "your_cloudflare_api_token",
        "DEEPINFRA_API_KEY": "your_deepinfra_api_key"
      }
    }
  }
}
```

#### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "arda-vector-db": {
      "command": "python",
      "args": ["/path/to/arda-mcp/server.py"],
      "env": {
        "QDRANT_URL": "https://xxxxx.gcp.cloud.qdrant.io",
        "QDRANT_API_KEY": "your_qdrant_api_key",
        "EMBEDDING_ENDPOINT": "https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat",
        "CLOUDFLARE_API_TOKEN": "your_cloudflare_api_token",
        "DEEPINFRA_API_KEY": "your_deepinfra_api_key"
      }
    }
  }
}
```

## 📖 Available MCP Features

### MCP Tools (19 Total - Expanded in v1.2.0)

### Core Search Tools

#### `smart_search` ⭐ NEW in v1.2.0

Intelligent search that automatically routes queries to the best specialized tool.

```python
# Arguments:
# - query: str (required) - Natural language query
# - context: dict (optional) - Additional context

# Example:
# query="What are the authentication systems?"

# Returns: Routing information + formatted result
{
  "routing": {
    "tool": "get_auth_systems",
    "params": {},
    "explanation": "Query is asking about authentication systems"
  },
  "result": { /* Formatted auth systems data */ }
}
```

**This is the recommended tool for general queries!** The smart search automatically:
- Detects query intent
- Routes to the appropriate specialized tool
- Formats results for IDE consumption
- Provides quick actions and related queries

#### `health_check`

Check Qdrant connection health and return system status.

```python
# Returns:
{
  "status": "healthy",
  "connected": True,
  "collections_count": 10,
  "collections": ["arda_code_rust", "arda_code_typescript", "arda_frontend", "arda_backend", ...],
  "server_version": "1.2.0"
}
```

#### `refresh_repo_cache` (New in v1.1.0)

Manually refresh GitHub repository structure cache to get latest updates immediately.

```python
# No arguments required

# Returns:
{
  "status": "success",
  "message": "Repository cache refreshed successfully",
  "cache_ttl_seconds": 3600,
  "repositories": [
    {
      "name": "arda-credit",
      "owner": "ardaglobal",
      "updated_at": "2025-10-06T20:30:15Z",
      "file_count": 247
    },
    {
      "name": "arda-credit-app",
      "owner": "ardaglobal",
      "updated_at": "2025-10-06T19:45:22Z",
      "file_count": 183
    }
  ]
}
```

**Use cases:**
- After pushing major changes to repositories
- When you need fresh structure data immediately
- To verify GitHub API connectivity
- Cache normally refreshes automatically every hour

### `list_collections`

List all available Qdrant collections with basic statistics.

```python
# Returns:
{
  "collections": [
    {
      "name": "arda_code_rust",
      "points_count": 25000,
      "vectors_count": 25000,
      "status": "green"
    },
    # ... more collections
  ],
  "total_collections": 4
}
```

### `get_collection_info`

Get detailed information about a specific collection.

```python
# Arguments:
# - collection_name: str (e.g., "arda_code_rust")

# Returns:
{
  "name": "arda_code_rust",
  "status": "green",
  "points_count": 25000,
  "vectors_count": 25000,
  "indexed_vectors_count": 25000,
  "segments_count": 2,
  "vector_size": 4096,
  "distance": "cosine"
}
```

#### `semantic_search` (Enhanced in v1.2.0)

Perform semantic search across code embeddings using natural language queries. **Now with 30-minute caching!**

```python
# Arguments:
# - query: str (required) - Natural language search query
# - collection_name: str (default: "arda_code_rust") - Target collection
# - limit: int (default: 20) - Maximum results (1-50)
# - score_threshold: float (default: 0.5) - Minimum similarity score (0.0-1.0)

# Example:
# query="authentication logic with JWT tokens"
# collection_name="arda_code_rust"
# limit=20
# score_threshold=0.5

# Returns:
{
  "query": "authentication logic with JWT tokens",
  "collection": "arda_code_rust",
  "results_count": 18,
  "results": [
    {
      "id": "rust_chunk_1234",
      "score": 0.87,
      "payload": {
        "file_path": "api/src/authentication_handlers.rs",
        "content": "pub async fn verify_jwt_token(token: &str) -> Result<Claims, AuthError> { ... }",
        "language": "rust",
        "chunk_type": "function"
      }
    },
    # ... more results
  ],
  "parameters": {
    "limit": 20,
    "score_threshold": 0.5
  },
  "from_cache": false  # True if result was cached
}
```

**Performance**: < 500ms for cached queries, < 2s for uncached queries.

#### `batch_semantic_search`

Perform multiple semantic searches efficiently to get comprehensive context.

```python
# Arguments:
# - queries: List[str] (required) - List of search queries (max 10)
# - collection_name: str (default: "arda_code_rust") - Target collection
# - limit_per_query: int (default: 10) - Results per query (1-20)
# - score_threshold: float (default: 0.6) - Minimum similarity score

# Example:
batch_semantic_search(
    queries=[
        "deal origination API handler",
        "KYC validation for deals",
        "database schema for deals table"
    ],
    collection_name="arda_code_rust",
    limit_per_query=10
)

# Returns: Up to 100 results (10 queries × 10 results)
{
  "batch_size": 3,
  "collection": "arda_code_rust",
  "total_results": 28,
  "queries": {
    "deal origination API handler": { /* search results */ },
    "KYC validation for deals": { /* search results */ },
    "database schema for deals table": { /* search results */ }
  }
}
```

#### `cross_collection_search` (Enhanced in v1.2.0)

Search across multiple collections for full-stack feature exploration. **Now with better error handling!**

```python
# Arguments:
# - query: str (required) - Natural language search query
# - collections: List[str] (optional) - Collections to search (default: all 3 code collections)
# - limit_per_collection: int (default: 10) - Results per collection (1-20)
# - score_threshold: float (default: 0.6) - Minimum similarity score

# Example:
cross_collection_search(
    query="USDC deposit flow from frontend to smart contract",
    collections=["arda_code_typescript", "arda_code_rust", "arda_code_solidity"],
    limit_per_collection=10
)

# Returns: Up to 30 results (3 collections × 10 results)
{
  "query": "USDC deposit flow from frontend to smart contract",
  "collections_searched": 3,
  "successful_searches": 3,
  "failed_searches": 0,
  "total_results": 27,
  "results_by_collection": {
    "arda_code_typescript": { /* frontend results */ },
    "arda_code_rust": { /* backend results */ },
    "arda_code_solidity": { /* contract results */ }
  }
}
```

**Improvement in v1.2.0**: Gracefully handles missing collections and provides detailed error information.

### Specialized Query Tools ⭐ NEW in v1.2.0

These tools answer specific common questions about the Arda codebase:

#### `get_auth_systems`

Find all authentication implementations across the Arda stack.

```python
# No arguments required

# Returns:
{
  "summary": "Authentication systems across Arda stack",
  "by_layer": {
    "frontend": [ /* auth components */ ],
    "backend": [ /* auth handlers */ ],
    "middleware": [ /* auth middleware */ ]
  },
  "key_implementations": [
    {
      "layer": "backend",
      "file": "repos/arda-credit/api/src/handlers/auth/jwt.rs",
      "type": "jwt_handler",
      "repo": "arda-credit",
      "preview": "..."
    }
  ],
  "auth_flows": ["JWT-based authentication", "OAuth 2.0 authorization"]
}
```

**Use this to answer**: "What are the authentication systems used across the ARDA stack?"

#### `get_stack_overview`

Get comprehensive overview of the entire Arda technical stack.

```python
# No arguments required

# Returns:
{
  "summary": "Complete Arda technical stack",
  "services_by_type": {
    "frontend": ["arda-platform", "arda-homepage"],
    "backend": ["arda-credit"],
    "middleware": ["arda-chat-agent", "arda-ingest"]
  },
  "technology_stack": {
    "frontend": ["TypeScript", "React", "Next.js"],
    "backend": ["Rust", "Axum", "Tokio"],
    "infrastructure": ["Kubernetes", "Helm", "Terraform"]
  },
  "deployment_info": { /* helm charts */ }
}
```

**Use this to answer**: "Walk me through the ARDA technical stack"

#### `get_deployed_services`

List all deployed services with their configurations.

```python
# Arguments:
# - environment: str (optional) - "production" (default), "staging", "dev"

# Returns:
{
  "environment": "production",
  "services_count": 8,
  "services": {
    "arda-credit": {
      "type": "Deployment",
      "container_images": ["arda-credit:v1.2.3"],
      "env_vars": { /* environment variables */ },
      "ports": [8080, 8443]
    }
  }
}
```

**Use this to answer**: "What services are deployed in production?"

#### `find_service_location`

Find where a service, function, or feature is implemented.

```python
# Arguments:
# - query: str (required) - What to search for
# - search_scope: str (optional) - "all", "frontend", "backend", "middleware", "infrastructure"

# Returns:
{
  "query": "balance calculation",
  "search_scope": "backend",
  "total_results": 12,
  "locations": [
    {
      "repo": "arda-credit",
      "file": "repos/arda-credit/lib/src/balance.rs",
      "lines": "45-67",
      "item_name": "calculate_balance",
      "relevance_score": 0.89,
      "preview": "..."
    }
  ],
  "top_match": { /* best match */ }
}
```

**Use this to answer**: "Where does X occur?" or "Find the implementation of Y"

#### `trace_service_dependencies`

Show complete dependency tree for a service.

```python
# Arguments:
# - service_name: str (required) - e.g., "arda-credit"

# Returns:
{
  "service": "arda-credit",
  "depends_on": {
    "services": [],
    "databases": ["postgresql"],
    "external_apis": ["blockchain-rpc"]
  },
  "depended_by": ["arda-platform", "arda-chat-agent"],
  "api_endpoints": [ /* API endpoints */ ],
  "deployment": { /* deployment config */ },
  "dependency_graph": {
    "nodes": [...],
    "edges": [...]
  }
}
```

**Use this to answer**: "What does X depend on?" or "What calls service Y?"

---

### MCP Metadata Tools ⭐ NEW in v1.2.0

These tools provide programmatic discovery of available resources and prompts according to the MCP specification:

#### `list_resources`

List all available MCP resources exposed by the server.

```python
# No arguments required

# Returns:
{
  "resources": [
    {
      "uri": "arda://collections",
      "name": "Collection Information",
      "description": "Live collection stats, repository structure...",
      "mime_type": "text/markdown"
    },
    # ... 9 more resources
  ],
  "count": 10,
  "server": "arda-vector-db"
}
```

**Use this to answer**: "What resources are available?"

#### `read_resource`

Read a specific MCP resource by its URI.

```python
# Arguments:
# - uri: str (required) - Resource URI (e.g., "arda://collections")

# Example:
read_resource("arda://collections")

# Returns:
{
  "uri": "arda://collections",
  "content": "# Arda Credit Vector Collections\n\n...",
  "mime_type": "text/markdown",
  "length": 5432
}
```

**Use this to answer**: "Show me the collections resource", "What's in arda://dashboard?"

#### `list_prompts`

List all available pre-configured prompts (search templates).

```python
# No arguments required

# Returns:
{
  "prompts": [
    {
      "name": "search_deal_operations",
      "description": "Search for deal management operations...",
      "parameters": [
        {
          "name": "operation_type",
          "type": "string",
          "default": "all",
          "options": ["origination", "payment", "transfer", "marketplace", "all"]
        }
      ],
      "example_use": "Find deal payment processing logic in the backend"
    },
    # ... 11 more prompts
  ],
  "count": 12
}
```

**Use this to answer**: "What prompts are available?", "Show me search templates"

#### `get_prompt` (Enhanced in v1.2.1)

Get details about a specific prompt and generate its search instructions. **Now handles required parameters gracefully with placeholders!**

```python
# Arguments:
# - name: str (required) - Prompt name (e.g., "search_deal_operations")

# Example:
get_prompt("search_deal_operations")

# Returns:
{
  "name": "search_deal_operations",
  "description": "Search for deal management operations...",
  "parameters": [
    {
      "name": "operation_type",
      "type": "string",
      "default": "all",
      "required": false
    }
  ],
  "instructions": "Find deal management code in Arda Credit platform...",
  "has_required_params": false
}

# For prompts with required params (e.g., search_frontend_feature):
get_prompt("search_frontend_feature")
# Returns instructions with placeholder: "Search for <feature_name> in frontend..."
```

**Use this to answer**: "Show me the deal operations prompt", "What does debug_arda_issue do?"

#### `execute_prompt` ⭐ NEW in v1.2.1

Execute a prompt's search strategy automatically by parsing instructions and running searches.

```python
# Arguments:
# - name: str (required) - Prompt name
# - **kwargs: Prompt-specific parameters (varies by prompt)

# Example:
execute_prompt("search_deal_operations", operation_type="payment")

# Returns:
{
  "prompt_name": "search_deal_operations",
  "parameters": {"operation_type": "payment"},
  "instructions": "Find deal payment processing...",
  "searches_executed": 3,
  "total_results": 42,
  "results": [ /* Top 50 results */ ],
  "execution_summary": "Executed 3 searches across 3 collections, found 42 total results"
}

# More examples:
execute_prompt("debug_arda_issue", issue_description="deal payment failure")
execute_prompt("search_frontend_feature", feature_name="investor portfolio")
execute_prompt("search_zkproof_implementation")  # No params required
```

**Use this to answer**: "Execute the deal operations search", "Run the zkproof prompt"

**Benefits:**
- Automatic parsing of search strategy from prompt instructions
- Executes multiple collection searches in parallel
- Aggregates and ranks results by score
- Returns top 50 results across all searches

---

### MCP Prompts (12 Total - Expanded in v1.2.0)

Pre-built search templates that guide AI assistants to search the Arda Credit codebase effectively:

1. **`search_deal_operations(operation_type)`** - Find deal management code (origination, payment, transfer, marketplace)
2. **`search_zkproof_implementation()`** - Find SP1 zero-knowledge proof implementation
3. **`search_authentication_system(auth_type)`** - Find magic link auth, JWT, sessions
4. **`search_usdc_integration()`** - Find USDC deposit/withdrawal smart contract integration
5. **`search_frontend_feature(feature_name)`** - Find React components and features
6. **`debug_arda_issue(issue_description)`** - Debug-focused multi-collection search
7. **`explore_architecture_layer(layer)`** - Explore presentation, business, data, or blockchain layers
8. **`find_api_endpoint(endpoint_pattern)`** - Find API endpoint implementations
9. **`trace_data_flow(entity)`** - Trace data flow for an entity through the stack
10. **`find_test_coverage(feature)`** - Find test coverage for a feature
11. **`explore_deployment_config(service)`** - Explore deployment configurations
12. **`audit_security_patterns(concern)`** - Audit security implementations

Use `list_prompts()` and `get_prompt(name)` tools to discover and explore these templates programmatically.

### MCP Resources (10 Total - Expanded in v1.2.1)

**Dynamic documentation** that stays synchronized with GitHub repositories:

1. **`arda://collections`** - Live repository structure and collection information
2. **`arda://search-tips`** - Enhanced search best practices with live repository insights
3. **`arda://dashboard`** - Real-time collection health metrics and status
4. **`arda://api-catalog`** - Complete catalog of all API endpoints
5. **`arda://patterns`** - Common code patterns and best practices
6. **`arda://stats`** - Live codebase statistics (LOC, files, languages)
7. **`arda://dependencies`** - Service dependency map and integration points
8. **`arda://changelog`** ⭐ NEW - Recent code changes and repository updates
9. **`arda://metrics`** ⭐ NEW - Performance metrics and operational insights
10. **`arda://architecture`** ⭐ NEW - System architecture with Mermaid diagrams

Use `list_resources()` and `read_resource(uri)` tools to discover and access these resources programmatically.

**How it works:**
- Server fetches repository structure via GitHub API on startup
- Cache refreshes automatically every hour (configurable with `_repo_cache_ttl`)
- Use `refresh_repo_cache()` tool to manually force immediate refresh
- Requires `GHCR_TOKEN`, `ARDA_CREDIT_REPO_URL`, and `ARDA_CREDIT_APP_REPO_URL` in `.env` (optional)

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (Cursor/Claude)                │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
┌─────────────────────▼───────────────────────────────────────┐
│              Arda Vector Database MCP Server                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  FastMCP Features:                                  │    │
│  │  Tools (6):                                         │    │
│  │  - health_check()                                   │    │
│  │  - list_collections()                               │    │
│  │  - get_collection_info(collection_name)             │    │
│  │  - semantic_search(query, collection, limit, ...)   │    │
│  │  - batch_semantic_search(queries, ...)              │    │
│  │  - cross_collection_search(query, collections, ...) │    │
│  │  Prompts (6): search_deal_operations, etc.          │    │
│  │  Resources (2): arda://collections, arda://search-tips │ │
│  └─────────────────────────────────────────────────────┘    │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
             │                          │
  ┌──────────▼──────────┐    ┌─────────▼────────────┐
  │  Qdrant Vector DB   │    │  Embedding Endpoint  │
  │  - 4096-dim vectors │    │   Service (L4 GPU)   │
  │  - Cosine distance  │    │   - Qwen3-8B model   │
  │  - Multi-collection │    │   - 45 emb/sec       │
  └─────────────────────┘    └──────────────────────┘
```

### Data Flow

1. **Query Processing** - AI assistant sends natural language query via MCP
2. **Embedding Generation** - Server forwards query to embedding endpoint (Cloudflare AI gateway)
3. **Vector Search** - Embedding used to search Qdrant collections
4. **Result Formatting** - Top results returned with scores and metadata
5. **Context Enhancement** - AI assistant uses results for code understanding

### Technology Stack

- **FastMCP** - MCP server framework
- **Qdrant** - Vector database (cloud or self-hosted)
- **Cloudflare AI Gateway** - Embedding service endpoint
- **Qwen3-Embedding-8B** - 4096-dimensional embedding model
- **httpx** - HTTP client for embedding endpoint communication

## 📊 Available Collections

### Code Collections (Arda Credit Platform)

- **`arda_code_rust`** - Rust backend for Arda Credit
  - API server, database layer, SP1 zkVM program, Ethereum client
  - Technologies: Rust, Axum, SQLx, Alloy, SP1 zkVM

- **`arda_code_typescript`** - React frontend for Arda Credit
  - Components (deals, investments, auth, portfolio, profile), pages, utilities
  - Technologies: React 18, TypeScript, Vite, shadcn/ui, React Query

- **`arda_code_solidity`** - Smart contracts for Arda Credit
  - ARDA.sol (proof verification), MockUSDC.sol, ARDAFaucet.sol
  - Technologies: Solidity 0.8.28, Foundry, SP1 Groth16 verifier

### Documentation Collection

- **`arda_documentation`** - Architecture docs, API specs, deployment guides
  - Three-component architecture, deal system design, privacy guarantees

### Collection Metadata

Each code chunk includes:
- `file_path` - Relative path from repository root
- `content` - Code snippet (typically 500 tokens)
- `language` - Programming language (rust, typescript, solidity)
- `chunk_type` - Type of code (function, struct, class, module, etc.)
- `start_line` / `end_line` - Line numbers in source file

## 🔍 Search Examples

### Finding Authentication Logic

```python
semantic_search(
    query="JWT token validation and authentication middleware",
    collection_name="arda_code_rust",
    limit=5,
    score_threshold=0.6
)
```

### Finding React Components

```python
semantic_search(
    query="credit score display component with charts",
    collection_name="arda_code_typescript",
    limit=10,
    score_threshold=0.5
)
```

### Finding Smart Contract Functions

```python
semantic_search(
    query="loan approval logic with zero-knowledge proof verification",
    collection_name="arda_code_solidity",
    limit=5,
    score_threshold=0.7
)
```

### Architecture Documentation

```python
semantic_search(
    query="system architecture and component interactions",
    collection_name="arda_documentation",
    limit=3,
    score_threshold=0.5
)
```

## ⚙️ Configuration

### Environment Variables

| Variable                | Required | Description                                                                                 |
| ----------------------- | -------- | ------------------------------------------------------------------------------------------- |
| `QDRANT_URL`            | Yes      | Qdrant instance URL (e.g., `https://xxxxx.gcp.cloud.qdrant.io`)                             |
| `QDRANT_API_KEY`        | Yes      | Qdrant JWT authentication token                                                             |
| `EMBEDDING_ENDPOINT`    | Yes      | Embedding service base URL (format: `https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat`) |
| `CLOUDFLARE_API_TOKEN`  | Yes      | Cloudflare API token for authentication                                                      |
| `DEEPINFRA_API_KEY`     | Yes      | Deep Infra provider API key (required for embeddings)                                        |
| `OPENROUTER_API_KEY`    | Optional | For LLM features (not used by MCP server)                                                   |

### Qdrant Setup

#### Option 1: Qdrant Cloud (Recommended)

1. Create account at [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create a cluster (free tier available)
3. Copy cluster URL and API key to `.env`

#### Option 2: Self-Hosted

```bash
# Using Docker
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant

# Set in .env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Leave empty for local instance
```

### Embedding Endpoint

The server uses Cloudflare AI gateway for embedding generation. The `EMBEDDING_ENDPOINT` should be the full base URL in the format:
`https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat`

The server will automatically append `/embeddings` to this base URL. You must provide both:
- `CLOUDFLARE_API_TOKEN` - Cloudflare Gateway authentication token
- `DEEPINFRA_API_KEY` - Deep Infra provider API key (for the actual embedding service)

Example:
```
EMBEDDING_ENDPOINT=https://gateway.ai.cloudflare.com/v1/2de868ad9edb1b11250bc516705e1639/aig/compat
CLOUDFLARE_API_TOKEN=your_cloudflare_token
DEEPINFRA_API_KEY=your_deepinfra_api_key
```

## 🎯 Arda Credit Specific Features

### Domain-Specific Search Patterns

The server includes **6 pre-built prompts** optimized for Arda Credit development:

1. **Deal Operations** - Search for deal origination, payments, transfers, marketplace
2. **ZK Proof System** - Find SP1 zkVM implementation, batch processing, privacy guarantees
3. **Authentication** - Locate magic link auth, KYC validation, user management
4. **USDC Integration** - Find deposit/withdrawal flows across frontend, backend, contracts
5. **Frontend Features** - Search React components with specific feature names
6. **Debugging** - Multi-collection search with lower thresholds for issue investigation

### Collection-Specific Guidance

The server provides **2 resources** with static documentation:

1. **`arda://collections`** - Detailed breakdown of each collection's structure and tech stack
2. **`arda://search-tips`** - Best practices for query formulation and parameter tuning

### Context Limit Optimization

**v1.1.0 increases default limits by 2x** to better handle Arda Credit's codebase size:

| Search Type      | Results       | Use Case                            |
| ---------------- | ------------- | ----------------------------------- |
| Single query     | 20 (was 10)   | Standard code search                |
| Batch search     | 100 (10×10)   | Comprehensive feature understanding |
| Cross-collection | 30 (3×10)     | Full-stack feature exploration      |
| Combined max     | 300 (10×3×10) | Deep architectural analysis         |

## 🛡️ Security & Best Practices

### Read-Only Operations

The MCP server is designed for **read-only** vector search operations. It does not support:
- Writing new vectors to Qdrant
- Modifying existing collections
- Creating or deleting collections
- Updating collection configuration

### API Key Security

- Store credentials in `.env` file (never commit to git)
- Use environment variables in MCP configuration
- Rotate Qdrant API keys periodically
- Use separate API keys for development and production

### Network Security

- Qdrant Cloud provides TLS encryption by default
- Use HTTPS for embedding endpoints
- Consider VPC networking for production deployments
- Monitor API usage through Qdrant dashboard

## 📈 Performance

### Typical Metrics (v1.2.0)

- **Search Latency (Cached)**: < 500ms ⚡ NEW
- **Search Latency (Uncached)**: < 2s
- **Cache Hit Rate**: > 60% after warmup ⚡ NEW
- **Embedding Generation**: Via Cloudflare AI gateway
- **Vector Dimensions**: 4096 (Qwen3-Embedding-8B)
- **Search Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Distance Metric**: Cosine similarity

### Caching ⭐ NEW in v1.2.0

Query results are automatically cached for 30 minutes:
- **First query**: Full search (< 2s)
- **Repeated query**: From cache (< 500ms)
- **Cache size**: Up to 1000 queries
- **TTL**: 30 minutes
- **Automatic eviction**: Oldest entries removed when cache is full

### Optimization Tips

1. **Use Smart Search** - ⭐ NEW: Automatically routes to the best tool
2. **Score Threshold** - Use higher thresholds (0.6-0.8) for precision, lower (0.4-0.5) for recall
3. **Limit** - Default 20 results balances context and speed (max 50)
4. **Batch Search** - Use for comprehensive understanding (10 queries × 10 results = 100 total)
5. **Cross-Collection** - Use for full-stack features (3 collections × 10 results = 30 total)
6. **Collection Selection** - Search specific language collections for better accuracy
7. **Query Quality** - More specific queries yield better results
8. **Use Prompts** - Pre-built templates provide optimized search strategies
9. **Specialized Tools** - ⭐ NEW: Use `get_auth_systems`, `get_stack_overview`, etc. for common queries

## 🧪 Testing

### Quick Local Testing

Run the comprehensive test script to verify all components:

```bash
# Make sure your .env file is set up with:
# - QDRANT_URL
# - QDRANT_API_KEY
# - CLOUDFLARE_API_TOKEN
# - EMBEDDING_ENDPOINT (optional, defaults to https://gateway.ai.cloudflare.com)

# Run the test script
python test_local.py
```

The test script will verify:
1. ✅ Environment variable validation
2. ✅ Qdrant connection and collections
3. ✅ Embedding endpoint connection (with Cloudflare token)
4. ✅ Semantic search functionality

### Manual Testing

```bash
# Start the server
python server.py

# The server will:
# - Validate environment variables
# - Connect to Qdrant
# - Warm up the embedding endpoint
# - Be ready to accept MCP connections
```

### Quick Health Check

```bash
# Verify environment and Qdrant connection
python -c "
from server import validate_environment, initialize_qdrant_client
config = validate_environment()
client = initialize_qdrant_client(config)
print('✅ All systems operational')
"
```

### Testing Embedding Endpoint Directly

```bash
# Test Cloudflare embedding endpoint with curl
curl -X POST https://gateway.ai.cloudflare.com \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["test query"]}'
```

## 🐛 Troubleshooting

### "Qdrant client not initialized"

**Cause**: Server failed to connect to Qdrant during startup.

**Solutions**:
- Verify `QDRANT_URL` is accessible from your network
- Check `QDRANT_API_KEY` is valid and has read permissions
- Ensure Qdrant service is running and healthy

### "Cloudflare API token not configured"

**Cause**: `CLOUDFLARE_API_TOKEN` environment variable is missing.

**Solutions**:
- Obtain a Cloudflare API token from your Cloudflare account
- Add `CLOUDFLARE_API_TOKEN` to your `.env` file
- The `EMBEDDING_ENDPOINT` defaults to `https://gateway.ai.cloudflare.com` if not specified
- Verify endpoint is accessible with authentication

### "Collection 'X' not found"

**Cause**: Requested collection doesn't exist in Qdrant.

**Solutions**:
- Run `health_check()` to list available collections
- Ingest codebase using i2p ingestion pipeline
- Verify collection names match expected values

### "Failed to generate query embedding"

**Cause**: Embedding endpoint is unreachable or erroring.

**Solutions**:
- Check embedding endpoint (Cloudflare AI gateway) status
- Verify `EMBEDDING_ENDPOINT` URL is correct
- Check endpoint logs for service errors

### "Invalid embedding dimensions"

**Cause**: Embedding endpoint returned embedding with wrong dimensions.

**Solutions**:
- Verify embedding endpoint is using Qwen3-Embedding-8B model
- Check embedding endpoint configuration
- Check endpoint logs for configuration issues

## 📚 Documentation

- **[docs/TOOLS_GUIDE.md](./docs/TOOLS_GUIDE.md)** ⭐ NEW - Comprehensive guide for all tools
- **[docs/MANUAL_TESTS.md](./docs/MANUAL_TESTS.md)** ⭐ NEW - Manual test scenarios
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** ⭐ NEW - Deployment checklist and verification
- **[server.py](./server.py)** - Complete MCP server implementation with inline documentation
- **[src/cache.py](./src/cache.py)** ⭐ NEW - Query result caching implementation
- **[src/query_router.py](./src/query_router.py)** ⭐ NEW - Intelligent query routing
- **[src/response_formatter.py](./src/response_formatter.py)** ⭐ NEW - IDE-optimized response formatting
- **[src/collections.py](./src/collections.py)** ⭐ NEW - Collection schema and aliases
- **[FastMCP Documentation](https://github.com/gofastmcp/fastmcp)** - MCP framework reference
- **[Qdrant Documentation](https://qdrant.tech/documentation/)** - Vector database reference

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Follow the [i2p coding standards](./i2p/CLAUDE.md)
2. Keep files under 500 lines
3. Use single responsibility principle
4. Add comprehensive tests for new features
5. Update documentation for all changes

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

## 🔗 Related Projects

- **[I2P Meta-Reasoning System](./i2p/)** - Strategic technical advisory for AI agents
- **[FastMCP](https://github.com/gofastmcp/fastmcp)** - Model Context Protocol framework
- **[Qdrant](https://qdrant.tech/)** - Vector database for semantic search
- **Cloudflare AI Gateway** - Embedding service endpoint

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/ardaglobal/arda-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ardaglobal/arda-mcp/discussions)
- **Email**: support@arda.global

## 📋 Version History

### v1.2.1 (Current)
**Release Date**: 2025-11-19

**New Features:**
- ⭐ **execute_prompt Tool** - Automatically execute prompt search strategies with parameter support
- ⭐ **3 New Resources** - changelog (recent updates), metrics (performance insights), architecture (Mermaid diagrams)

**Improvements:**
- Enhanced `get_prompt` to handle required parameters gracefully with placeholders
- Fixed dashboard resource `hit_rate` variable bug
- Fixed search-tips and stats resources missing import errors
- All resources now properly reference dependencies

**Bug Fixes:**
- Dashboard: Use `hit_rate_percent` instead of `hit_rate`
- Search tips: Import `get_cached_repo_structures` function
- Stats: Import `get_cached_repo_structures` function
- Get prompt: Handle prompts with required parameters without throwing errors

**Total Counts:**
- 19 tools (added 1: `execute_prompt`)
- 12 prompts (unchanged)
- 10 resources (added 3: `changelog`, `metrics`, `architecture`)

### v1.2.0
**Release Date**: 2025-11-19

**New Features:**
- ⭐ **Smart Search** - Intelligent query routing to best tool
- ⭐ **5 Specialized Tools** - Common query patterns (auth, stack, deployed services, location finder, dependencies)
- ⭐ **4 MCP Metadata Tools** - Programmatic discovery (`list_resources`, `read_resource`, `list_prompts`, `get_prompt`)
- ⭐ **Query Caching** - 30-minute TTL, < 500ms cached responses
- ⭐ **Response Formatting** - IDE-optimized responses for Cursor/Claude Code
- ⭐ **Query Router** - Automatic intent detection and tool selection
- ⭐ **Collection Schema** - Comprehensive collection definitions and aliases
- ⭐ **Expanded Prompts** - 12 prompts (was 6) with new architecture, API, testing, deployment, and security templates
- ⭐ **Expanded Resources** - 7 resources (was 2) with API catalog, code patterns, stats, and dependencies

**Improvements:**
- Enhanced `cross_collection_search` with better error handling
- All search tools now async for better performance
- Graceful degradation when collections are missing
- Detailed error reporting with error types
- Cache statistics tracking
- Comprehensive documentation (Tools Guide, Manual Tests, Deployment Guide)
- MCP specification compliance for resource and prompt discovery

**Performance:**
- Response time: < 500ms (cached), < 2s (uncached)
- Cache hit rate: > 60% after warmup
- Supports up to 1000 cached queries
- 18 tools total (was 13) for comprehensive codebase exploration

### v1.1.0
**Release Date**: 2025-01-06

**New Features:**
- ✨ Added 6 domain-specific MCP prompts for Arda Credit codebase
- ✨ Added 2 MCP resources (collections guide, search tips)
- ✨ Added `batch_semantic_search` tool (up to 100 results per call)
- ✨ Added `cross_collection_search` tool (full-stack exploration)
- 🚀 Increased default limits by 2x (20 results vs 10)
- 📚 Updated README with comprehensive v1.1.0 documentation

**Improvements:**
- Better context retrieval for large Arda Credit codebase
- Pre-built search strategies for common development tasks
- Static documentation accessible through MCP resources
- Enhanced full-stack feature exploration capabilities

### v1.0.0
**Release Date**: 2025-01-05

**Initial Release:**
- Basic semantic search functionality
- Collection health monitoring
- Embedding endpoint integration (Cloudflare AI gateway)
- Qdrant vector database connectivity
- Support for 4 collections (rust, typescript, solidity, documentation)

---

**Arda Vector Database MCP Server** - Semantic code search for AI-powered development.
