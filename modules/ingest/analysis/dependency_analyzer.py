"""
Dependency Analyzer

Analyzes dependencies and relationships across repositories to build
a comprehensive service dependency graph.

Following CLAUDE.md: <500 lines, single responsibility (dependency analysis only).
"""

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Analyzes dependencies and relationships across repositories.
    
    Features:
    - Import graph building (Python, Node, Rust)
    - API call detection (HTTP clients)
    - Service mesh extraction (Helm/K8s)
    - Package dependency mapping
    """
    
    def __init__(self, all_repo_data: Dict[str, List[Any]]):
        """
        Initialize dependency analyzer.
        
        Args:
            all_repo_data: Dictionary mapping repo_id to list of metadata items
        """
        self.all_repo_data = all_repo_data
        self.import_graph = {}
        self.api_call_graph = {}
        self.service_mesh = {}
    
    def analyze_all_dependencies(self) -> Dict[str, Any]:
        """
        Run all dependency analyses.
        
        Returns:
            Comprehensive dependency graph
        """
        logger.info("🔍 Analyzing cross-repo dependencies...")
        
        self.analyze_import_graph()
        self.analyze_api_calls()
        self.analyze_service_mesh()
        
        return {
            "imports": self.import_graph,
            "api_calls": self.api_call_graph,
            "service_mesh": self.service_mesh
        }
    
    def analyze_import_graph(self):
        """
        Build import graph across repos.
        Analyzes package imports from:
        - Node (package.json dependencies)
        - Rust (Cargo.toml dependencies)
        - Python (import statements)
        """
        logger.info("  📦 Analyzing import graph...")
        
        for repo_id, metadata_items in self.all_repo_data.items():
            self.import_graph[repo_id] = {
                "imports_from": [],
                "imported_by": []
            }
            
            # Analyze each metadata item
            for item in metadata_items:
                # Extract imports from metadata
                if hasattr(item, 'imports') and item.imports:
                    for imported_package in item.imports:
                        if self._is_internal_package(imported_package):
                            self.import_graph[repo_id]["imports_from"].append(imported_package)
                
                # Analyze package.json files
                if item.file_path.endswith('package.json'):
                    deps = self._analyze_package_json(item.full_content)
                    self.import_graph[repo_id]["imports_from"].extend(deps)
                
                # Analyze Cargo.toml files
                elif item.file_path.endswith('Cargo.toml'):
                    deps = self._analyze_cargo_toml(item.full_content)
                    self.import_graph[repo_id]["imports_from"].extend(deps)
                
                # Analyze Python files
                elif item.language == 'python':
                    imports = self._extract_python_imports(item.full_content)
                    for imp in imports:
                        if self._is_internal_package(imp):
                            self.import_graph[repo_id]["imports_from"].append(imp)
            
            # Remove duplicates
            self.import_graph[repo_id]["imports_from"] = list(set(
                self.import_graph[repo_id]["imports_from"]
            ))
        
        # Build reverse mapping (imported_by)
        for repo_id, data in self.import_graph.items():
            for imported_package in data["imports_from"]:
                # Find which repo provides this package
                for other_repo_id in self.all_repo_data.keys():
                    if imported_package in other_repo_id:
                        if other_repo_id in self.import_graph:
                            self.import_graph[other_repo_id]["imported_by"].append(repo_id)
    
    def analyze_api_calls(self):
        """
        Find API endpoint consumers.
        Detects:
        - HTTP calls to other services (fetch, axios, reqwest)
        - API base paths called
        """
        logger.info("  🌐 Analyzing API calls...")
        
        for repo_id, metadata_items in self.all_repo_data.items():
            self.api_call_graph[repo_id] = {
                "calls": [],  # APIs this service calls
                "called_by": []  # Services that call this service's APIs
            }
            
            for item in metadata_items:
                content = item.full_content
                
                # Analyze TypeScript/JavaScript HTTP calls
                if item.language in ['typescript', 'javascript', 'tsx', 'jsx']:
                    api_calls = self._extract_js_api_calls(content)
                    self.api_call_graph[repo_id]["calls"].extend(api_calls)
                
                # Analyze Rust HTTP calls
                elif item.language == 'rust':
                    api_calls = self._extract_rust_api_calls(content)
                    self.api_call_graph[repo_id]["calls"].extend(api_calls)
                
                # Analyze Python HTTP calls
                elif item.language == 'python':
                    api_calls = self._extract_python_api_calls(content)
                    self.api_call_graph[repo_id]["calls"].extend(api_calls)
            
            # Remove duplicates
            self.api_call_graph[repo_id]["calls"] = [
                dict(t) for t in {tuple(d.items()) for d in self.api_call_graph[repo_id]["calls"]}
            ]
    
    def analyze_service_mesh(self):
        """
        Extract service mesh from Helm charts and K8s manifests.
        Maps:
        - Which services exist
        - How they communicate
        - Network policies
        """
        logger.info("  🕸️  Analyzing service mesh...")
        
        for repo_id, metadata_items in self.all_repo_data.items():
            self.service_mesh[repo_id] = {
                "services": [],
                "endpoints": [],
                "dependencies": []
            }
            
            for item in metadata_items:
                # Analyze Helm charts
                if item.item_type == 'helm_chart':
                    if hasattr(item, 'helm_chart_name') and item.helm_chart_name:
                        self.service_mesh[repo_id]["services"].append(item.helm_chart_name)
                    
                    if hasattr(item, 'depends_on_services') and item.depends_on_services:
                        self.service_mesh[repo_id]["dependencies"].extend(item.depends_on_services)
                
                # Analyze K8s Service resources
                elif item.item_type == 'k8s_resource' and item.k8s_resource_type == 'Service':
                    service_info = {
                        'name': item.item_name,
                        'ports': item.ports if hasattr(item, 'ports') else []
                    }
                    self.service_mesh[repo_id]["services"].append(service_info)
                
                # Analyze API endpoints from metadata
                elif hasattr(item, 'api_endpoints') and item.api_endpoints:
                    self.service_mesh[repo_id]["endpoints"].extend(item.api_endpoints)
    
    def _analyze_package_json(self, content: str) -> List[str]:
        """Extract dependencies from package.json."""
        try:
            data = json.loads(content)
            deps = list(data.get('dependencies', {}).keys())
            
            # Filter for internal packages
            return [d for d in deps if self._is_internal_package(d)]
        except Exception as e:
            logger.debug(f"Failed to parse package.json: {e}")
            return []
    
    def _analyze_cargo_toml(self, content: str) -> List[str]:
        """Extract dependencies from Cargo.toml."""
        deps = []
        try:
            # Simple regex-based parsing (full TOML parser would be better)
            in_dependencies = False
            for line in content.split('\n'):
                if line.strip() == '[dependencies]':
                    in_dependencies = True
                    continue
                
                if in_dependencies:
                    if line.startswith('['):
                        break
                    
                    # Parse dependency line
                    match = re.match(r'^(\w+)\s*=', line)
                    if match:
                        dep_name = match.group(1)
                        if self._is_internal_package(dep_name):
                            deps.append(dep_name)
        
        except Exception as e:
            logger.debug(f"Failed to parse Cargo.toml: {e}")
        
        return deps
    
    def _extract_python_imports(self, content: str) -> List[str]:
        """Extract import statements from Python code."""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except Exception as e:
            logger.debug(f"Failed to parse Python imports: {e}")
        
        return imports
    
    def _extract_js_api_calls(self, content: str) -> List[Dict[str, str]]:
        """Extract API calls from JavaScript/TypeScript code."""
        api_calls = []
        
        # Patterns for HTTP client calls
        patterns = [
            r'fetch\s*\(\s*["\']([^"\']+)["\']',
            r'axios\.\w+\s*\(\s*["\']([^"\']+)["\']',
            r'\.get\s*\(\s*["\']([^"\']+)["\']',
            r'\.post\s*\(\s*["\']([^"\']+)["\']',
            r'\.put\s*\(\s*["\']([^"\']+)["\']',
            r'\.delete\s*\(\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for url in matches:
                # Check if it's an internal API or contains service names
                if '/api/' in url or any(service in url for service in self.all_repo_data.keys()):
                    api_calls.append({
                        'url': url,
                        'type': 'http'
                    })
        
        return api_calls
    
    def _extract_rust_api_calls(self, content: str) -> List[Dict[str, str]]:
        """Extract API calls from Rust code."""
        api_calls = []
        
        # Patterns for Rust HTTP clients (reqwest, etc.)
        patterns = [
            r'\.get\s*\(\s*"([^"]+)"',
            r'\.post\s*\(\s*"([^"]+)"',
            r'reqwest::get\s*\(\s*"([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for url in matches:
                if '/api/' in url or any(service in url for service in self.all_repo_data.keys()):
                    api_calls.append({
                        'url': url,
                        'type': 'http'
                    })
        
        return api_calls
    
    def _extract_python_api_calls(self, content: str) -> List[Dict[str, str]]:
        """Extract API calls from Python code."""
        api_calls = []
        
        # Patterns for Python HTTP clients (requests, httpx, etc.)
        patterns = [
            r'requests\.\w+\s*\(\s*["\']([^"\']+)["\']',
            r'httpx\.\w+\s*\(\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for url in matches:
                if '/api/' in url or any(service in url for service in self.all_repo_data.keys()):
                    api_calls.append({
                        'url': url,
                        'type': 'http'
                    })
        
        return api_calls
    
    def _is_internal_package(self, package_name: str) -> bool:
        """Check if package is an internal package (in all_repo_data)."""
        # Internal if it matches a known repo id
        return package_name in self.all_repo_data

