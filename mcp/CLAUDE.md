# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Arda Vector Database MCP Server - A FastMCP server that provides semantic code search capabilities through Qdrant vector database integration. Designed for Cursor IDE and other MCP-compatible AI assistants to search the Arda Credit platform codebase using natural language queries.

**Version:** 1.2.1
**Framework:** FastMCP 2.0+
**Primary Language:** Python 3.11+

## Core Architecture

### High-Level Components

The server follows a modular architecture with clear separation of concerns:

1. **MCP Server Layer** (`server.py`) - FastMCP server orchestration and lifecycle management (~480 lines)
2. **Tools Layer** (`src/tools/`) - 30 tools organized into 6 modules (collection, search, domain, metadata, code_quality, analytics)
3. **Prompts Layer** (`src/prompts/`) - 12 domain-specific search patterns
4. **Resources Layer** (`src/resources/`) - 10 dynamic documentation resources
5. **Query Intelligence** (`src/query_router.py`) - Intent detection and automatic routing
6. **Caching Layer** (`src/cache.py`) - 30-minute TTL in-memory cache for query results
7. **Response Formatting** (`src/response_formatter.py`) - IDE-optimized output formatting
8. **Collection Schema** (`src/collections.py`) - Vector collection definitions and aliases
9. **Utilities** (`src/utils/`) - GitHub API integration and helper functions

### Directory Structure

```
src/
├── tools/              # MCP tool implementations (30 tools)
│   ├── __init__.py
│   ├── collection.py   # 5 tools: health_check, list_collections, get_collection_info, get_collections_by_type, refresh_repo_cache
│   ├── search.py       # 4 tools: semantic_search, batch_semantic_search, cross_collection_search, smart_search
│   ├── domain.py       # 5 tools: get_auth_systems, get_stack_overview, get_deployed_services, find_service_location, trace_service_dependencies
│   ├── metadata.py     # 5 tools: list_resources, read_resource, list_prompts, get_prompt, execute_prompt
│   ├── code_quality.py # 6 tools: analyze_semantic_coherence, analyze_test_elasticity, analyze_contextual_density,
│   │                   #           analyze_dependency_entropy, analyze_organizational_memory, calculate_oink_score
│   └── analytics.py    # 5 tools: analyze_searchability, analyze_topic_clusters, get_prompt_usage_stats,
│                       #           analyze_architecture_coherence, analyze_documentation_gaps
├── prompts/            # MCP prompt definitions (12 prompts)
│   ├── __init__.py
│   └── prompts.py
├── resources/          # MCP resource definitions (7 resources)
│   ├── __init__.py
│   └── resources.py
├── utils/              # Helper utilities
│   ├── __init__.py
│   ├── github.py       # GitHub API integration (extended with PR metrics)
│   └── code_analysis.py # Code quality and architecture analysis helpers
├── tracking/           # Usage tracking module (NEW in v1.4.0)
│   ├── __init__.py
│   └── prompt_tracker.py # Prompt usage tracking singleton
├── cache.py            # Query result caching
├── collections.py      # Collection schema
├── query_router.py     # Query routing logic
└── response_formatter.py  # Response formatting
```

### Key Design Patterns

- **Read-Only Operations**: Server provides semantic search only; no ingestion or write capabilities
- **Async-First**: All search tools use `async/await` for concurrent operations
- **Global State Management**: Qdrant client and embedding endpoint stored in module-level globals, initialized in `lifespan` context manager
- **Tool Composition**: High-level tools (e.g., `smart_search`) compose lower-level tools (e.g., `semantic_search`)

### Data Flow

```
User Query → QueryRouter → Specialized Tool → Embedding Endpoint (Cloudflare AI Gateway) → Qdrant Vector Search → ResponseFormatter → User
                                              ↑
                                         QueryCache
                                      (30-min TTL)
```

## Development Commands

### Running the Server

