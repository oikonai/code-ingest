"""
MCP Resources - Generic Vector Search Resources

Provides minimal generic resources for code search:
- vector://collections - List available collections
- vector://search-tips - Search best practices
"""

import logging
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Global dependencies (set by server module)
_list_collections_impl = None
_query_cache = None


def set_resource_dependencies(list_collections_fn, query_cache):
    """
    Set function dependencies needed by resources.
    
    Args:
        list_collections_fn: Function to list collections
        query_cache: Query cache instance
    """
    global _list_collections_impl, _query_cache
    _list_collections_impl = list_collections_fn
    _query_cache = query_cache


async def collections_info() -> str:
    """
    Information about available vector collections.
    
    Dynamic resource that lists collections from Qdrant + schema.
    """
    try:
        # Get collections from Qdrant via list_collections
        if not _list_collections_impl:
            return "# Vector Collections\n\n⚠️ Unable to list collections (not initialized)"
        
        collections_data = _list_collections_impl()
        
        output = "# Vector Collections\n\n"
        output += "Available collections in the vector database:\n\n"
        
        # Group by type
        by_type = collections_data.get('collections_by_type', {})
        
        # Language collections
        if by_type.get('language'):
            output += "## Language Collections\n\n"
            for coll in by_type['language']:
                output += f"### {coll['name']}\n"
                if 'description' in coll:
                    output += f"{coll['description']}\n\n"
                output += f"- Points: {coll.get('points_count', 'N/A')}\n"
                output += f"- Status: {coll.get('status', 'N/A')}\n\n"
        
        # Service collections
        if by_type.get('service'):
            output += "## Service Collections\n\n"
            for coll in by_type['service']:
                output += f"### {coll['name']}\n"
                if 'description' in coll:
                    output += f"{coll['description']}\n\n"
                output += f"- Points: {coll.get('points_count', 'N/A')}\n\n"
        
        # Concern collections
        if by_type.get('concern'):
            output += "## Concern Collections\n\n"
            for coll in by_type['concern']:
                output += f"### {coll['name']}\n"
                if 'description' in coll:
                    output += f"{coll['description']}\n\n"
                output += f"- Points: {coll.get('points_count', 'N/A')}\n\n"
        
        # Unknown collections (discovered from Qdrant)
        if by_type.get('unknown'):
            output += "## Other Collections\n\n"
            for coll in by_type['unknown']:
                output += f"### {coll['name']}\n"
                output += f"- Points: {coll.get('points_count', 'N/A')}\n\n"
        
        # Summary
        total = collections_data.get('count', 0)
        output += f"\n---\n\nTotal collections: {total}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate collections resource: {e}")
        return f"# Vector Collections\n\n❌ Error: {e}"


async def search_tips() -> str:
    """
    Best practices for semantic search across code collections.
    
    Generic tips on how to formulate queries and use search parameters.
    """
    return """# Vector Search Tips

## Query Formulation

**Natural language queries work best:**
- Good: "authentication logic for user login"
- Good: "error handling in API requests"
- Good: "database connection pooling"
- Avoid: single words like "auth" or "db"

**Be specific about what you're looking for:**
- "Where are JWT tokens validated?" > "JWT"
- "How do we handle payment failures?" > "payment"
- "What's the retry logic for failed requests?" > "retry"

## Search Parameters

### limit (default: 20)
- Number of results to return (1-50)
- Higher limit = more context but slower
- Start with 10-20 for focused queries
- Use 30-50 for broad exploratory searches

### score_threshold (default: 0.5)
- Minimum similarity score (0.0-1.0)
- Lower threshold = more results, less relevant
- Higher threshold = fewer results, more relevant
- Recommended: 0.4-0.6 for most queries
- Use 0.3 for fuzzy/exploratory searches
- Use 0.7+ for exact semantic matches

### collection_name
- Target a specific collection for faster, focused results
- Use language collections (e.g., "rust", "typescript") when you know the language
- Use multi_search for cross-collection searches

## Multi-Collection Search

When searching across multiple collections:
1. Results are grouped by collection
2. Each collection can have different limits/thresholds
3. Use when you don't know where code is located
4. More expensive than single-collection search

## Query Cache

- Identical queries (same params) are cached for 30 minutes
- Cache is per-collection and parameter set
- Use exact same query text for cache hits

## Examples

```
# Focused single-collection search
semantic_search(
    query="user authentication with JWT",
    collection_name="rust",
    limit=15,
    score_threshold=0.6
)

# Broad multi-collection search
multi_search(
    query="error handling patterns",
    collections=["rust", "typescript"],
    limit=20,
    score_threshold=0.4
)

# Exploratory search
semantic_search(
    query="how do we process payments",
    collection_name="backend",
    limit=30,
    score_threshold=0.3
)
```
"""


def register_resources(mcp: FastMCP):
    """
    Register generic MCP resources for vector search.
    
    Args:
        mcp: FastMCP instance
    """
    # Register collections info resource
    @mcp.resource("vector://collections")
    async def collections_resource() -> str:
        """List available vector collections with metadata."""
        return await collections_info()
    
    # Register search tips resource
    @mcp.resource("vector://search-tips")
    async def search_tips_resource() -> str:
        """Best practices for semantic code search."""
        return await search_tips()
    
    logger.info("✅ Registered 2 generic resources (vector://collections, vector://search-tips)")
