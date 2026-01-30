#!/usr/bin/env python3
"""
Arda Vector Database MCP Server

FastMCP server providing semantic code search capabilities through Qdrant
vector database integration. Exposes i2p's vector search infrastructure
to Cursor IDE and other MCP-compatible AI coding assistants.

Features:
- Semantic code search across Rust, TypeScript, Solidity codebases
- Domain-specific prompts and resources for Arda Credit platform
- Smart query routing and caching
- Collection management and health monitoring

Architecture:
- Modular design with tools, prompts, and resources in separate modules
- Read-only vector database operations (no ingestion)
- 4096-dimensional embeddings (Qwen3-Embedding-8B)
- Cosine similarity search with 30-minute query caching
"""

import os
import sys
import logging
import httpx
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# FastMCP framework
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, ResourceError, NotFoundError

# Import Qdrant client
from qdrant_client import QdrantClient

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
SERVER_NAME = "arda-vector-db"
SERVER_VERSION = "1.2.0"
SERVER_DESCRIPTION = (
    "Semantic code search server for Arda Credit platform powered by Qdrant. "
    "Search across Rust, TypeScript, and Solidity codebases using "
    "natural language queries with domain-specific prompts and resources."
)

logger.info(f"🚀 Initializing {SERVER_NAME} v{SERVER_VERSION}")
logger.info(f"📝 {SERVER_DESCRIPTION}")

# Global state for sharing between modules (initialized in lifespan)
_qdrant_client: Optional[QdrantClient] = None
_embedding_endpoint: Optional[str] = None
_cloudflare_api_token: Optional[str] = None
_config: Optional[Dict[str, Any]] = None
_repo_cache: Dict[str, Any] = {}
_repo_cache_timestamp: Optional[float] = None
_repo_cache_ttl: int = 3600  # 1 hour cache TTL
_query_cache: QueryCache = QueryCache(ttl_minutes=30, max_size=1000)


# ============================================================================
# Helper Functions
# ============================================================================

async def warmup_embedding_endpoint(endpoint: str, cloudflare_token: str, deepinfra_key: str, model: str = 'custom-deepinfra/Qwen/Qwen2.5-7B-Instruct-Embedding', timeout: float = 30.0) -> bool:
    """
    Pre-warm the embedding endpoint to avoid cold start delays.

    This function sends a test query to wake up the endpoint before
    actual requests are made.

    Args:
        endpoint: Embedding endpoint base URL (Cloudflare AI gateway, e.g., https://gateway.ai.cloudflare.com/v1/{account_id}/aig/compat)
        api_token: Cloudflare API token for authentication
        timeout: Maximum time to wait for warmup (default: 30s)

    Returns:
        True if warmup successful, False otherwise
    """
    logger.info("🔥 Warming up embedding endpoint...")
    logger.info(f"   Endpoint: {endpoint[:60]}...")

    try:
        # Cloudflare AI Gateway requires both headers:
        # - Authorization: Provider API key (Deep Infra)
        # - cf-aig-authorization: Cloudflare Gateway token
        headers = {
            "Authorization": f"Bearer {deepinfra_key}",
            "cf-aig-authorization": f"Bearer {cloudflare_token}",
            "Content-Type": "application/json"
        }
        # Construct embeddings endpoint with custom provider path
        # Format: {base_url}/custom-deepinfra/embeddings
        # The base URL should be: https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}
        # So we append /custom-deepinfra/embeddings
        embeddings_url = f"{endpoint.rstrip('/')}/custom-deepinfra/embeddings"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                embeddings_url,
                json={
                    "model": model,
                    "input": ["warmup query"]
                },
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            # OpenAI-compatible API returns 'data' array with embeddings
            if 'data' in result and len(result['data']) > 0:
                embedding = result['data'][0].get('embedding', [])
                if len(embedding) > 0:
                    logger.info("✅ Embedding endpoint warmed up successfully")
                    return True
            logger.warning("⚠️  Embedding endpoint responded but format unexpected")
            return False

    except asyncio.TimeoutError:
        logger.warning(f"⚠️  Embedding endpoint warmup timed out after {timeout}s - endpoint may be cold")
        return False
    except httpx.HTTPError as e:
        logger.error(f"❌ Embedding endpoint warmup failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during embedding endpoint warmup: {e}")
        return False


