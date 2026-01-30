"""
Response Formatter for Arda MCP Server

Formats MCP tool responses for optimal IDE integration (Cursor, Claude Code).
Provides clickable file paths, concise summaries, and action suggestions.
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class FormattedResponse:
    """
    Optimized response format for IDE consumption.
    
    Attributes:
        summary: Concise summary of results
        results: List of formatted result items
        total_results: Total number of results
        query: Original query string
        collections_searched: List of collections searched
        quick_actions: Suggested actions user can take
        related_queries: Suggested related queries
    """
    
    summary: str
    results: List[Dict]
    total_results: int
    query: str
    collections_searched: List[str]
    quick_actions: List[str]
    related_queries: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary,
            "results": self.results,
            "metadata": {
                "total_results": self.total_results,
                "query": self.query,
                "collections_searched": self.collections_searched
            },
            "ide_hints": {
                "quick_actions": self.quick_actions,
                "related_queries": self.related_queries
            }
        }


class ResponseFormatter:
    """Format MCP responses for optimal IDE integration."""
    
    def format_for_cursor(self, raw_response: Dict) -> FormattedResponse:
        """
        Format response for Cursor IDE.
        
        Cursor benefits from:
        - File paths as clickable links
        - Line numbers for jump-to-definition
        - Concise summaries
        
        Args:
            raw_response: Raw response from tool
        
        Returns:
            FormattedResponse optimized for Cursor
        """
        results = raw_response.get("results", [])
        query = raw_response.get("query", "")
        
        formatted_results = []
        for result in results:
            payload = result.get("payload", {})
            
            # Format for Cursor with clickable paths
            formatted_results.append({
                "file": payload.get("file_path", "unknown"),
                "lines": f"{payload.get('start_line', 0)}-{payload.get('end_line', 0)}",
                "preview": payload.get("content_preview", "")[:200],
                "relevance": result.get("score", 0),
                "repo": payload.get("repo_id", "unknown"),
                "type": payload.get("item_type", "unknown"),
                "item_name": payload.get("item_name", ""),
                # Cursor can use this to create file:// links
                "click_action": f"open:{payload.get('file_path', '')}:{payload.get('start_line', 1)}"
            })
        
        summary = self._generate_summary(formatted_results)
        quick_actions = self._suggest_actions(formatted_results)
        related_queries = self._suggest_related_queries(query)
        
        collections_searched = []
        if "collection" in raw_response:
            collections_searched = [raw_response["collection"]]
        elif "collections_searched" in raw_response:
            collections_searched = raw_response.get("collections_searched", [])
        
        return FormattedResponse(
            summary=summary,
            results=formatted_results,
            total_results=len(formatted_results),
            query=query,
            collections_searched=collections_searched,
            quick_actions=quick_actions,
            related_queries=related_queries
        )
    
    def format_for_claude_code(self, raw_response: Dict) -> FormattedResponse:
        """
        Format response for Claude Code CLI.
        
        CLI benefits from:
        - Concise text output
        - Clear file paths
        - Action suggestions
        
        Args:
            raw_response: Raw response from tool
        
        Returns:
            FormattedResponse optimized for CLI
        """
        # Similar to Cursor but with CLI-friendly formatting
        return self.format_for_cursor(raw_response)
    
    def format_tool_response(self, raw_response: Dict, tool_name: str) -> Dict:
        """
        Format response from specialized tools (auth, stack, etc).
        
        Args:
            raw_response: Raw response from tool
            tool_name: Name of the tool that generated response
        
        Returns:
            Formatted response dictionary
        """
        # Add metadata
        formatted = {
            "tool": tool_name,
            "data": raw_response,
            "metadata": {
                "formatted_at": "runtime",
                "format_version": "1.0"
            }
        }
        
        # Add quick actions based on tool type
        if tool_name == "get_auth_systems":
            formatted["ide_hints"] = {
                "quick_actions": [
                    "View JWT implementation",
                    "Check OAuth flow",
                    "Review session management"
                ],
                "related_queries": [
                    "Find JWT token validation",
                    "Show OAuth configuration",
                    "Where is session storage?"
                ]
            }
        elif tool_name == "get_stack_overview":
            formatted["ide_hints"] = {
                "quick_actions": [
                    "View service dependencies",
                    "Check deployment configs",
                    "Explore repositories"
                ],
                "related_queries": [
                    "What services are deployed?",
                    "Trace arda-credit dependencies",
                    "Find frontend components"
                ]
            }
        elif tool_name == "get_deployed_services":
            formatted["ide_hints"] = {
                "quick_actions": [
                    "View Helm charts",
                    "Check environment variables",
                    "Review resource limits"
                ],
                "related_queries": [
                    "Show deployment configuration",
                    "Find Kubernetes manifests",
                    "What are the service endpoints?"
                ]
            }
        elif tool_name == "find_service_location":
            formatted["ide_hints"] = {
                "quick_actions": [
                    "Open top match",
                    "View all implementations",
                    "Check tests"
                ],
                "related_queries": [
                    "Find tests for this",
                    "Show documentation",
                    "Find usage examples"
                ]
            }
        elif tool_name == "trace_service_dependencies":
            formatted["ide_hints"] = {
                "quick_actions": [
                    "View dependency graph",
                    "Check API endpoints",
                    "Review deployment"
                ],
                "related_queries": [
                    "What depends on this service?",
                    "Show API contracts",
                    "Find database schemas"
                ]
            }
        
        return formatted
    
    def _generate_summary(self, results: List[Dict]) -> str:
        """
        Generate concise summary of results.
        
        Args:
            results: List of formatted results
        
        Returns:
            Summary string
        """
        if not results:
            return "No results found"
        
        repos = set(r.get("repo") for r in results if r.get("repo") != "unknown")
        file_types = set(r.get("type") for r in results if r.get("type") != "unknown")
        
        summary = f"Found {len(results)} results"
        
        if repos:
            summary += f" across {len(repos)} repositories"
        
        if file_types:
            type_str = ", ".join(sorted(file_types)[:3])
            summary += f". Includes {type_str}"
            if len(file_types) > 3:
                summary += " and more"
        
        summary += "."
        
        return summary
    
    def _suggest_actions(self, results: List[Dict]) -> List[str]:
        """
        Suggest actions user might want to take.
        
        Args:
            results: List of formatted results
        
        Returns:
            List of suggested actions
        """
        if not results:
            return ["Try a different search", "Check collection availability"]
        
        actions = [
            f"Open {results[0].get('file', 'top result')}",
            "Find related implementations",
            "View full file content"
        ]
        
        # Add repo-specific actions
        unique_repos = set(r.get("repo") for r in results if r.get("repo") != "unknown")
        if len(unique_repos) > 1:
            actions.append("Compare implementations across repos")
        
        # Add type-specific actions
        types = set(r.get("type") for r in results)
        if "function" in types:
            actions.append("Find function usages")
        if "class" in types or "struct" in types:
            actions.append("View class hierarchy")
        
        return actions[:5]  # Limit to 5 actions
    
    def _suggest_related_queries(self, original_query: str) -> List[str]:
        """
        Suggest related queries user might want to run.
        
        Args:
            original_query: Original search query
        
        Returns:
            List of related query suggestions
        """
        if not original_query:
            return []
        
        related = [
            f"Find tests for {original_query}",
            f"Show documentation for {original_query}",
            f"Find usage examples of {original_query}"
        ]
        
        # Add context-specific suggestions
        query_lower = original_query.lower()
        
        if "function" in query_lower or "method" in query_lower:
            related.append("Show function callers")
        
        if "api" in query_lower or "endpoint" in query_lower:
            related.append("Find API documentation")
        
        if "component" in query_lower:
            related.append("Find component props and usage")
        
        return related[:5]  # Limit to 5 suggestions

