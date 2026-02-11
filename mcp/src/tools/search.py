"""MCP tools for semantic code search."""

import logging
import httpx
from typing import List, Optional, Dict
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, NotFoundError

from ..collections import DEFAULT_COLLECTION, resolve_collection_name

logger = logging.getLogger(__name__)

# Global state - will be set by server module
_vector_client = None
_embedding_endpoint = None
_cloudflare_api_token = None
_deepinfra_api_key = None
_embedding_model = None
_query_cache = None


def set_search_globals(vector_client, embedding_endpoint, cloudflare_api_token, deepinfra_api_key, embedding_model, query_cache):
    """
    Set global state references needed by search tools.

    Args:
        vector_client: Vector backend client instance
        embedding_endpoint: Embedding service URL (Cloudflare AI gateway)
        cloudflare_api_token: Cloudflare API token for authentication
        deepinfra_api_key: Deep Infra provider API key
        embedding_model: Model name for embeddings
        query_cache: Query cache instance
    """
    global _vector_client, _embedding_endpoint, _cloudflare_api_token, _deepinfra_api_key, _embedding_model, _query_cache
    _vector_client = vector_client
    _embedding_endpoint = embedding_endpoint
    _cloudflare_api_token = cloudflare_api_token
    _deepinfra_api_key = deepinfra_api_key
    _embedding_model = embedding_model
    _query_cache = query_cache