```bash
# Start MCP server (with environment variables)
python server.py

# With explicit environment (for testing)
QDRANT_URL=https://your-qdrant.io \
QDRANT_API_KEY=your-key \
EMBEDDING_ENDPOINT=https://your-embedding-endpoint.run \
python server.py
```

### Testing

```bash
# Manual testing via health check
python -c "
from server import validate_environment, initialize_qdrant_client
config = validate_environment()
client = initialize_qdrant_client(config)
print('✅ All systems operational')
"

# Run pytest (if tests exist)
pytest -v

# Test with MCP client (Cursor or Claude Desktop)
# Configure in ~/.cursor/mcp.json or ~/Library/Application Support/Claude/claude_desktop_config.json
```

### Environment Setup

Required environment variables in `.env`:
- `QDRANT_URL` - Qdrant instance URL (required)
- `QDRANT_API_KEY` - Qdrant authentication token (required)
- `EMBEDDING_ENDPOINT` - Embedding service base URL (required, format: `https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat`)
- `CLOUDFLARE_API_TOKEN` - Cloudflare API token for authentication (required)
- `DEEPINFRA_API_KEY` - Deep Infra provider API key (required)
- `GHCR_TOKEN` - GitHub token for repo structure fetching (optional, for dynamic resources)
- `ARDA_CREDIT_REPO_URL` - arda-credit repo URL (optional)
- `ARDA_CREDIT_PLATFORM` - arda-platform repo URL (optional)

## Critical Implementation Details

### Embedding Generation

- **Model**: Qwen3-Embedding-8B (4096-dimensional vectors)
- **Infrastructure**: Cloudflare AI gateway
- **Cold Start**: Server pre-warms embedding endpoint on startup (30s timeout) to avoid delays
- **Request Format**: `POST /embed` with `{"texts": ["query"]}`
- **Response**: `{"results": [{"embedding": [4096 floats]}]}`

### Caching Strategy

Query results cached for 30 minutes with automatic eviction:
- **Cache Key**: MD5 hash of `{query, collection, params}`
- **Size Limit**: 1000 entries max (evicts 100 oldest when full)
- **Performance**: <500ms for cached queries, <2s for uncached
- **Location**: `_query_cache` global variable in `server.py:79`

### Query Routing Logic

The `QueryRouter` (src/query_router.py) uses regex pattern matching to detect intent:
- **auth_systems**: Authentication-related queries → `get_auth_systems()`
- **stack_overview**: Architecture/stack queries → `get_stack_overview()`
- **deployed_services**: Deployment queries → `get_deployed_services(environment)`
- **find_location**: "Where is X" queries → `find_service_location(query, scope)`
- **trace_dependencies**: Dependency queries → `trace_service_dependencies(service)`
- **Default**: Generic queries → `semantic_search(query, collection, limit)`

### Collection Organization

Collections are organized by four patterns (see `src/collections.py`):
1. **BY_LANGUAGE**: `arda_code_rust`, `arda_code_typescript`, `arda_code_solidity`, etc.
2. **BY_REPO**: `arda_repo_platform`, `arda_repo_credit`, etc.
3. **BY_SERVICE**: `arda_frontend`, `arda_backend`, `arda_middleware`, etc.
4. **BY_CONCERN**: `arda_api_contracts`, `arda_database_schemas`, `arda_deployment`, etc.

Use `resolve_collection_name(alias)` to map shortcuts (e.g., "rust" → "arda_code_rust")

### Server Lifecycle Management

The `lifespan` async context manager (server.py:295-367) handles:
1. Environment validation
2. Qdrant client initialization
3. Embedding endpoint warmup (async background task)
4. Resource cleanup on shutdown

**Important**: Never initialize Qdrant or embedding endpoint clients outside the lifespan context.

## Code Style Guidelines

### File Organization

- **server.py**: ~350 lines (orchestration only)
- **Tool modules**: 200-400 lines each (single responsibility per module)
- **Prompt/Resource modules**: < 500 lines each
- **Utility modules**: < 300 lines each
- Single responsibility: Each module has one clear purpose
- Use OOP-first design with classes for stateful components (e.g., `QueryCache`, `QueryRouter`)
- Tools, prompts, and resources are organized in separate directories under `src/`

