"""MCP tools for collection management and repository caching."""

import logging
from typing import Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, NotFoundError

logger = logging.getLogger(__name__)

# Global state - will be set by server module
_vector_client = None
_repo_cache = None
_repo_cache_timestamp = None
_repo_cache_ttl = None
SERVER_VERSION = None


def set_collection_globals(vector_client, repo_cache, repo_cache_timestamp, repo_cache_ttl, server_version):
    """
    Set global state references needed by collection tools.
    
    Args:
        vector_client: Vector backend client instance
        repo_cache: Reference to repository cache dict
        repo_cache_timestamp: Reference to cache timestamp
        repo_cache_ttl: Cache TTL in seconds
        server_version: Server version string
    """
    global _vector_client, _repo_cache, _repo_cache_timestamp, _repo_cache_ttl, SERVER_VERSION
    _vector_client = vector_client
    _repo_cache = repo_cache
    _repo_cache_timestamp = repo_cache_timestamp
    _repo_cache_ttl = repo_cache_ttl
    SERVER_VERSION = server_version


def _list_collections_impl(collection_type: Optional[str] = None) -> dict:
    """
    Internal implementation of list_collections (not decorated with @mcp.tool).
    This can be called from other tools without triggering the FunctionTool error.

    Args:
        collection_type: Optional filter by type ("language", "service", "repo", "concern")

    Returns:
        Dictionary with collections grouped by type and metadata

    Raises:
        ToolError: If vector client is not initialized or listing fails
    """
    try:
        global _vector_client

        if not _vector_client:
            raise ToolError("Vector client not initialized")

        from src.collections import COLLECTION_SCHEMA, CollectionType

        # Get all collections from vector backend
        collection_names = _vector_client.get_collections()

        # Group collections by type
        collections_by_type = {
            "language": [],
            "service": [],
            "repo": [],
            "concern": [],
            "unknown": []  # Collections not in schema
        }

        for collection_name in collection_names:
            # Get detailed info
            info = _vector_client.get_collection_info(collection_name)
            
            if not info:
                continue
            
            # Handle SurrealDB response format
            points_count = info.get('vectors_count', info.get('points_count', 0))
            status = info.get('status', 'unknown')
            
            collection_data = {
                'name': collection_name,
                'points_count': points_count,
                'status': status.value if hasattr(status, 'value') else str(status)
            }

            # Categorize based on schema
            if collection_name in COLLECTION_SCHEMA:
                schema_info = COLLECTION_SCHEMA[collection_name]
                collection_type_str = schema_info["type"]
                collection_data["description"] = schema_info["description"]
                collection_data["type"] = collection_type_str
                collections_by_type[collection_type_str].append(collection_data)
            else:
                # Collection exists in backend but not in schema
                collection_data["type"] = "unknown"
                collection_data["description"] = "Collection not defined in schema"
                collections_by_type["unknown"].append(collection_data)

        # Filter by type if requested
        if collection_type:
            if collection_type not in collections_by_type:
                raise ToolError(f"Invalid collection type: {collection_type}. Must be one of: language, service, repo, concern")
            
            filtered_collections = collections_by_type[collection_type]
            return {
                'filter': collection_type,
                'collections': filtered_collections,
                'total_collections': len(filtered_collections)
            }

        # Return all collections grouped by type
        total_count = sum(len(colls) for colls in collections_by_type.values())
        
        return {
            'by_type': collections_by_type,
            'total_collections': total_count,
            'summary': {
                'language': len(collections_by_type['language']),
                'service': len(collections_by_type['service']),
                'repo': len(collections_by_type['repo']),
                'concern': len(collections_by_type['concern']),
                'unknown': len(collections_by_type['unknown'])
            }
        }

    except ToolError:
        raise  # Re-raise ToolError as-is

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise ToolError(f"Failed to list collections: {str(e)}") from e