async def _semantic_search_impl(
    query: str,
    collection_name: str = None,
    limit: int = 20,
    score_threshold: float = 0.5
) -> dict:
    """
    Internal implementation of semantic search (not decorated with @mcp.tool).
    This can be called from other tools without triggering the FunctionTool error.

    Args:
        query: Natural language search query (e.g., "authentication logic", "error handling")
        collection_name: Target collection (uses default from config if not specified)
        limit: Maximum number of results to return (1-50, default: 20)
        score_threshold: Minimum similarity score (0.0-1.0, default: 0.5)

    Returns:
        Dictionary with search results containing code snippets, scores, and metadata

    Raises:
        ToolError: If search fails or embedding generation fails
        NotFoundError: If collection doesn't exist
    """
    # Use default collection if not specified
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    try:
        global _vector_client, _embedding_endpoint, _cloudflare_api_token, _query_cache

        if not _vector_client:
            raise ToolError("Vector client not initialized")

        if not _embedding_endpoint:
            raise ToolError("Embedding endpoint not configured")

        if not _cloudflare_api_token:
            raise ToolError("Cloudflare API token not configured")

        if not _deepinfra_api_key:
            raise ToolError("Deep Infra API key not configured")

        # Validate parameters
        if not query or not query.strip():
            raise ToolError("Query cannot be empty")

        if limit < 1 or limit > 50:
            raise ToolError("Limit must be between 1 and 50")

        if score_threshold < 0.0 or score_threshold > 1.0:
            raise ToolError("Score threshold must be between 0.0 and 1.0")

        logger.info(f"🔍 Semantic search: '{query}' in {collection_name} (limit={limit}, threshold={score_threshold})")

        # Check cache first
        cache_params = {"limit": limit, "score_threshold": score_threshold}
        cached_result = _query_cache.get(query, collection_name, cache_params)

        if cached_result:
            logger.info("   ⚡ Returned from cache")
            cached_result["from_cache"] = True
            return cached_result

        # Generate embedding via embedding endpoint
        try:
            # Cloudflare AI Gateway requires both headers:
            # - Authorization: Provider API key (Deep Infra)
            # - cf-aig-authorization: Cloudflare Gateway token
            headers = {
                "Authorization": f"Bearer {_deepinfra_api_key}",
                "cf-aig-authorization": f"Bearer {_cloudflare_api_token}",
                "Content-Type": "application/json"
            }
            # Construct embeddings endpoint with custom provider path
            # Format: {base_url}/custom-deepinfra/embeddings
            # The base URL should be: https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}
            # So we append /custom-deepinfra/embeddings
            embeddings_url = f"{_embedding_endpoint.rstrip('/')}/custom-deepinfra/embeddings"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Keep the full model name with prefix - Cloudflare Gateway needs it to route to the provider
                request_payload = {
                    "model": _embedding_model,
                    "input": [query]
                }

                response = await client.post(
                    embeddings_url,
                    json=request_payload,
                    headers=headers
                )
                response.raise_for_status()
                embedding_data = response.json()

                if 'error' in embedding_data:
                    error_msg = embedding_data.get('error', {})
                    if isinstance(error_msg, list) and len(error_msg) > 0:
                        error_detail = error_msg[0]
                        error_code = error_detail.get('code', '')
                        error_message = error_detail.get('message', str(error_detail))
                        if error_code == 2005:  # Failed to get response from provider
                            raise ToolError(
                                f"Embedding endpoint error: {error_message}. "
                                f"This usually means the model '{_embedding_model}' doesn't support embeddings or the model name is incorrect. "
                                f"Please verify the EMBEDDING_MODEL environment variable matches a valid embedding model in your Cloudflare AI Gateway."
                            )
                        raise ToolError(f"Embedding endpoint error (code {error_code}): {error_message}")
                    raise ToolError(f"Embedding endpoint error: {error_msg}")

                # OpenAI-compatible API returns 'data' array with embeddings
                if 'data' not in embedding_data or not embedding_data['data']:
                    raise ToolError("Embedding endpoint returned invalid response (missing 'data' field)")

                query_embedding = embedding_data['data'][0].get('embedding', [])

                if not isinstance(query_embedding, list) or len(query_embedding) != 4096:
                    raise ToolError(f"Invalid embedding dimensions: expected 4096, got {len(query_embedding) if isinstance(query_embedding, list) else 'non-list'}")

        except httpx.HTTPError as e:
            logger.error(f"Embedding request failed: {e}")
            raise ToolError(f"Failed to generate query embedding: {str(e)}") from e

        # Search vector collection
        try:
            search_results = _vector_client.search_vectors(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions=None
            )
        except Exception as e:
            if 'not found' in str(e).lower() or 'does not exist' in str(e).lower():
                raise NotFoundError(f"Collection '{collection_name}' not found") from e
            raise ToolError(f"Vector search failed: {str(e)}") from e

        # Results are already formatted by the backend
        results = search_results

        logger.info(f"✅ Found {len(results)} results")

        result_dict = {
            'query': query,
            'collection': collection_name,
            'results_count': len(results),
            'results': results,
            'parameters': {
                'limit': limit,
                'score_threshold': score_threshold
            },
            'from_cache': False
        }

        # Cache the result
        _query_cache.set(query, collection_name, cache_params, result_dict)

        return result_dict

    except (ToolError, NotFoundError):
        raise

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise ToolError(f"Semantic search failed: {str(e)}") from e