### Error Handling

- Use FastMCP exceptions: `ToolError`, `NotFoundError`, `ResourceError`
- Graceful degradation: Tools continue if some collections are missing
- Detailed error types in responses (e.g., `error_type: "not_found"`)

### Async Patterns

```python
# Good: Parallel independent operations
for collection in collections:
    result = await semantic_search(...)  # Each awaited in sequence

# Better: Use asyncio.gather for true parallelism
results = await asyncio.gather(*[
    semantic_search(query, coll) for coll in collections
])
```

### Logging

- Use module-level logger: `logger = logging.getLogger(__name__)`
- Emojis in logs for visual scanning (🔍 search, ✅ success, ❌ error, ⚡ cache hit)
- Debug-level logs for cache hits/misses
- Info-level logs for major operations

## MCP Metadata Discovery

The server provides tools for programmatic discovery of available resources and prompts according to the MCP specification:

### Resources Discovery

Resources are contextual data/documentation that can be read:

```python
# List all available resources
result = await list_resources()
# Returns: {"resources": [...], "count": 7, "server": "arda-vector-db"}

# Read a specific resource
result = await read_resource("arda://collections")
# Returns: {"uri": "...", "content": "...", "mime_type": "text/markdown"}
```

Available resources:
- `arda://collections` - Collection information and structure
- `arda://search-tips` - Search best practices
- `arda://dashboard` - Collection health metrics
- `arda://api-catalog` - API endpoint catalog
- `arda://patterns` - Code patterns library
- `arda://stats` - Codebase statistics
- `arda://dependencies` - Service dependency map

### Prompts Discovery

Prompts are pre-configured query templates:

```python
# List all available prompts
result = list_prompts()
# Returns: {"prompts": [...], "count": 12}

# Get details about a specific prompt
result = get_prompt("search_deal_operations")
# Returns: {"name": "...", "description": "...", "parameters": [...], "instructions": "..."}
```

These tools enable IDE integrations and AI assistants to:
1. Discover available resources without hardcoding
2. Dynamically list search templates
3. Generate contextual help and documentation
4. Provide autocomplete suggestions

## Common Patterns for Development

### Adding a New Tool

1. Choose the appropriate module in `src/tools/`:
   - `collection.py` for collection management tools
   - `search.py` for search-related tools
   - `domain.py` for domain-specific query tools
   - `metadata.py` for MCP metadata discovery tools

2. Add your tool function inside the `register_tools(mcp)` function
3. Use `@mcp.tool()` decorator
4. Add comprehensive docstring (args, returns, use cases)
5. Use `async def` for I/O operations
6. Raise `ToolError` for validation failures

Example (in `src/tools/domain.py`):
```python
def register_tools(mcp: FastMCP):
    """Register all domain tools with the MCP server."""

    # ... existing tools ...

    @mcp.tool()
    async def my_new_tool(param: str) -> dict:
        """
        Tool description.

        Args:
            param: Parameter description

        Returns:
            Dictionary with results

        Use this to answer: "Example user question"
        """
        logger.info(f"🔍 My new tool: {param}")
        # Implementation
        return {"result": "data"}
```

**Note**: If your tool needs access to global state (like `_qdrant_client`), make sure the appropriate `set_*_globals()` function is called in `server.py`'s `register_all_features()`.

### Adding a New Prompt

1. Add your prompt function to `src/prompts/prompts.py` at module level (before `register_prompts`)
2. Add the function name to the registration list in `register_prompts()`
3. Import it in `server.py`'s `register_all_features()` and add to `prompt_map`
4. Add metadata entry in `src/tools/metadata.py`'s `list_prompts()` function

