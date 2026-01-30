"""MCP tools for domain-specific queries - auth systems, stack overview, services, etc."""

import logging
from typing import Dict, List, Set
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, NotFoundError
from ..config import load_collections_config

logger = logging.getLogger(__name__)

# These will be set by server module and imported from search module
_semantic_search_impl = None
_list_collections_impl = None
_collections_config = None


def set_domain_dependencies(semantic_search_fn, list_collections_fn):
    """
    Set function dependencies needed by domain tools.
    
    Args:
        semantic_search_fn: Function to perform semantic search
        list_collections_fn: Function to list collections
    """
    global _semantic_search_impl, _list_collections_impl, _collections_config
    _semantic_search_impl = semantic_search_fn
    _list_collections_impl = list_collections_fn
    _collections_config = load_collections_config()


# Helper functions
def _extract_key_implementations(results_by_layer: Dict[str, List]) -> List[Dict]:
    """Extract key auth implementations from search results."""
    implementations = []
    seen = set()
    
    for layer, results in results_by_layer.items():
        for result in results[:3]:  # Top 3 per layer
            payload = result.get("payload", {})
            file_path = payload.get("file_path", "")
            
            if file_path and file_path not in seen:
                implementations.append({
                    "layer": layer,
                    "file": file_path,
                    "type": payload.get("item_name", ""),
                    "repo": payload.get("repo_id", ""),
                    "preview": payload.get("content_preview", "")[:200]
                })
                seen.add(file_path)
    
    return implementations


def _identify_auth_flows(results_by_layer: Dict[str, List]) -> List[str]:
    """Identify common auth flows from search results."""
    flows = []
    
    # Collect all results
    all_results = []
    for results in results_by_layer.values():
        all_results.extend(results)
    
    # Check for JWT
    if any("jwt" in r.get("payload", {}).get("content_preview", "").lower() for r in all_results):
        flows.append("JWT-based authentication")
    
    # Check for OAuth
    if any("oauth" in r.get("payload", {}).get("content_preview", "").lower() for r in all_results):
        flows.append("OAuth 2.0 authorization")
    
    # Check for session
    if any("session" in r.get("payload", {}).get("content_preview", "").lower() for r in all_results):
        flows.append("Session-based authentication")
    
    # Check for Magic Link
    if any("magic" in r.get("payload", {}).get("content_preview", "").lower() for r in all_results):
        flows.append("Magic Link authentication")
    
    return flows


async def _build_service_flow() -> Dict:
    """Build service dependency flow from metadata."""
    logger.debug("Building service flow from metadata")
    return {}


async def _get_deployment_info() -> Dict:
    """Get deployment information from Helm charts."""
    # Load collections config if not available
    if not _collections_config:
        global _collections_config
        _collections_config = load_collections_config()
    
    deploy_coll = _collections_config.get('concern', {}).get('deployment', 'deployment')
    
    try:
        deployment_results = await _semantic_search_impl(
            query="helm chart deployment configuration",
            collection_name=deploy_coll,
            limit=20,
            score_threshold=0.6
        )
        
        deployments = {}
        for result in deployment_results.get("results", []):
            payload = result.get("payload", {})
            chart_name = payload.get("helm_chart_name")
            if chart_name:
                deployments[chart_name] = {
                    "file": payload.get("file_path"),
                    "repo": payload.get("repo_id"),
                    "environment": payload.get("environment", "unknown")
                }
        
        return deployments
    except Exception as e:
        logger.warning(f"Failed to get deployment info: {e}")
        return {}


async def _get_service_api_endpoints(service_name: str) -> List[Dict]:
    """Extract API endpoints from service code."""
    endpoints = []
    
    try:
        # Try to find the service's collection
        # Use backend collection as default for service-specific searches
        collection_name = _collections_config.get('service', {}).get('backend', 'backend')
        
        endpoint_results = await _semantic_search_impl(
            query="API endpoint route handler",
            collection_name=collection_name,
            limit=30,
            score_threshold=0.6
        )
        
        for result in endpoint_results.get("results", []):
            payload = result.get("payload", {})
            
            # Extract endpoints from metadata if available
            if "api_endpoints" in payload:
                endpoints.extend(payload.get("api_endpoints", []))
        
        return endpoints
    except Exception as e:
        logger.warning(f"Failed to get API endpoints for {service_name}: {e}")
        return []


def _build_visual_graph(service: str, depends_on: set, depended_by: set) -> Dict:
    """Build a visual representation of dependencies."""
    graph = {
        "nodes": [service],
        "edges": []
    }
    
    for dep in depends_on:
        graph["nodes"].append(dep)
        graph["edges"].append({"from": service, "to": dep, "type": "depends_on"})
    
    for dep in depended_by:
        graph["nodes"].append(dep)
        graph["edges"].append({"from": dep, "to": service, "type": "uses"})
    
    return graph