def register_tools(mcp: FastMCP):
    """Register all search tools with the MCP server."""

    @mcp.tool()
    async def semantic_search(
        query: str,
        collection_name: str = None,
        limit: int = 20,
        score_threshold: float = 0.5
    ) -> dict:
        """
        Perform semantic search across code embeddings using natural language query.

        Args:
            query: Natural language search query (e.g., "authentication logic", "error handling")
            collection_name: Target collection (or alias like "rust", "typescript"). Uses default if not specified.
            limit: Maximum number of results to return (1-50, default: 20)
            score_threshold: Minimum similarity score (0.0-1.0, default: 0.5)

        Returns:
            Dictionary with search results containing code snippets, scores, and metadata

        Raises:
            ToolError: If search fails or embedding generation fails
            NotFoundError: If collection doesn't exist
        """
        # Resolve collection name or use default
        if collection_name is None:
            collection_name = DEFAULT_COLLECTION
        else:
            collection_name = resolve_collection_name(collection_name)
        
        return await _semantic_search_impl(query, collection_name, limit, score_threshold)


    @mcp.tool()
    async def batch_semantic_search(
        queries: List[str],
        collection_name: str = None,
        limit_per_query: int = 10,
        score_threshold: float = 0.6
    ) -> dict:
        """
        Perform multiple semantic searches efficiently to get comprehensive context.

        Useful for exploring related aspects of a feature or building comprehensive understanding
        across multiple queries. Maximum 10 queries per batch.

        Args:
            queries: List of search queries (max 10)
            collection_name: Target collection (default: from config or first collection)
            limit_per_query: Results per query (1-20, default: 10)
            score_threshold: Minimum similarity (0.0-1.0, default: 0.6)

        Returns:
            Dictionary with results for each query and aggregate statistics

        Raises:
            ToolError: If parameters are invalid or search fails
        """
        if len(queries) > 10:
            raise ToolError("Maximum 10 queries per batch")

        if len(queries) == 0:
            raise ToolError("At least one query required")

        if limit_per_query < 1 or limit_per_query > 20:
            raise ToolError("limit_per_query must be between 1 and 20")

        logger.info(f"🔍 Batch search: {len(queries)} queries in {collection_name}")

        results = {}
        total_results = 0

        for query in queries:
            try:
                result = await _semantic_search_impl(
                    query=query,
                    collection_name=collection_name,
                    limit=limit_per_query,
                    score_threshold=score_threshold
                )
                results[query] = result
                total_results += result.get('results_count', 0)
            except Exception as e:
                results[query] = {'error': str(e), 'results_count': 0}

        return {
            'batch_size': len(queries),
            'collection': collection_name,
            'total_results': total_results,
            'queries': results
        }


    @mcp.tool()
    async def cross_collection_search(
        query: str,
        collections: List[str] = None,
        limit_per_collection: int = 10,
        score_threshold: float = 0.6
    ) -> dict:
        """
        Search across multiple collections for full-stack feature exploration.

        Useful for understanding how a feature is implemented across the entire stack
        (backend, frontend, smart contracts, documentation).

        Args:
            query: Natural language search query
            collections: List of collections to search (default: all configured code collections)
            limit_per_collection: Results per collection (1-20, default: 10)
            score_threshold: Minimum similarity (0.0-1.0, default: 0.6)

        Returns:
            Dictionary with results grouped by collection

        Raises:
            ToolError: If parameters are invalid or search fails
        """
        # Validate parameters
        if not query or not query.strip():
            raise ToolError("Query cannot be empty")

        if collections is None:
            # Import here to avoid circular dependency
            from ..collections import DEFAULT_CODE_COLLECTIONS
            collections = DEFAULT_CODE_COLLECTIONS[:3]  # Use first 3 language collections

        # Validate collections list
        if not isinstance(collections, list):
            raise ToolError("Collections must be a list")

        if len(collections) == 0:
            raise ToolError("At least one collection must be specified")

        if len(collections) > 5:
            raise ToolError("Maximum 5 collections per search")

        if limit_per_collection < 1 or limit_per_collection > 20:
            raise ToolError("limit_per_collection must be between 1 and 20")

        if score_threshold < 0.0 or score_threshold > 1.0:
            raise ToolError("score_threshold must be between 0.0 and 1.0")

        logger.info(f"🔍 Cross-collection search: '{query}' across {len(collections)} collections")
        logger.debug(f"   Collections: {', '.join(collections)}")
        logger.debug(f"   Limit per collection: {limit_per_collection}, Threshold: {score_threshold}")

        results = {}
        total_results = 0
        successful_searches = 0
        failed_searches = 0

        for collection in collections:
            try:
                # Make sure to await the async function
                result = await _semantic_search_impl(
                    query=query,
                    collection_name=collection,
                    limit=limit_per_collection,
                    score_threshold=score_threshold
                )
                results[collection] = result
                total_results += result.get('results_count', 0)
                successful_searches += 1
                logger.debug(f"   ✓ {collection}: {result.get('results_count', 0)} results")
            except NotFoundError as e:
                # Collection doesn't exist
                logger.warning(f"   ✗ {collection}: Collection not found - {e}")
                results[collection] = {
                    'error': f"Collection not found: {str(e)}",
                    'error_type': 'not_found',
                    'results_count': 0
                }
                failed_searches += 1
            except ToolError as e:
                # Tool-specific error (e.g., embedding generation failed)
                logger.warning(f"   ✗ {collection}: Tool error - {e}")
                results[collection] = {
                    'error': str(e),
                    'error_type': 'tool_error',
                    'results_count': 0
                }
                failed_searches += 1
            except Exception as e:
                # Unexpected error
                logger.error(f"   ✗ {collection}: Unexpected error - {e}")
                results[collection] = {
                    'error': str(e),
                    'error_type': 'unexpected',
                    'results_count': 0
                }
                failed_searches += 1

        logger.info(f"✅ Cross-collection search complete: {successful_searches} succeeded, {failed_searches} failed")

        return {
            'query': query,
            'collections_searched': len(collections),
            'successful_searches': successful_searches,
            'failed_searches': failed_searches,
            'total_results': total_results,
            'results_by_collection': results
        }


    @mcp.tool()
    async def smart_search(query: str, context: Optional[Dict] = None) -> dict:
        """
        Intelligent search that automatically routes to the best tool.

        This is the main entry point for IDE integrations.
        It analyzes the query and routes to the appropriate specialized tool.

        Args:
            query: Natural language query
            context: Optional context dictionary with additional hints

        Returns:
            Dictionary with routing information and formatted result
        """
        from src.query_router import QueryRouter
        from src.response_formatter import ResponseFormatter

        logger.info(f"🧠 Smart search: '{query[:100]}...'")

        # Initialize components
        router = QueryRouter()
        formatter = ResponseFormatter()

        # Route query to best tool
        routing = router.route_query(query)

        tool_name = routing["tool"]
        params = routing["params"]

        logger.info(f"   Routed to: {tool_name} ({routing['explanation']})")

        # Execute the appropriate tool
        # Import domain tools at runtime to avoid circular dependencies
        try:
            if tool_name == "get_auth_systems":
                from src.tools.domain import get_auth_systems_impl
                result = await get_auth_systems_impl()
                formatted = formatter.format_tool_response(result, tool_name)
            elif tool_name == "get_stack_overview":
                from src.tools.domain import get_stack_overview_impl
                result = await get_stack_overview_impl()
                formatted = formatter.format_tool_response(result, tool_name)
            elif tool_name == "get_deployed_services":
                from src.tools.domain import _get_deployed_services_impl
                result = await _get_deployed_services_impl(**params)
                formatted = formatter.format_tool_response(result, tool_name)
            elif tool_name == "find_service_location":
                from src.tools.domain import find_service_location_impl
                result = await find_service_location_impl(**params)
                formatted = formatter.format_tool_response(result, tool_name)
            elif tool_name == "trace_service_dependencies":
                from src.tools.domain import trace_service_dependencies_impl
                result = await trace_service_dependencies_impl(**params)
                formatted = formatter.format_tool_response(result, tool_name)
            elif tool_name == "semantic_search":
                result = await _semantic_search_impl(**params)
                formatted_response = formatter.format_for_cursor(result)
                formatted = formatted_response.to_dict()
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
                formatted = result

            logger.info(f"✅ Smart search complete")

            return {
                "routing": routing,
                "result": formatted
            }

        except Exception as e:
            logger.error(f"Smart search failed: {e}")
            return {
                "routing": routing,
                "error": str(e),
                "result": None
            }