Example (in `src/prompts/prompts.py`):
```python
def search_pattern_name(param: str = "default") -> str:
    """Prompt description for documentation."""
    return f"""Search strategy for {param}:

1. Search collection X with query Y
2. Parameters: limit=15, threshold=0.6
3. Focus on: specific aspects
"""

def register_prompts(mcp: FastMCP):
    """Register all prompt functions with the MCP server."""
    mcp.prompt()(search_deal_operations)
    # ... other prompts ...
    mcp.prompt()(search_pattern_name)  # Add your new prompt here
```

**Important**: Also update:
1. Import in `server.py`'s `register_all_features()` function
2. Add to `prompt_map` dictionary in same function
3. Add metadata entry in `src/tools/metadata.py`'s `list_prompts()` array

### Adding a New Resource

1. Add your resource function to `src/resources/resources.py` at module level (before `register_resources`)
2. Add the function to the registration list in `register_resources()`
3. Import it in `server.py`'s `register_all_features()` and add to `resource_map`
4. Add metadata entry in `src/tools/metadata.py`'s `list_resources()` function

Example (in `src/resources/resources.py`):
```python
async def resource_function_name() -> str:
    """Resource description."""
    return """# Resource Content

Markdown-formatted content here...
"""

def register_resources(mcp: FastMCP):
    """Register all resource functions with the MCP server."""
    mcp.resource("arda://collections")(arda_collections_info)
    # ... other resources ...
    mcp.resource("arda://resource-name")(resource_function_name)  # Add your new resource
```

**Important**: Also update:
1. Import in `server.py`'s `register_all_features()` function
2. Add to `resource_map` dictionary in same function
3. Add metadata entry in `src/tools/metadata.py`'s `list_resources()` array

### Modifying Collection Schema

Edit `src/collections.py`:
1. Add to `COLLECTION_SCHEMA` dict with type and description
2. Add aliases to `COLLECTION_ALIASES` if needed
3. Update `DEFAULT_*_COLLECTIONS` lists if applicable

### Cache Management

```python
# Get cache stats
stats = _query_cache.get_stats()

# Clear cache
_query_cache.clear()

# Force expire check
_query_cache.remove_expired()
```

## MCP Server Configuration

### Cursor IDE

Add to `~/.cursor/mcp.json` or project `.mcp.json`:
```json
{
  "mcpServers": {
    "arda-vector-db": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "QDRANT_URL": "https://your-qdrant.io",
        "QDRANT_API_KEY": "your-key",
        "EMBEDDING_ENDPOINT": "https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat",
        "CLOUDFLARE_API_TOKEN": "your-cloudflare-token",
        "DEEPINFRA_API_KEY": "your-deepinfra-key"
      }
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (same format as above)

## Performance Considerations

- **Query Cache**: Achieves >60% hit rate after warmup, reduces response time by 75%
- **Batch Operations**: `batch_semantic_search` reuses embeddings for efficiency (max 10 queries)
- **Collection Selection**: Specific collections (e.g., `arda_code_rust`) faster than cross-collection search
- **Score Threshold**: Higher thresholds (0.7+) = fewer results but faster; lower (0.4-0.5) = more comprehensive

## Troubleshooting

### "Qdrant client not initialized"
- Check `QDRANT_URL` and `QDRANT_API_KEY` in environment
- Verify Qdrant service is accessible
- Check server startup logs for connection errors

### "Embedding endpoint not configured" or "Cloudflare API token not configured"
- Ensure `CLOUDFLARE_API_TOKEN` is set (required)
- `EMBEDDING_ENDPOINT` defaults to `https://gateway.ai.cloudflare.com` if not specified
- Verify embedding service (Cloudflare AI gateway) is accessible
- Check warmup logs during server startup

### "Collection not found"
- Run `health_check()` tool to list available collections
- Collections are created by separate ingestion system (not this server)
- Check Qdrant dashboard for collection status

### Server won't start
- Check all required env vars are set
- Verify Python version (3.11+ required)
- Check `pip install -r requirements.txt` completed successfully
- Review startup logs for detailed error messages

## Available Tools (30)