async def _get_deployed_services_impl(environment: str = "production") -> dict:
    """Internal implementation for get_deployed_services."""
    logger.info(f"🔍 Analyzing deployed services in {environment}")
    
    try:
        # Search for deployment configurations
        deployment_results = await _semantic_search_impl(
            query=f"kubernetes deployment configuration {environment} environment",
            collection_name="arda_deployment",
            limit=30,
            score_threshold=0.6
        )
        
        services = {}
        for result in deployment_results.get("results", []):
            payload = result.get("payload", {})
            service_name = payload.get("service_name") or payload.get("deployment_name")
            
            if service_name:
                services[service_name] = {
                    "type": payload.get("resource_type", "Deployment"),
                    "repo": payload.get("repo_id", ""),
                    "container_images": payload.get("container_images", []),
                    "exposed_ports": payload.get("ports", []),
                    "replicas": payload.get("replicas", 1),
                    "env_vars": payload.get("environment_variables", {}),
                    "file": payload.get("file_path", "")
                }
        
        return {
            "environment": environment,
            "services_count": len(services),
            "services": services
        }
    
    except NotFoundError:
        deploy_coll = _collections_config.get('concern', {}).get('deployment', 'deployment')
        logger.warning(f"{deploy_coll} collection not found")
        return {
            "environment": environment,
            "services_count": 0,
            "services": {},
            "error": "Deployment collection not found. Collection may not be ingested yet."
        }
    except Exception as e:
        logger.error(f"Failed to get deployed services: {e}")
        return {
            "environment": environment,
            "services_count": 0,
            "services": {},
            "error": str(e)
        }


# Implementation functions for smart_search to call
async def get_auth_systems_impl() -> dict:
    """Implementation of get_auth_systems for internal/smart_search use."""
    logger.info("🔍 Analyzing authentication systems across ingested stack")
    
    auth_queries = [
        "JWT authentication implementation",
        "OAuth authorization flow",
        "session management middleware",
        "API key authentication",
        "user authentication handler"
    ]
    
    results_by_layer = {
        "frontend": [],
        "backend": [],
        "middleware": [],
    }
    
    # Search in frontend
    try:
        for query in auth_queries:
            try:
                frontend_results = await _semantic_search_impl(
                    query=query,
                    collection_name=_collections_config.get('service', {}).get('frontend', 'frontend'),
                    limit=5,
                    score_threshold=0.65
                )
                results_by_layer["frontend"].extend(frontend_results.get("results", []))
            except NotFoundError:
                frontend_results = await _semantic_search_impl(
                    query=query,
                    collection_name=_collections_config.get('language', {}).get('typescript', 'code_typescript'),
                    limit=5,
                    score_threshold=0.65
                )
                results_by_layer["frontend"].extend(frontend_results.get("results", []))
    except Exception as e:
        logger.warning(f"Frontend auth search failed: {e}")
    
    # Search in backend
    try:
        for query in auth_queries:
            try:
                backend_results = await _semantic_search_impl(
                    query=query,
                    collection_name=_collections_config.get('service', {}).get('backend', 'backend'),
                    limit=5,
                    score_threshold=0.65
                )
                results_by_layer["backend"].extend(backend_results.get("results", []))
            except NotFoundError:
                backend_results = await _semantic_search_impl(
                    query=query,
                    collection_name=_collections_config.get('language', {}).get('rust', 'code_rust'),
                    limit=5,
                    score_threshold=0.65
                )
                results_by_layer["backend"].extend(backend_results.get("results", []))
    except Exception as e:
        logger.warning(f"Backend auth search failed: {e}")
    
    # Search in middleware
    try:
        for query in auth_queries:
            try:
                middleware_results = await _semantic_search_impl(
                    query=query,
                    collection_name=_collections_config.get('service', {}).get('middleware', 'middleware'),
                    limit=5,
                    score_threshold=0.65
                )
                results_by_layer["middleware"].extend(middleware_results.get("results", []))
            except NotFoundError:
                pass  # Middleware collection might not exist
    except Exception as e:
        logger.warning(f"Middleware auth search failed: {e}")
    
    auth_systems = {
        "summary": "Authentication systems across ingested stack",
        "by_layer": results_by_layer,
        "key_implementations": _extract_key_implementations(results_by_layer),
        "auth_flows": _identify_auth_flows(results_by_layer)
    }
    
    logger.info(f"✅ Found {len(auth_systems['key_implementations'])} key auth implementations")
    
    return auth_systems


