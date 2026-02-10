#!/usr/bin/env python3
"""
Code Ingestion MCP Server

FastMCP server providing semantic code search capabilities through SurrealDB
vector database integration. Enables semantic search over ingested code
repositories for Cursor IDE and other MCP-compatible AI coding assistants.

Features:
- Semantic code search across multiple programming languages
- Config-driven collection naming (from config/collections.yaml)
- Smart query routing and caching
- Collection management and health monitoring

Architecture:
- Modular design with tools and resources in separate modules
- Read-only vector database operations (no ingestion)
- 4096-dimensional embeddings (Qwen3-Embedding-8B)
- Cosine similarity search with 30-minute query caching
"""

import os
import sys
import time
import logging
import httpx
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# FastMCP framework
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, ResourceError, NotFoundError
from starlette.responses import JSONResponse

# Import vector backend abstraction
import sys
import os
# Add parent directory to path to import from modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ingest.core.vector_backend import create_vector_backend, VectorBackend

# Import cache module
from src.cache import QueryCache

# Setup logging
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Server metadata
SERVER_NAME = "code-ingest-mcp"
SERVER_VERSION = "2.0.0"
SERVER_DESCRIPTION = (
    "Semantic code search server for ingested repositories via SurrealDB. "
    "Search across code collections using natural language queries."
)

logger.info(f"🚀 Initializing {SERVER_NAME} v{SERVER_VERSION}")
logger.info(f"📝 {SERVER_DESCRIPTION}")

# Global state for sharing between modules (initialized in lifespan)
_vector_client: Optional[VectorBackend] = None
_embedding_endpoint: Optional[str] = None
_cloudflare_api_token: Optional[str] = None
_config: Optional[Dict[str, Any]] = None
_repo_cache: Dict[str, Any] = {}
_repo_cache_timestamp: Optional[float] = None
_repo_cache_ttl: int = 3600  # 1 hour cache TTL
_query_cache: QueryCache = QueryCache(ttl_minutes=30, max_size=1000)


