"""MCP tools for metadata discovery - listing resources and prompts."""

import logging
import inspect
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Global state - will be set by server module
SERVER_NAME = None
_resource_functions = {}  # Map of URI to resource function
_prompt_functions = {}  # Map of prompt name to prompt function
_semantic_search_impl = None  # Semantic search function


def set_metadata_globals(server_name, resource_fns, prompt_fns, semantic_search_fn=None):
    """
    Set global state references needed by metadata tools.

    Args:
        server_name: Server name string
        resource_fns: Dictionary mapping URIs to resource functions
        prompt_fns: Dictionary mapping prompt names to prompt functions
        semantic_search_fn: Optional semantic search function for execute_prompt
    """
    global SERVER_NAME, _resource_functions, _prompt_functions, _semantic_search_impl
    SERVER_NAME = server_name
    _resource_functions = resource_fns
    _prompt_functions = prompt_fns
    _semantic_search_impl = semantic_search_fn


def register_tools(mcp: FastMCP):
    """Register all metadata tools with the MCP server."""

    @mcp.tool()
    async def list_resources() -> dict:
        """
        List all available MCP resources exposed by this server.

        Resources provide contextual data and documentation that can be read.

        Returns:
            Dictionary with list of resources, each containing:
            - uri: Resource URI (e.g., "arda://collections")
            - name: Human-readable name
            - description: What the resource contains
            - mime_type: Content type (typically "text/plain" or "text/markdown")

        Use this to answer: "What resources are available?"
        """
        logger.info("📚 Listing all MCP resources")

        resources = [
            {
                "uri": "arda://collections",
                "name": "Collection Information",
                "description": "Live collection stats, repository structure, and vector database organization",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://search-tips",
                "name": "Search Best Practices",
                "description": "Tips for effective semantic code search with collection guides and query formulation",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://dashboard",
                "name": "Collection Health Dashboard",
                "description": "Real-time health metrics, point counts, and status for all collections",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://api-catalog",
                "name": "API Endpoint Catalog",
                "description": "Complete catalog of all API endpoints extracted from the codebase",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://patterns",
                "name": "Code Patterns Library",
                "description": "Common code patterns, best practices, and implementation examples",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://stats",
                "name": "Codebase Statistics",
                "description": "Live statistics aggregated from vector collections (LOC, files, languages)",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://dependencies",
                "name": "Service Dependency Map",
                "description": "Service dependency graph and integration points across the stack",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://changelog",
                "name": "Codebase Changelog",
                "description": "Recent code changes and repository updates with live GitHub metadata",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://metrics",
                "name": "Performance Metrics",
                "description": "Operational metrics including cache performance and search insights",
                "mime_type": "text/markdown"
            },
            {
                "uri": "arda://architecture",
                "name": "Architecture Diagrams",
                "description": "System architecture with Mermaid diagrams showing service dependencies and data flows",
                "mime_type": "text/markdown"
            }
        ]

        return {
            "resources": resources,
            "count": len(resources),
            "server": SERVER_NAME,
            "spec_version": "2024-11-05"
        }


    @mcp.tool()
    async def read_resource(uri: str) -> dict:
        """
        Read a specific MCP resource by its URI.

        Args:
            uri: Resource URI (e.g., "arda://collections", "arda://search-tips")

        Returns:
            Dictionary with:
            - uri: The requested URI
            - content: The resource content (markdown text)
            - mime_type: Content type
            - error: Error message if resource not found

        Use this to answer: "Show me the collections resource", "What's in arda://dashboard?"
        """
        logger.info(f"📖 Reading resource: {uri}")

        if uri not in _resource_functions:
            available = ", ".join(_resource_functions.keys())
            return {
                "uri": uri,
                "error": f"Resource not found. Available resources: {available}",
                "error_type": "not_found"
            }

        try:
            # Call the resource function
            content = await _resource_functions[uri]()

            return {
                "uri": uri,
                "content": content,
                "mime_type": "text/markdown",
                "length": len(content)
            }
        except Exception as e:
            logger.error(f"Failed to read resource {uri}: {e}")
            return {
                "uri": uri,
                "error": f"Failed to read resource: {str(e)}",
                "error_type": "server_error"
            }


    @mcp.tool()
    def list_prompts() -> dict:
        """
        List all available pre-configured prompts (search templates).

        Prompts are domain-specific search patterns optimized for Arda Credit codebase.

        Returns:
            Dictionary with list of prompts, each containing:
            - name: Prompt name/identifier
            - description: What the prompt helps you find
            - parameters: List of parameters the prompt accepts
            - example_use: Example usage description

        Use this to answer: "What prompts are available?", "Show me search templates"
        """
        logger.info("📋 Listing all MCP prompts")

        prompts = [
            {
                "name": "search_deal_operations",
                "description": "Search for deal management operations (origination, payment, transfer, marketplace)",
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
            {
                "name": "search_zkproof_implementation",
                "description": "Search for zero-knowledge proof implementation with SP1 zkVM",
                "parameters": [],
                "example_use": "Find ZK proof generation and verification code"
            },
            {
                "name": "search_authentication_system",
                "description": "Search for authentication patterns (magic link, JWT, sessions)",
                "parameters": [
                    {
                        "name": "auth_type",
                        "type": "string",
                        "default": "all",
                        "options": ["magic_link", "jwt", "sessions", "all"]
                    }
                ],
                "example_use": "Find magic link authentication implementation"
            },
            {
                "name": "search_usdc_integration",
                "description": "Search for USDC stablecoin integration (deposits, withdrawals, smart contracts)",
                "parameters": [],
                "example_use": "Find USDC deposit handling in contracts and backend"
            },
            {
                "name": "search_frontend_feature",
                "description": "Search for frontend features and React components",
                "parameters": [
                    {
                        "name": "feature_name",
                        "type": "string",
                        "required": True
                    }
                ],
                "example_use": "Find investor portfolio dashboard component"
            },
            {
                "name": "debug_arda_issue",
                "description": "Debug-focused search with lower thresholds for comprehensive results",
                "parameters": [
                    {
                        "name": "issue_description",
                        "type": "string",
                        "required": True
                    }
                ],
                "example_use": "Debug deal payment processing failure"
            },
            {
                "name": "explore_architecture_layer",
                "description": "Explore specific architectural layer (presentation, business, data, blockchain)",
                "parameters": [
                    {
                        "name": "layer",
                        "type": "string",
                        "default": "all",
                        "options": ["presentation", "business", "data", "blockchain", "all"]
                    }
                ],
                "example_use": "Explore the data layer and database schemas"
            },
            {
                "name": "find_api_endpoint",
                "description": "Find API endpoint implementation across frontend and backend",
                "parameters": [
                    {
                        "name": "endpoint_pattern",
                        "type": "string",
                        "required": True
                    }
                ],
                "example_use": "Find /api/deals/:id endpoint implementation"
            },
            {
                "name": "trace_data_flow",
                "description": "Trace data flow for an entity through the entire stack",
                "parameters": [
                    {
                        "name": "entity",
                        "type": "string",
                        "required": True
                    }
                ],
                "example_use": "Trace User entity from database to frontend"
            },
            {
                "name": "find_test_coverage",
                "description": "Find test coverage for a specific feature (unit, integration, e2e)",
                "parameters": [
                    {
                        "name": "feature",
                        "type": "string",
                        "required": True
                    }
                ],
                "example_use": "Find all tests for deal creation feature"
            },
            {
                "name": "explore_deployment_config",
                "description": "Explore deployment configuration and infrastructure",
                "parameters": [
                    {
                        "name": "service",
                        "type": "string",
                        "default": "all"
                    }
                ],
                "example_use": "Find Kubernetes deployment config for arda-credit"
            },
            {
                "name": "audit_security_patterns",
                "description": "Audit security implementations (authentication, authorization, encryption, validation)",
                "parameters": [
                    {
                        "name": "concern",
                        "type": "string",
                        "default": "all",
                        "options": ["authentication", "authorization", "encryption", "validation", "all"]
                    }
                ],
                "example_use": "Audit authentication security patterns"
            }
        ]

        return {
            "prompts": prompts,
            "count": len(prompts),
            "server": SERVER_NAME,
            "spec_version": "2024-11-05"
        }


    @mcp.tool()
    def get_prompt(name: str) -> dict:
        """
        Get details about a specific prompt and generate its search instructions.

        Args:
            name: Prompt name (e.g., "search_deal_operations", "debug_arda_issue")

        Returns:
            Dictionary with:
            - name: Prompt name
            - description: What the prompt does
            - parameters: Parameter definitions
            - instructions: Generated search instructions (what you'd use to search)
            - error: Error message if prompt not found

        Use this to answer: "Show me the deal operations prompt", "What does debug_arda_issue do?"
        """
        logger.info(f"📝 Getting prompt: {name}")

        if name not in _prompt_functions:
            available = ", ".join(_prompt_functions.keys())
            return {
                "name": name,
                "error": f"Prompt not found. Available prompts: {available}",
                "error_type": "not_found"
            }

        try:
            prompt_func = _prompt_functions[name]

            # Get function signature to extract parameters
            sig = inspect.signature(prompt_func)

            parameters = []
            has_required_params = False
            for param_name, param in sig.parameters.items():
                param_info = {
                    "name": param_name,
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "string",
                    "required": param.default == inspect.Parameter.empty,
                }
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default
                else:
                    has_required_params = True
                parameters.append(param_info)

            # Generate sample instructions
            # If function has required parameters, call with placeholder values
            sample_instructions = None
            try:
                if has_required_params:
                    # Build kwargs with placeholders for required params and defaults for optional
                    kwargs = {}
                    for param_name, param in sig.parameters.items():
                        if param.default == inspect.Parameter.empty:
                            # Use placeholder for required param
                            kwargs[param_name] = f"<{param_name}>"
                        else:
                            # Use default value
                            kwargs[param_name] = param.default
                    sample_instructions = prompt_func(**kwargs)
                else:
                    # No required params, call with defaults
                    sample_instructions = prompt_func()
            except Exception as e:
                logger.warning(f"Could not generate sample instructions for {name}: {e}")
                sample_instructions = "(Instructions require parameters - see parameter list above)"

            return {
                "name": name,
                "description": prompt_func.__doc__ or "No description available",
                "parameters": parameters,
                "instructions": sample_instructions,
                "length": len(sample_instructions) if sample_instructions else 0,
                "has_required_params": has_required_params
            }
        except Exception as e:
            logger.error(f"Failed to get prompt {name}: {e}")
            return {
                "name": name,
                "error": f"Failed to get prompt: {str(e)}",
                "error_type": "server_error"
            }


    @mcp.tool()
    async def execute_prompt(name: str, parameters: str = "{}") -> dict:
        """
        Execute a prompt's search strategy automatically.

        This tool takes a prompt name and its parameters (as JSON string), generates the search
        instructions, parses them to identify search operations, and executes
        the searches automatically, returning aggregated results.

        Args:
            name: Prompt name (e.g., "search_deal_operations", "debug_arda_issue")
            parameters: JSON string with prompt-specific parameters (default: "{}")
                Examples:
                - '{"operation_type": "payment"}' for search_deal_operations
                - '{"issue_description": "deal payment failure"}' for debug_arda_issue
                - '{"feature_name": "investor portfolio"}' for search_frontend_feature
                - '{}' for prompts with no parameters

        Returns:
            Dictionary with:
            - prompt_name: Name of the executed prompt
            - parameters: Parameters used
            - instructions: Generated search instructions
            - results: Aggregated search results from all searches
            - searches_executed: Number of searches performed
            - total_results: Total number of results found
            - error: Error message if execution failed

        Use this to answer: "Execute the deal operations search", "Run the zkproof prompt"

        Examples:
            execute_prompt("search_deal_operations", '{"operation_type": "payment"}')
            execute_prompt("debug_arda_issue", '{"issue_description": "deal payment failure"}')
            execute_prompt("search_frontend_feature", '{"feature_name": "investor portfolio"}')
            execute_prompt("search_zkproof_implementation", "{}")
        """
        import json as json_module
        import time
        from src.tracking.prompt_tracker import PromptUsageTracker

        # Start timing
        start_time = time.time()
        tracker = PromptUsageTracker()

        # Parse parameters JSON string
        try:
            params_dict = json_module.loads(parameters) if parameters else {}
        except json_module.JSONDecodeError as e:
            # Record failure
            duration_ms = (time.time() - start_time) * 1000
            tracker.record_execution(name, success=False, duration_ms=duration_ms)
            return {
                "prompt_name": name,
                "error": f"Invalid JSON in parameters: {str(e)}",
                "error_type": "validation_error"
            }

        logger.info(f"🚀 Executing prompt: {name} with params: {params_dict}")

        if name not in _prompt_functions:
            available = ", ".join(_prompt_functions.keys())
            duration_ms = (time.time() - start_time) * 1000
            tracker.record_execution(name, success=False, duration_ms=duration_ms)
            return {
                "prompt_name": name,
                "error": f"Prompt not found. Available prompts: {available}",
                "error_type": "not_found"
            }

        if not _semantic_search_impl:
            duration_ms = (time.time() - start_time) * 1000
            tracker.record_execution(name, success=False, duration_ms=duration_ms)
            return {
                "prompt_name": name,
                "error": "Semantic search function not available. Server may not be fully initialized.",
                "error_type": "server_error"
            }

        try:
            prompt_func = _prompt_functions[name]

            # Get function signature to validate parameters
            sig = inspect.signature(prompt_func)

            # Check if all required parameters are provided
            missing_params = []
            for param_name, param in sig.parameters.items():
                if param.default == inspect.Parameter.empty and param_name not in params_dict:
                    missing_params.append(param_name)

            if missing_params:
                duration_ms = (time.time() - start_time) * 1000
                tracker.record_execution(name, success=False, duration_ms=duration_ms)
                return {
                    "prompt_name": name,
                    "error": f"Missing required parameters: {', '.join(missing_params)}",
                    "error_type": "validation_error",
                    "required_parameters": missing_params
                }

            # Generate instructions with provided parameters
            instructions = prompt_func(**params_dict)

            # Parse instructions to extract search operations
            # Look for patterns like:
            # 1. arda_code_rust collection (limit=20, threshold=0.6)
            # 2. collection_name (limit=X, threshold=Y): query description
            import re

            search_pattern = r'(\w+)\s+collection.*?limit=(\d+).*?threshold=([\d.]+)'
            matches = re.findall(search_pattern, instructions, re.IGNORECASE)

            if not matches:
                # Fallback: try to identify collection mentions
                collection_pattern = r'(arda_\w+)'
                collection_matches = re.findall(collection_pattern, instructions)

                if collection_matches:
                    # Use default search parameters
                    matches = [(coll, "15", "0.6") for coll in set(collection_matches)]

            if not matches:
                duration_ms = (time.time() - start_time) * 1000
                tracker.record_execution(name, success=False, duration_ms=duration_ms)
                return {
                    "prompt_name": name,
                    "parameters": params_dict,
                    "instructions": instructions,
                    "error": "Could not parse search operations from prompt instructions. Prompt may not contain searchable collections.",
                    "error_type": "parse_error"
                }

            # Execute searches
            all_results = []
            searches_executed = 0

            # Build a query from the prompt name and parameters
            query_parts = [name.replace('_', ' ')]
            for key, value in params_dict.items():
                query_parts.append(str(value))
            base_query = ' '.join(query_parts)

            for collection_name, limit, threshold in matches:
                try:
                    logger.info(f"  🔍 Searching {collection_name} (limit={limit}, threshold={threshold})")

                    search_result = await _semantic_search_impl(
                        query=base_query,
                        collection_name=collection_name,
                        limit=int(limit),
                        score_threshold=float(threshold)
                    )

                    if search_result.get('results'):
                        all_results.extend(search_result['results'])
                        searches_executed += 1
                        logger.info(f"    ✓ Found {len(search_result['results'])} results")
                    else:
                        logger.info(f"    ℹ No results found")

                except Exception as e:
                    logger.warning(f"  ⚠️ Search failed for {collection_name}: {e}")
                    continue

            # Sort results by score
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)

            # Record success
            duration_ms = (time.time() - start_time) * 1000
            tracker.record_execution(name, success=True, duration_ms=duration_ms)

            return {
                "prompt_name": name,
                "parameters": params_dict,
                "instructions": instructions,
                "searches_executed": searches_executed,
                "total_results": len(all_results),
                "results": all_results[:50],  # Limit to top 50 results
                "execution_summary": f"Executed {searches_executed} searches across {len(matches)} collections, found {len(all_results)} total results"
            }

        except Exception as e:
            logger.error(f"Failed to execute prompt {name}: {e}")
            # Record failure
            duration_ms = (time.time() - start_time) * 1000
            tracker.record_execution(name, success=False, duration_ms=duration_ms)
            return {
                "prompt_name": name,
                "parameters": params_dict,
                "error": f"Failed to execute prompt: {str(e)}",
                "error_type": "execution_error"
            }