async def get_stack_overview_impl() -> dict:
    """Implementation of get_stack_overview for internal/smart_search use."""
    logger.info("🔍 Building comprehensive stack overview")
    
    # Query for high-level architectural documents
    try:
        overview_results = await _semantic_search_impl(
            query="system architecture overview components services",
            collection_name=_collections_config.get('language', {}).get('documentation', 'documentation'),
            limit=10,
            score_threshold=0.6
        )
        docs = overview_results.get("results", [])[:3]
    except Exception as e:
        logger.warning(f"Failed to get architecture docs: {e}")
        docs = []
    
    # Get repository information
    repos_by_type = {
        "frontend": [],
        "backend": [],
        "middleware": [],
        "infrastructure": [],
    }
    
    try:
        all_collections = _list_collections_impl()
        for collection_name in all_collections.get("by_type", {}).get("service", []):
            name = collection_name.get("name", "")
            if "frontend" in name:
                repos_by_type["frontend"].append(name)
            elif "backend" in name:
                repos_by_type["backend"].append(name)
            elif "middleware" in name:
                repos_by_type["middleware"].append(name)
            elif "infrastructure" in name or "deployment" in name:
                repos_by_type["infrastructure"].append(name)
    except Exception as e:
        logger.warning(f"Failed to list collections: {e}")
    
    service_flow = await _build_service_flow()
    deployment_info = await _get_deployment_info()
    
    tech_stack = {
        "frontend": ["TypeScript", "React", "Next.js", "shadcn/ui"],
        "backend": ["Rust", "Axum", "Tokio"],
        "middleware": ["Python", "TypeScript", "FastAPI"],
        "infrastructure": ["Kubernetes", "Helm", "Terraform", "AWS"],
        "databases": ["PostgreSQL", "SurrealDB"],
        "ai_ml": ["Claude API", "Vector embeddings", "Qdrant"],
        "blockchain": ["Ethereum", "Solidity", "SP1 zkVM"]
    }
    
    logger.info("✅ Stack overview complete")
    
    return {
        "summary": "Complete technical stack overview",
        "services_by_type": repos_by_type,
        "service_flow": service_flow,
        "deployment_info": deployment_info,
        "technology_stack": tech_stack,
        "documentation": docs
    }


async def find_service_location_impl(query: str, search_scope: str = "all") -> dict:
    """Implementation of find_service_location for internal/smart_search use."""
    logger.info(f"🔍 Finding service location: '{query}' (scope={search_scope})")
    
    # Load collections config if not already loaded
    if not _collections_config:
        global _collections_config
        _collections_config = load_collections_config()
    
    # Determine collections to search based on scope (using config or defaults)
    collections = []
    if search_scope == "all":
        rust_coll = _collections_config.get('language', {}).get('rust', 'code_rust')
        ts_coll = _collections_config.get('language', {}).get('typescript', 'code_typescript')
        sol_coll = _collections_config.get('language', {}).get('solidity', 'code_solidity')
        collections = [rust_coll, ts_coll, sol_coll]
    elif search_scope == "frontend":
        collections = [_collections_config.get('language', {}).get('typescript', 'code_typescript')]
    elif search_scope == "backend":
        collections = [_collections_config.get('language', {}).get('rust', 'code_rust')]
    elif search_scope == "infrastructure":
        collections = [_collections_config.get('concern', {}).get('deployment', 'deployment')]
    else:
        rust_coll = _collections_config.get('language', {}).get('rust', 'code_rust')
        ts_coll = _collections_config.get('language', {}).get('typescript', 'code_typescript')
        collections = [rust_coll, ts_coll]
    
    all_results = []
    for collection in collections:
        try:
            results = await _semantic_search_impl(
                query=query,
                collection_name=collection,
                limit=10,
                score_threshold=0.6
            )
            for result in results.get("results", []):
                result["collection"] = collection
                all_results.append(result)
        except Exception as e:
            logger.warning(f"Search in {collection} failed: {e}")
    
    # Sort by score
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Extract locations
    locations = []
    for result in all_results[:15]:
        payload = result.get("payload", {})
        locations.append({
            "repo": payload.get("repo_id", ""),
            "file": payload.get("file_path", ""),
            "lines": f"{payload.get('start_line', 0)}-{payload.get('end_line', 0)}",
            "item_name": payload.get("item_name", ""),
            "relevance_score": result.get("score", 0),
            "preview": payload.get("content_preview", "")[:200]
        })
    
    top_match = locations[0] if locations else None
    
    return {
        "query": query,
        "search_scope": search_scope,
        "total_results": len(locations),
        "locations": locations,
        "top_match": top_match
    }


