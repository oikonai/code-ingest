"""
Intelligent Query Router for MCP Server

Routes natural language queries to the most appropriate specialized tool
based on pattern matching and intent detection.
"""

import re
import logging
from typing import Dict, Optional, List

from .config import load_collections_config

logger = logging.getLogger(__name__)

# Load collections config for routing
_COLLECTIONS_CONFIG = load_collections_config()


class QueryIntent:
    """Detected intent from user query."""
    
    def __init__(self, intent_type: str, entities: Dict, confidence: float):
        self.intent_type = intent_type
        self.entities = entities
        self.confidence = confidence


class QueryRouter:
    """
    Intelligently route queries to the most appropriate tools.
    
    Uses regex pattern matching to detect query intent and extract
    relevant parameters for tool invocation.
    """
    
    def __init__(self):
        """Initialize the query router with intent patterns."""
        self.intent_patterns = {
            "auth_systems": [
                r"auth(?:entication)?.*system",
                r"how.*auth",
                r"what.*auth",
                r"login.*work",
                r"jwt|oauth|session.*management"
            ],
            "stack_overview": [
                r"walk.*through.*stack",
                r"technical.*stack",
                r"architecture.*overview",
                r"what.*components",
                r"system.*overview",
                r"entire.*stack"
            ],
            "deployed_services": [
                r"what.*deployed",
                r"services.*running",
                r"production.*services",
                r"deployment.*status",
                r"what.*running"
            ],
            "find_location": [
                r"where.*(?:is|does|located|implement)",
                r"find.*(?:implementation|code|function)",
                r"locate.*service",
                r"show me.*code",
                r"find.*where"
            ],
            "trace_dependencies": [
                r"what.*depend",
                r"dependency.*tree",
                r"calls.*service",
                r"who.*uses",
                r"depends on"
            ]
        }
        
        logger.info("QueryRouter initialized with 5 intent patterns")
    
    def route_query(self, query: str) -> Dict:
        """
        Analyze query and route to appropriate tool.
        
        Args:
            query: Natural language query from user
        
        Returns:
            Dictionary with:
                - tool: Name of the tool to invoke
                - params: Parameters for the tool
                - explanation: Why this tool was chosen
        """
        query_lower = query.lower()
        
        logger.debug(f"Routing query: '{query[:100]}...'")
        
        # Check for auth systems query
        if self._matches_pattern(query_lower, "auth_systems"):
            return {
                "tool": "get_auth_systems",
                "params": {},
                "explanation": "Query is asking about authentication systems"
            }
        
        # Check for stack overview
        if self._matches_pattern(query_lower, "stack_overview"):
            return {
                "tool": "get_stack_overview",
                "params": {},
                "explanation": "Query is requesting system architecture overview"
            }
        
        # Check for deployed services
        if self._matches_pattern(query_lower, "deployed_services"):
            # Extract environment if mentioned
            environment = "production"
            if "staging" in query_lower:
                environment = "staging"
            elif "dev" in query_lower or "development" in query_lower:
                environment = "dev"
            
            return {
                "tool": "get_deployed_services",
                "params": {"environment": environment},
                "explanation": f"Query is asking about deployed services in {environment}"
            }
        
        # Check for location finding
        if self._matches_pattern(query_lower, "find_location"):
            # Extract what to find
            search_term = self._extract_search_term(query)
            
            # Determine scope
            scope = "all"
            if "frontend" in query_lower:
                scope = "frontend"
            elif "backend" in query_lower:
                scope = "backend"
            elif "middleware" in query_lower:
                scope = "middleware"
            elif "infrastructure" in query_lower or "infra" in query_lower:
                scope = "infrastructure"
            
            return {
                "tool": "find_service_location",
                "params": {
                    "query": search_term,
                    "search_scope": scope
                },
                "explanation": f"Query is searching for '{search_term}' in {scope}"
            }
        
        # Check for dependency tracing
        if self._matches_pattern(query_lower, "trace_dependencies"):
            # Extract service name
            service_name = self._extract_service_name(query)
            
            return {
                "tool": "trace_service_dependencies",
                "params": {"service_name": service_name},
                "explanation": f"Query is tracing dependencies for {service_name}"
            }
        
        # Default: semantic search
        # Determine best collection based on query context
        collection = self._infer_collection(query_lower)
        
        return {
            "tool": "semantic_search",
            "params": {
                "query": query,
                "collection_name": collection,
                "limit": 20
            },
            "explanation": f"General search query routed to {collection}"
        }
    
    def _matches_pattern(self, query: str, intent_type: str) -> bool:
        """
        Check if query matches any pattern for intent type.
        
        Args:
            query: Query string (lowercase)
            intent_type: Type of intent to check
        
        Returns:
            True if query matches any pattern for this intent
        """
        patterns = self.intent_patterns.get(intent_type, [])
        return any(re.search(pattern, query) for pattern in patterns)
    
    def _extract_search_term(self, query: str) -> str:
        """
        Extract what user is searching for.
        
        Args:
            query: Original query string
        
        Returns:
            Cleaned search term
        """
        # Remove common question words
        cleaned = re.sub(
            r'\b(where|what|how|find|show|locate|is|does|the|a|an)\b',
            '',
            query,
            flags=re.IGNORECASE
        )
        return cleaned.strip()
    
    def _extract_service_name(self, query: str) -> str:
        """
        Extract service name from query.
        
        Args:
            query: Query string
        
        Returns:
            Service name or "unknown"
        """
        # Look for common service names in query
        services = [
            "arda-credit", "arda-platform", "arda-chat-agent",
            "arda-ingest", "fastmcp-proxy", "arda-knowledge-hub",
            "arda-homepage", "ari-ui"
        ]
        
        query_lower = query.lower()
        for service in services:
            if service in query_lower:
                return service
        
        # Try to extract after "service" word
        match = re.search(r'(\w+)\s*service', query, re.IGNORECASE)
        if match:
            return f"arda-{match.group(1)}"
        
        # Try to find repo names
        match = re.search(r'arda[_-](\w+)', query_lower)
        if match:
            return f"arda-{match.group(1)}"
        
        return "unknown"
    
    def _infer_collection(self, query: str) -> str:
        """
        Infer best collection based on query keywords.
        
        Args:
            query: Query string (lowercase)
        
        Returns:
            Collection name from config, or default
        """
        service_collections = _COLLECTIONS_CONFIG.get('service', {})
        concern_collections = _COLLECTIONS_CONFIG.get('concern', {})
        language_collections = _COLLECTIONS_CONFIG.get('language', {})
        default_collection = _COLLECTIONS_CONFIG.get('default')
        
        # Frontend-related keywords
        if any(word in query for word in [
            "frontend", "ui", "component", "page", "react",
            "button", "form", "dashboard", "view"
        ]):
            return service_collections.get('frontend', default_collection or 'frontend')
        
        # Backend-related keywords
        elif any(word in query for word in [
            "backend", "api", "server", "handler", "endpoint",
            "service", "rust", "axum"
        ]):
            return service_collections.get('backend', default_collection or 'backend')
        
        # Middleware keywords
        elif any(word in query for word in [
            "middleware", "agent", "proxy", "gateway"
        ]):
            return service_collections.get('middleware', default_collection or 'middleware')
        
        # Database keywords
        elif any(word in query for word in [
            "database", "model", "schema", "table", "query",
            "postgres", "sql"
        ]):
            return concern_collections.get('database_schemas', default_collection or 'database')
        
        # Deployment keywords
        elif any(word in query for word in [
            "deploy", "helm", "kubernetes", "k8s", "container",
            "docker", "manifest"
        ]):
            return concern_collections.get('deployment', default_collection or 'deployment')
        
        # Config keywords
        elif any(word in query for word in [
            "config", "configuration", "environment", "settings",
            "env", "yaml"
        ]):
            return concern_collections.get('config', default_collection or 'config')
        
        # Smart contract keywords
        elif any(word in query for word in [
            "contract", "solidity", "blockchain", "ethereum",
            "web3", "proof"
        ]):
            return language_collections.get('solidity', default_collection or 'solidity')
        
        # Documentation keywords
        elif any(word in query for word in [
            "doc", "documentation", "readme", "guide", "architecture"
        ]):
            return language_collections.get('documentation', default_collection or 'documentation')
        
        # Default collection from config
        else:
            return default_collection or list(language_collections.values())[0] if language_collections else 'code'
    
    def get_supported_intents(self) -> List[str]:
        """
        Get list of supported intent types.
        
        Returns:
            List of intent type names
        """
        return list(self.intent_patterns.keys())