# ============================================================================
# Server Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Server lifecycle management.

    Handles initialization and cleanup of resources:
    - Validates environment configuration
    - Initializes SurrealDB vector backend
    - Registers tools, prompts, and resources
    - Cleans up connections on shutdown
    """
    global _vector_client, _embedding_endpoint, _cloudflare_api_token, _config

    logger.info("=" * 80)
    logger.info(f"🚀 Starting {SERVER_NAME} v{SERVER_VERSION}")
    logger.info("=" * 80)

    try:
        # Validate environment configuration
        config = validate_environment()

        # Initialize vector backend
        vector_client = initialize_vector_backend(config)

        # Store in global variables for modules to access
        _vector_client = vector_client
        _config = config

        # Register all tools, prompts, and resources from modules
        logger.info("📦 Registering MCP features from modules...")
        register_all_features()
        logger.info("✅ All features registered successfully")

        logger.info("=" * 80)
        logger.info("✅ Server initialization complete")
        logger.info(f"📡 {SERVER_NAME} is ready to accept MCP connections")
        logger.info("=" * 80)

        # Start health endpoint server only when NOT using HTTP transport (stdio + separate health server)
        use_http_transport = os.getenv('MCP_HTTP_TRANSPORT', '').lower() == 'true'
        health_server = None
        if (os.getenv('DOCKER_ENV') == 'true' or os.getenv('ENABLE_HEALTH_ENDPOINT') == 'true') and not use_http_transport:
            try:
                from health_server import start_health_server
                health_port = int(os.getenv('HEALTH_PORT', '8001'))
                start_health_server(port=health_port)
                logger.info(f"🏥 Health endpoint available at http://0.0.0.0:{health_port}/health")
            except Exception as e:
                logger.warning(f"⚠️  Failed to start health endpoint: {e}")

        # Yield control to server
        yield {"vector_client": vector_client, "embedding_endpoint": config['embedding_endpoint']}

    except ValueError as e:
        logger.error("=" * 80)
        logger.error(f"❌ Configuration Error: {e}")
        logger.error("=" * 80)
        sys.exit(1)

    except RuntimeError as e:
        logger.error("=" * 80)
        logger.error(f"❌ Runtime Error: {e}")
        logger.error("=" * 80)
        sys.exit(1)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Server initialization failed: {e}")
        logger.exception("Stack trace:")
        logger.error("=" * 80)
        sys.exit(1)

    finally:
        # Cleanup on shutdown
        logger.info("🛑 Shutting down server...")
        if _vector_client:
            logger.info("   Closing vector backend connection...")
        logger.info("✅ Shutdown complete")


# Initialize FastMCP server with lifespan
mcp = FastMCP(SERVER_NAME, lifespan=lifespan)


def _register_health_route():
    """Register /health route for HTTP transport (Docker). Uses FastMCP custom_route if available."""
    if not hasattr(mcp, 'custom_route'):
        return
    try:
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from health_server import get_health_status
        import asyncio

        @mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request):
            # get_health_status() is sync (urllib, file I/O); run in thread to avoid blocking
            loop = asyncio.get_event_loop()
            response_dict, status_code = await loop.run_in_executor(None, get_health_status)
            return JSONResponse(response_dict, status_code=status_code)
    except Exception as e:
        logger.warning("Could not register /health custom route: %s", e)


def _register_debug_route():
    """Register /debug/collections route for HTTP transport. Shows what collections MCP sees."""
    if not hasattr(mcp, 'custom_route'):
        return
    try:
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        @mcp.custom_route("/debug/collections", methods=["GET"])
        async def debug_collections(request: Request):
            """Return list of collections and counts from the vector client.
            Add ?raw=1 to include raw INFO FOR DB result (for debugging parsing)."""
            global _vector_client
            if not _vector_client:
                return JSONResponse(
                    {"error": "Vector client not initialized", "collections": [], "count": 0},
                    status_code=503,
                )
            try:
                raw_param = request.query_params.get("raw", "").lower() in ("1", "true", "yes")
                names = _vector_client.get_collections()
                details = []
                for name in names:
                    info = _vector_client.get_collection_info(name)
                    points = 0
                    if info:
                        points = info.get("vectors_count", info.get("points_count", 0))
                    details.append({"name": name, "points": points})
                body = {"collections": details, "count": len(names), "backend": "surrealdb"}
                if raw_param and hasattr(_vector_client, "client"):
                    try:
                        body["_client_url"] = getattr(_vector_client, "url", None)
                        body["_client_namespace"] = getattr(_vector_client, "namespace", None)
                        body["_client_database"] = getattr(_vector_client, "database", None)
                        raw_result = _vector_client.client.query("INFO FOR DB;")
                        body["_raw_info_type"] = type(raw_result).__name__
                        if isinstance(raw_result, dict):
                            body["_raw_info_keys"] = list(raw_result.keys())
                            if "tables" in raw_result:
                                tbls = raw_result["tables"]
                                body["_raw_tables_type"] = type(tbls).__name__
                                if isinstance(tbls, dict):
                                    body["_raw_tables_keys"] = list(tbls.keys())[:20]
                                elif isinstance(tbls, (list, tuple)):
                                    body["_raw_tables_len"] = len(tbls)
                                    body["_raw_tables_sample"] = list(tbls)[:5] if tbls else []
                                elif tbls is not None:
                                    body["_raw_tables_repr"] = str(tbls)[:200]
                        elif isinstance(raw_result, (list, tuple)):
                            body["_raw_info_len"] = len(raw_result)
                            if len(raw_result) > 0:
                                body["_raw_first_type"] = type(raw_result[0]).__name__
                                if isinstance(raw_result[0], dict):
                                    body["_raw_first_keys"] = list(raw_result[0].keys())
                    except Exception as raw_err:
                        body["_raw_error"] = str(raw_err)
                return JSONResponse(body)
            except Exception as e:
                return JSONResponse(
                    {"error": str(e), "collections": [], "count": 0},
                    status_code=500,
                )
    except Exception as e:
        logger.warning("Could not register /debug/collections custom route: %s", e)


# ============================================================================
# Module Registration
# ============================================================================

def register_all_features():
    """
    Register all tools, prompts, and resources from modular files.

    This function:
    1. Sets up global state in each module
    2. Calls registration functions to add features to the MCP server
    3. Sets up cross-module dependencies
    """
    global _vector_client, _query_cache, _config
    global _repo_cache, _repo_cache_timestamp, _repo_cache_ttl

    # Import minimal registration functions
    from src.resources.resources import register_resources, set_resource_dependencies
    from src.tools.collection import register_tools as register_collection_tools, set_collection_globals, _list_collections_impl
    from src.tools.search import register_tools as register_search_tools, set_search_globals

    # Set up global state in collection tools
    set_collection_globals(
        _vector_client,
        _repo_cache,
        _repo_cache_timestamp,
        _repo_cache_ttl,
        SERVER_VERSION
    )

    # Set up global state in search tools
    set_search_globals(
        _vector_client,
        _config.get('deepinfra_api_key'),
        _config.get('embedding_base_url', 'https://api.deepinfra.com/v1/openai'),
        _config.get('embedding_model', 'Qwen/Qwen3-Embedding-8B'),
        _query_cache
    )

    # Register resources first
    register_resources(mcp)

    # Set up resource dependencies
    set_resource_dependencies(
        _list_collections_impl,
        _query_cache
    )

    # Register minimal tool set (collection + search)
    register_collection_tools(mcp)
    register_search_tools(mcp)

    logger.info(f"   ✓ Registered 4 core tools (list_collections, get_collection_info, semantic_search, multi_search)")
    logger.info(f"   ✓ Registered 2 resources (vector://collections, vector://search-tips)")


# ============================================================================
# Environment and Client Initialization
# ============================================================================

def validate_environment() -> Dict[str, Any]:
    """
    Validate required environment variables.

    Returns:
        Dictionary with validation results and configuration

    Raises:
        ValueError: If required environment variables are missing
    """
    logger.info("🔍 Validating environment configuration...")

    # Required environment variables
    surrealdb_url = os.getenv('SURREALDB_URL')
    deepinfra_api_key = os.getenv('DEEPINFRA_API_KEY')
    
    # Optional: embedding endpoint override (defaults to DeepInfra)
    embedding_base_url = os.getenv('EMBEDDING_ENDPOINT', 'https://api.deepinfra.com/v1/openai')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'Qwen/Qwen3-Embedding-8B')

    if not surrealdb_url:
        raise ValueError(
            "SURREALDB_URL environment variable is required. "
            "Please set it in .env file or environment."
        )

    if not deepinfra_api_key:
        raise ValueError(
            "DEEPINFRA_API_KEY environment variable is required for embedding generation. "
            "Get your API key from: https://deepinfra.com/dash/api_keys"
        )

    config = {
        'surrealdb_url': surrealdb_url,
        'deepinfra_api_key': deepinfra_api_key,
        'embedding_base_url': embedding_base_url,
        'embedding_endpoint': embedding_base_url,  # alias used by lifespan yield
        'embedding_model': embedding_model,
    }

    logger.info(f"✅ Environment validation successful")
    logger.info(f"   SurrealDB URL: {surrealdb_url[:60]}...")
    logger.info(f"   Embedding Base URL: {embedding_base_url}")
    logger.info(f"   DeepInfra API Key: {'*' * 20}...{deepinfra_api_key[-4:] if len(deepinfra_api_key) > 4 else '****'}")
    logger.info(f"   Embedding Model: {embedding_model}")

    return config


def initialize_vector_backend(config: Dict[str, Any]) -> VectorBackend:
    """
    Initialize SurrealDB vector backend with configuration and validate connection.

    Args:
        config: Configuration dictionary from validate_environment()

    Returns:
        Initialized VectorBackend

    Raises:
        RuntimeError: If connection fails or collections are missing
        Exception: For other unexpected errors
    """
    try:
        logger.info("🔗 Connecting to SurrealDB vector backend...")

        client = create_vector_backend()

        # Test connection by listing collections
        collections = client.get_collections()
        collection_count = len(collections)

        if collection_count == 0:
            logger.warning(
                "⚠️  No collections found in vector database. "
                "Vector search will not work until ingestion is complete."
            )

        logger.info(f"✅ Connected to SurrealDB - Found {collection_count} collections")
        for collection_name in collections:
            logger.info(f"   📦 {collection_name}")

        # No specific collection validation - MCP works with any collections present
        logger.info(f"   MCP server ready to search {collection_count} collections")

        return client

    except RuntimeError:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to connect to SurrealDB: {e}")
        logger.error("💡 Please check:")
        logger.error("   - SURREALDB_URL is accessible (e.g., http://localhost:8000 or remote URL)")
        logger.error("   - SurrealDB service is running and healthy")
        logger.error("   - SURREALDB_NS, SURREALDB_DB are set correctly")
        logger.exception("Stack trace:")
        raise RuntimeError(f"SurrealDB connection failed: {e}") from e


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for the MCP server.

    The lifespan context manager handles initialization and cleanup.
    When MCP_HTTP_TRANSPORT=true (e.g. in Docker), runs with HTTP transport
    on HEALTH_PORT so Cursor can connect via http://localhost:8001/mcp
    and /health remains available on the same port.
    """
    use_http = os.getenv('MCP_HTTP_TRANSPORT', '').lower() == 'true'
    health_port = int(os.getenv('HEALTH_PORT', '8001'))

    if use_http:
        _register_health_route()
        _register_debug_route()
        logger.info(f"📡 MCP HTTP transport: http://0.0.0.0:{health_port}/mcp (Cursor: http://localhost:{health_port}/mcp)")
        mcp.run(transport="http", host="0.0.0.0", port=health_port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