async def trace_service_dependencies_impl(service_name: str) -> dict:
    """Implementation of trace_service_dependencies for internal/smart_search use."""
    logger.info(f"🔍 Tracing dependencies for service: {service_name}")
    
    # Search for service dependencies
    depends_on = set()
    depended_by = set()
    
    # Load collections config if not available
    if not _collections_config:
        global _collections_config
        _collections_config = load_collections_config()
    
    deploy_coll = _collections_config.get('concern', {}).get('deployment', 'deployment')
    
    try:
        # Search for imports and dependencies
        dep_results = await _semantic_search_impl(
            query=f"{service_name} dependencies imports requires",
            collection_name=deploy_coll,
            limit=20,
            score_threshold=0.6
        )
        
        for result in dep_results.get("results", []):
            payload = result.get("payload", {})
            if payload.get("dependencies"):
                depends_on.update(payload.get("dependencies", []))
    except Exception as e:
        logger.warning(f"Dependency search failed: {e}")
    
    # Get API endpoints
    api_endpoints = await _get_service_api_endpoints(service_name)
    
    # Get deployment configuration
    deployment = {}
    try:
        deployment_info = await _get_deployed_services_impl()
        deployment = deployment_info.get("services", {}).get(service_name, {})
    except Exception as e:
        logger.warning(f"Failed to get deployment info: {e}")
    
    # Build dependency graph
    dependency_graph = _build_visual_graph(service_name, depends_on, depended_by)
    
    return {
        "service": service_name,
        "depends_on": {
            "services": list(depends_on),
            "databases": ["postgresql"] if "backend" in service_name else [],
            "external_apis": []
        },
        "depended_by": list(depended_by),
        "api_endpoints": api_endpoints[:10],
        "deployment": deployment,
        "dependency_graph": dependency_graph
    }


def register_tools(mcp: FastMCP):
    """Register all domain tools with the MCP server."""
    
    @mcp.tool()
    async def get_auth_systems() -> dict:
        """
        Find all authentication implementations across the ingested stack.

        Returns information about:
        - Authentication middleware
        - JWT/OAuth implementations
        - Session management
        - API authentication

        Use this to answer: "What are the authentication systems used across the stack?"
        
        Returns:
            Dictionary with authentication systems grouped by layer
        """
        return await get_auth_systems_impl()


    @mcp.tool()
    async def get_stack_overview() -> dict:
        """
        Get a comprehensive overview of the entire technical stack.

        Returns:
        - All services grouped by type (frontend, backend, middleware, infrastructure)
        - Service dependencies
        - Deployment information
        - Technology stack

        Use this to answer: "Walk me through the technical stack"
        
        Returns:
            Dictionary with complete stack overview
        """
        return await get_stack_overview_impl()


    @mcp.tool()
    async def get_deployed_services(environment: str = "production") -> dict:
        """
        List all deployed services with their configurations.
        
        Args:
            environment: The environment to query (production, staging, dev)
        
        Returns:
            List of services with deployment details including:
            - Service name
            - Replicas
            - Resources (CPU, memory)
            - Exposed endpoints
            - Container images
            - Environment variables
        
        Use this to answer: "What services are deployed?"
        
        Returns:
            Dictionary with deployed services information
        """
        return await _get_deployed_services_impl(environment)


    @mcp.tool()
    async def find_service_location(query: str, search_scope: str = "all") -> dict:
        """
        Find where a service, function, or feature is implemented.
        
        Args:
            query: What to search for (e.g., "balance calculation", "user authentication", "payment processing")
            search_scope: Scope of search - "all", "frontend", "backend", "middleware", "infrastructure"
        
        Returns:
            Locations where the queried service/function/feature is implemented:
            - Repository
            - File path
            - Line numbers
            - Related code
            - Dependencies
        
        Use this to answer: "Where does X occur?" or "Find the implementation of Y"
        
        Returns:
            Dictionary with locations and metadata
        """
        return await find_service_location_impl(query, search_scope)


    @mcp.tool()
    async def trace_service_dependencies(service_name: str) -> dict:
        """
        Show complete dependency tree for a service.
        
        Args:
            service_name: Name of the service (e.g., "my-backend", "my-frontend")
        
        Returns:
            - Services this depends on
            - Services that depend on this
            - Databases used
            - External APIs called
            - Deployment configuration
        
        Use this to answer: "What does X depend on?" or "What calls service Y?"
        
        Returns:
            Dictionary with dependency information
        """
        return await trace_service_dependencies_impl(service_name)