# ============================================================================
# Server Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Server lifecycle management.

    Handles initialization and cleanup of resources:
    - Validates environment configuration
    - Initializes Qdrant client
    - Registers tools, prompts, and resources
    - Pre-warms embedding endpoint
    - Cleans up connections on shutdown
    """
    global _qdrant_client, _embedding_endpoint, _cloudflare_api_token, _config

    logger.info("=" * 80)
    logger.info(f"🚀 Starting {SERVER_NAME} v{SERVER_VERSION}")
    logger.info("=" * 80)

    try:
        # Validate environment configuration
        config = validate_environment()

        # Initialize Qdrant client
        qdrant_client = initialize_qdrant_client(config)

        # Store in global variables for modules to access
        _qdrant_client = qdrant_client
        _embedding_endpoint = config['embedding_endpoint']
        _cloudflare_api_token = config['cloudflare_api_token']
        _config = config

        # Register all tools, prompts, and resources from modules
        logger.info("📦 Registering MCP features from modules...")
        register_all_features()
        logger.info("✅ All features registered successfully")

        # Pre-warm embedding endpoint (runs in background)
        embedding_warmup_task = asyncio.create_task(
            warmup_embedding_endpoint(config['embedding_endpoint'], config['cloudflare_api_token'], config['deepinfra_api_key'], config['embedding_model'])
        )

        logger.info("=" * 80)
        logger.info("✅ Server initialization complete")
        logger.info(f"📡 {SERVER_NAME} is ready to accept MCP connections")
        logger.info("=" * 80)

        # Yield control to server
        yield {"qdrant_client": qdrant_client, "embedding_endpoint": config['embedding_endpoint']}

        # Wait for warmup task to complete before shutdown
        try:
            await asyncio.wait_for(embedding_warmup_task, timeout=35.0)
        except asyncio.TimeoutError:
            embedding_warmup_task.cancel()

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
        if _qdrant_client:
            logger.info("   Closing Qdrant connection...")
        logger.info("✅ Shutdown complete")


# Initialize FastMCP server with lifespan
mcp = FastMCP(SERVER_NAME, lifespan=lifespan)


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
    global _qdrant_client, _embedding_endpoint, _cloudflare_api_token, _query_cache
    global _repo_cache, _repo_cache_timestamp, _repo_cache_ttl

    # Import registration functions
    from src.prompts.prompts import register_prompts
    from src.resources.resources import register_resources, set_resource_dependencies
    from src.tools.collection import register_tools as register_collection_tools, set_collection_globals, _list_collections_impl
    from src.tools.search import register_tools as register_search_tools, set_search_globals, _semantic_search_impl
    from src.tools.domain import register_tools as register_domain_tools, set_domain_dependencies, _get_deployed_services_impl
    from src.tools.metadata import register_tools as register_metadata_tools, set_metadata_globals
    from src.tools.code_quality import register_tools as register_quality_tools, set_quality_globals
    from src.tools.analytics import register_tools as register_analytics_tools, set_analytics_globals
    from src.tracking.prompt_tracker import PromptUsageTracker

    # Set up global state in utils.github module
    from src.utils import github
    github._repo_cache = _repo_cache
    github._repo_cache_timestamp = _repo_cache_timestamp
    github._repo_cache_ttl = _repo_cache_ttl

    # Set up global state in collection tools
    set_collection_globals(
        _qdrant_client,
        _repo_cache,
        _repo_cache_timestamp,
        _repo_cache_ttl,
        SERVER_VERSION
    )

    # Set up global state in search tools
    set_search_globals(
        _qdrant_client,
        _embedding_endpoint,
        _cloudflare_api_token,
        _config.get('deepinfra_api_key'),
        _config.get('embedding_model', 'custom-deepinfra/Qwen/Qwen2.5-7B-Instruct-Embedding'),
        _query_cache
    )

    # Set up dependencies for domain tools
    set_domain_dependencies(
        _semantic_search_impl,
        _list_collections_impl
    )

    # Set up global state in code quality tools
    logger.info("   Setting up code quality analysis tools...")
    set_quality_globals(
        _semantic_search_impl,
        _list_collections_impl,
        _query_cache,
        _config.get('github_token')  # GHCR_TOKEN from environment
    )

    # Initialize prompt tracker for analytics
    _prompt_tracker = PromptUsageTracker()

    # Set up global state in analytics tools
    logger.info("   Setting up dashboard analytics tools...")
    set_analytics_globals(
        _semantic_search_impl,
        _qdrant_client,
        _query_cache,
        _prompt_tracker
    )

    # Set up dependencies for resources
    # Get resource functions from resources module for metadata tools
    from src.resources.resources import (
        arda_collections_info,
        arda_search_best_practices,
        collection_health_dashboard,
        api_endpoint_catalog,
        code_patterns_library,
        codebase_statistics,
        service_dependency_map,
        changelog_resource,
        metrics_resource,
        architecture_resource
    )

    # We need to register resources first so we can get the functions
    register_resources(mcp)

    # After resources are registered, set up their dependencies
    set_resource_dependencies(
        _list_collections_impl,
        _semantic_search_impl,
        _get_deployed_services_impl,
        _query_cache
    )

    # Build resource map for metadata tools
    resource_map = {
        "arda://collections": arda_collections_info,
        "arda://search-tips": arda_search_best_practices,
        "arda://dashboard": collection_health_dashboard,
        "arda://api-catalog": api_endpoint_catalog,
        "arda://patterns": code_patterns_library,
        "arda://stats": codebase_statistics,
        "arda://dependencies": service_dependency_map,
        "arda://changelog": changelog_resource,
        "arda://metrics": metrics_resource,
        "arda://architecture": architecture_resource
    }

    # Get prompt functions from prompts module
    from src.prompts.prompts import (
        search_deal_operations,
        search_zkproof_implementation,
        search_authentication_system,
        search_usdc_integration,
        search_frontend_feature,
        debug_arda_issue,
        explore_architecture_layer,
        find_api_endpoint,
        trace_data_flow,
        find_test_coverage,
        explore_deployment_config,
        audit_security_patterns
    )

    # Register prompts
    register_prompts(mcp)

    # Build prompt map for metadata tools
    prompt_map = {
        "search_deal_operations": search_deal_operations,
        "search_zkproof_implementation": search_zkproof_implementation,
        "search_authentication_system": search_authentication_system,
        "search_usdc_integration": search_usdc_integration,
        "search_frontend_feature": search_frontend_feature,
        "debug_arda_issue": debug_arda_issue,
        "explore_architecture_layer": explore_architecture_layer,
        "find_api_endpoint": find_api_endpoint,
        "trace_data_flow": trace_data_flow,
        "find_test_coverage": find_test_coverage,
        "explore_deployment_config": explore_deployment_config,
        "audit_security_patterns": audit_security_patterns
    }

    # Set up global state in metadata tools
    set_metadata_globals(
        SERVER_NAME,
        resource_map,
        prompt_map,
        _semantic_search_impl
    )

    # Register all tools
    register_collection_tools(mcp)
    register_search_tools(mcp)
    register_domain_tools(mcp)
    register_metadata_tools(mcp)
    register_quality_tools(mcp)
    register_analytics_tools(mcp)

    logger.info(f"   ✓ Registered 30 tools across 6 modules")
    logger.info(f"   ✓ Registered 12 prompts")
    logger.info(f"   ✓ Registered 10 resources")


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
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    embedding_endpoint = os.getenv('EMBEDDING_ENDPOINT')
    cloudflare_api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    deepinfra_api_key = os.getenv('DEEPINFRA_API_KEY')  # Provider API key for Deep Infra
    embedding_model = os.getenv('EMBEDDING_MODEL', 'custom-deepinfra/Qwen/Qwen2.5-7B-Instruct-Embedding')

    if not qdrant_url:
        raise ValueError(
            "QDRANT_URL environment variable is required. "
            "Please set it in .env file or environment."
        )

    if not qdrant_api_key:
        raise ValueError(
            "QDRANT_API_KEY environment variable is required. "
            "Please set it in .env file or environment."
        )

    # Default embedding endpoint if not provided
    # Note: Should be full base URL like https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}
    # The /custom-deepinfra/embeddings path will be appended automatically
    if not embedding_endpoint:
        raise ValueError(
            "EMBEDDING_ENDPOINT environment variable is required. "
            "Format: https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}"
        )

    if not cloudflare_api_token:
        raise ValueError(
            "CLOUDFLARE_API_TOKEN environment variable is required for embedding generation. "
            "Please set it in .env file or environment."
        )

    if not deepinfra_api_key:
        raise ValueError(
            "DEEPINFRA_API_KEY environment variable is required for embedding generation. "
            "This is the provider API key for Deep Infra. Please set it in .env file or environment."
        )

    config = {
        'qdrant_url': qdrant_url,
        'qdrant_api_key': qdrant_api_key,
        'embedding_endpoint': embedding_endpoint,
        'cloudflare_api_token': cloudflare_api_token,
        'deepinfra_api_key': deepinfra_api_key,
        'embedding_model': embedding_model,
    }

    logger.info(f"✅ Environment validation successful")
    logger.info(f"   Qdrant URL: {qdrant_url[:60]}...")
    logger.info(f"   Embedding Endpoint: {embedding_endpoint[:60]}...")
    logger.info(f"   Cloudflare API Token: {'*' * 20}...{cloudflare_api_token[-4:] if len(cloudflare_api_token) > 4 else '****'}")
    logger.info(f"   Deep Infra API Key: {'*' * 20}...{deepinfra_api_key[-4:] if len(deepinfra_api_key) > 4 else '****'}")
    logger.info(f"   Embedding Model: {embedding_model}")

    return config


def initialize_qdrant_client(config: Dict[str, Any]) -> QdrantClient:
    """
    Initialize Qdrant client with configuration and validate connection.

    Args:
        config: Configuration dictionary from validate_environment()

    Returns:
        Initialized QdrantClient

    Raises:
        RuntimeError: If connection fails or collections are missing
        Exception: For other unexpected errors
    """
    try:
        logger.info("🔗 Connecting to Qdrant...")

        client = QdrantClient(
            url=config['qdrant_url'],
            api_key=config['qdrant_api_key'],
            timeout=60
        )

        # Test connection by listing collections
        collections = client.get_collections()
        collection_count = len(collections.collections)

        if collection_count == 0:
            raise RuntimeError(
                "No collections found in Qdrant database. "
                "Please ensure the vector database has been populated with data."
            )

        logger.info(f"✅ Connected to Qdrant - Found {collection_count} collections")
        for collection in collections.collections:
            logger.info(f"   📦 {collection.name}")

        # Validate expected collections exist
        expected_collections = ['arda_code_rust', 'arda_code_typescript', 'arda_code_solidity', 'arda_documentation']
        existing_names = [c.name for c in collections.collections]
        missing = [name for name in expected_collections if name not in existing_names]

        if missing:
            logger.warning(f"⚠️  Some expected collections are missing: {', '.join(missing)}")
            logger.warning("   Vector search may have limited functionality")

        return client

    except RuntimeError:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to connect to Qdrant: {e}")
        logger.error("💡 Please check:")
        logger.error("   - QDRANT_URL is accessible from your network")
        logger.error("   - QDRANT_API_KEY is valid and has proper permissions")
        logger.error("   - Qdrant service is running and healthy")
        logger.exception("Stack trace:")
        raise RuntimeError(f"Qdrant connection failed: {e}") from e


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for the MCP server.

    The lifespan context manager handles initialization and cleanup.
    This function just starts the server.
    """
    # Start FastMCP server (lifespan handles initialization)
    mcp.run()


if __name__ == "__main__":
    main()