### Core Collection Tools
1. `refresh_repo_cache` - Refresh repository structure cache
2. `health_check` - Check Qdrant connection and list collections
3. `get_collection_info` - Get detailed info about a specific collection
4. `list_collections` - List all available collections
5. `get_collections_by_type` - Get collections filtered by type (language, repo, service, concern)

### Search Tools
6. `semantic_search` - Core semantic search in a single collection
7. `batch_semantic_search` - Search multiple queries efficiently (up to 10)
8. `cross_collection_search` - Search across multiple collections
9. `smart_search` - Intelligent query routing to the best tool

### Domain-Specific Tools
10. `get_auth_systems` - Find authentication and authorization implementations
11. `get_stack_overview` - Get high-level tech stack and architecture overview
12. `get_deployed_services` - Find deployed services and infrastructure
13. `find_service_location` - Find where specific services/features are implemented
14. `trace_service_dependencies` - Trace dependencies for a service

### MCP Metadata Tools
15. `list_resources` - List all available MCP resources (documentation, catalogs, stats)
16. `read_resource` - Read a specific resource by URI (e.g., "arda://collections")
17. `list_prompts` - List all available pre-configured search prompts
18. `get_prompt` - Get details and instructions for a specific prompt (enhanced in v1.2.1)
19. `execute_prompt` - Execute a prompt's search strategy automatically (NEW in v1.2.1)

### Code Quality Analysis Tools (NEW in v1.3.0)
20. `analyze_semantic_coherence` - Analyze code naming quality and detect generic names
21. `analyze_test_elasticity` - Evaluate test quality, mock density, and test robustness
22. `analyze_contextual_density` - Measure information locality and dependency distance
23. `analyze_dependency_entropy` - Detect circular dependencies and god modules
24. `analyze_organizational_memory` - Track AI code effectiveness via GitHub PR metrics
25. `calculate_oink_score` - Calculate comprehensive "Oink Score" across all metrics

### Dashboard Analytics Tools (NEW in v1.4.0)
26. `analyze_searchability` - Calculate search quality scores and coverage analysis
27. `analyze_topic_clusters` - Extract topic clusters with coherence scores and file mappings
28. `get_prompt_usage_stats` - Track prompt usage statistics and analytics
29. `analyze_architecture_coherence` - Comprehensive architecture analysis (4 aspects)
30. `analyze_documentation_gaps` - Detect undocumented code and measure doc quality

## Available Prompts (12)

1. `search_deal_operations` - Search for deal/transaction operations
2. `search_zkproof_implementation` - Search for zero-knowledge proof implementations
3. `search_authentication_system` - Search for authentication patterns
4. `search_usdc_integration` - Search for USDC/stablecoin integration
5. `search_frontend_feature` - Search for frontend features
6. `debug_arda_issue` - Debug-focused search strategy
7. `explore_architecture_layer` - Explore specific architectural layers
8. `find_api_endpoint` - Find API endpoint implementations
9. `trace_data_flow` - Trace data flow through the system
10. `find_test_coverage` - Find test coverage for features
11. `explore_deployment_config` - Explore deployment configurations
12. `audit_security_patterns` - Audit security implementations

## Available Resources (10)

1. `arda_collections_info` - Information about available collections
2. `arda_search_best_practices` - Best practices for semantic search
3. `collection_health_dashboard` - Collection health metrics
4. `api_endpoint_catalog` - Catalog of API endpoints
5. `code_patterns_library` - Common code patterns
6. `codebase_statistics` - Codebase statistics and metrics
7. `service_dependency_map` - Service dependency mappings
8. `changelog_resource` - Recent code changes and repository updates (NEW in v1.2.1)
9. `metrics_resource` - Performance metrics and operational insights (NEW in v1.2.1)
10. `architecture_resource` - System architecture with Mermaid diagrams (NEW in v1.2.1)

## Related Documentation

- **README.md** - User-facing documentation with feature overview
- **FastMCP Docs** - https://github.com/gofastmcp/fastmcp
- **Qdrant Docs** - https://qdrant.tech/documentation/