def register_tools(mcp: FastMCP):
    """Register all collection tools with the MCP server."""
    
    from src.utils.github import get_cached_repo_structures
    
    @mcp.tool()
    async def refresh_repo_cache() -> dict:
        """
        Manually refresh the GitHub repository structure cache.

        Useful when you know repositories have been recently updated and want
        fresh data without waiting for cache TTL to expire.

        Returns:
            Dictionary with refresh status and repository information
        """
        global _repo_cache, _repo_cache_timestamp

        try:
            logger.info("🔄 Manual repository cache refresh requested")

            # Clear existing cache
            _repo_cache = {}
            _repo_cache_timestamp = None

            # Fetch fresh data
            repos = await get_cached_repo_structures()

            if not repos:
                return {
                    'status': 'failed',
                    'message': 'Unable to fetch repository structures from GitHub',
                    'repositories': []
                }

            repo_info = []
            for repo_key, repo_data in repos.items():
                if repo_data:
                    repo_info.append({
                        'name': repo_data.get('name', repo_key),
                        'owner': repo_data.get('owner', 'unknown'),
                        'updated_at': repo_data.get('updated_at', 'unknown'),
                        'file_count': len(repo_data.get('tree', []))
                    })

            return {
                'status': 'success',
                'message': 'Repository cache refreshed successfully',
                'cache_ttl_seconds': _repo_cache_ttl,
                'repositories': repo_info
            }

        except Exception as e:
            logger.error(f"Failed to refresh repository cache: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'repositories': []
            }


    @mcp.tool()
    def health_check() -> dict:
        """
        Check vector database connection health and return system status.

        Returns:
            Dictionary with connection status, collections count, and available collections

        Raises:
            ToolError: If vector client is not initialized or connection fails
        """
        try:
            global _vector_client

            if not _vector_client:
                raise ToolError("Vector client not initialized. Server may not have started correctly.")

            # Use the backend's health_check method
            health = _vector_client.health_check()
            
            # Add server version
            health['server_version'] = SERVER_VERSION

            return health

        except ToolError:
            raise  # Re-raise ToolError as-is

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise ToolError(f"Health check failed: {str(e)}") from e


    @mcp.tool()
    def get_collection_info(collection_name: str) -> dict:
        """
        Get detailed information about a specific vector database collection.

        Args:
            collection_name: Name of the collection (e.g., 'code_rust', 'code_typescript', or with prefix)

        Returns:
            Dictionary with collection statistics and configuration

        Raises:
            NotFoundError: If collection doesn't exist
            ToolError: If vector client is not initialized or other errors occur
        """
        try:
            global _vector_client

            if not _vector_client:
                raise ToolError("Vector client not initialized")

            from src.collections import COLLECTION_SCHEMA

            # Get collection info from vector backend
            info = _vector_client.get_collection_info(collection_name)
            
            if not info:
                raise NotFoundError(f"Collection '{collection_name}' not found")

            # Extract stats from SurrealDB response format
            points_count = info.get('vectors_count', info.get('points_count', 0))
            status = info.get('status', 'unknown')
            
            result = {
                'name': collection_name,
                'status': status.value if hasattr(status, 'value') else str(status),
                'points_count': points_count,
                'segments_count': info.get('segments_count', 0),
                'vector_size': info.get('config', {}).get('vector_size', info.get('embedding_size')),
                'distance': info.get('config', {}).get('distance_metric', 'cosine')
            }

            # Add schema information if available
            if collection_name in COLLECTION_SCHEMA:
                schema_info = COLLECTION_SCHEMA[collection_name]
                result['type'] = schema_info['type']
                result['description'] = schema_info['description']
            else:
                result['type'] = 'unknown'
                result['description'] = 'Collection not defined in schema'

            return result

        except ToolError:
            raise  # Re-raise ToolError as-is

        except Exception as e:
            logger.error(f"Failed to get collection info for '{collection_name}': {e}")

            # Check if it's a "not found" error
            if 'not found' in str(e).lower() or 'does not exist' in str(e).lower():
                raise NotFoundError(f"Collection '{collection_name}' not found") from e

            raise ToolError(f"Failed to get collection info: {str(e)}") from e


    @mcp.tool()
    def list_collections() -> dict:
        """
        List all available vector database collections grouped by type.

        Returns collections organized by:
        - language: BY_LANGUAGE collections (rust, typescript, solidity, etc.)
        - service: BY_SERVICE collections (frontend, backend, middleware, etc.)
        - repo: BY_REPO collections (platform, credit, etc.)
        - concern: BY_CONCERN collections (deployment, documentation, etc.)
        - unknown: Collections not defined in schema

        Returns:
            Dictionary with collections grouped by type:
            {
                'by_type': {
                    'language': [...],
                    'service': [...],
                    'repo': [...],
                    'concern': [...],
                    'unknown': [...]
                },
                'summary': {
                    'language': count,
                    'service': count,
                    ...
                },
                'total_collections': total
            }

        Raises:
            ToolError: If vector client is not initialized or listing fails
        """
        return _list_collections_impl()


    @mcp.tool()
    def get_collections_by_type(collection_type: str) -> dict:
        """
        Get collections filtered by a specific type.

        Args:
            collection_type: Type of collections to retrieve. Must be one of:
                - "language": BY_LANGUAGE collections (code organized by programming language)
                - "service": BY_SERVICE collections (code organized by service/layer)
                - "repo": BY_REPO collections (code organized by repository)
                - "concern": BY_CONCERN collections (code organized by architectural concern)

        Returns:
            Dictionary with filtered collections:
            {
                'filter': collection_type,
                'collections': [...],
                'total_collections': count
            }

        Raises:
            ToolError: If collection_type is invalid or client not initialized

        Examples:
            - get_collections_by_type("language") -> All code collections by language
            - get_collections_by_type("service") -> All service-layer collections
        """
        return _list_collections_impl(collection_type=collection_type)

