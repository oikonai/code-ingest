"""
TypeScript AST Parser

Single responsibility: Parse TypeScript/React source files using tree-sitter to extract 
syntactically coherent code units (functions, classes, interfaces, types, components).

Following AGENTS.md guidelines:
- Under 400 lines
- OOP-first design
- Single responsibility principle
- Modular and reusable
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class TypeScriptCodeChunk:
    """Represents a syntactically coherent TypeScript code chunk."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    item_name: str
    item_type: str  # function, class, interface, type, component, hook, const, export
    imports: List[str]
    exports: List[str]
    metadata: Dict[str, Any]

@dataclass
class TypeScriptParseResult:
    """Result of parsing a TypeScript file."""
    success: bool
    chunks: List[TypeScriptCodeChunk]
    error_message: Optional[str] = None
    total_lines: int = 0
    parsed_items: int = 0

class TypeScriptASTParser:
    """
    TypeScript AST parser using tree-sitter for syntactically accurate parsing.
    
    Extracts: React components, functions, classes, interfaces, types, hooks, exports
    """
    
    def __init__(self):
        """Initialize the TypeScript parser."""
        self.tree_sitter_available = False
        self.ts_language = None
        self.parser = None
        
        # Try to initialize tree-sitter for TypeScript
        try:
            import tree_sitter
            import tree_sitter_typescript as ts_ts
            
            ts_language_capsule = ts_ts.language_typescript()
            self.ts_language = tree_sitter.Language(ts_language_capsule)
            self.parser = tree_sitter.Parser(self.ts_language)
            self.tree_sitter_available = True
            logger.info("✅ Tree-sitter TypeScript parser initialized")
            
        except Exception as e:
            logger.warning(f"⚠️ Tree-sitter TypeScript unavailable: {e}")
            logger.warning("tree-sitter not available, falling back to regex parsing")
            self.tree_sitter_available = False
    
    def parse_file(self, file_path: str, content: str, repo_id: str) -> TypeScriptParseResult:
        """Parse a TypeScript file and extract code chunks."""
        try:
            if self.tree_sitter_available:
                return self._parse_with_tree_sitter(file_path, content, repo_id)
            else:
                return self._parse_with_regex(file_path, content, repo_id)
        except Exception as e:
            logger.error(f"❌ Failed to parse {file_path}: {e}")
            return TypeScriptParseResult(
                success=False,
                chunks=[],
                error_message=str(e),
                total_lines=len(content.split('\n'))
            )
    
    def _parse_with_tree_sitter(self, file_path: str, content: str, repo_id: str) -> TypeScriptParseResult:
        """Parse using tree-sitter AST."""
        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node
            
            chunks = []
            lines = content.split('\n')
            
            # Extract top-level items
            for child in root_node.children:
                chunk = self._extract_ts_chunk(child, content, lines, file_path, repo_id)
                if chunk:
                    chunks.append(chunk)
            
            return TypeScriptParseResult(
                success=True,
                chunks=chunks,
                total_lines=len(lines),
                parsed_items=len(chunks)
            )
            
        except Exception as e:
            logger.error(f"❌ Tree-sitter parsing failed for {file_path}: {e}")
            return self._parse_with_regex(file_path, content, repo_id)
    
    def _extract_ts_chunk(self, node, content: str, lines: List[str], 
                         file_path: str, repo_id: str) -> Optional[TypeScriptCodeChunk]:
        """Extract a TypeScript chunk from a tree-sitter node."""
        node_type = node.type
        
        # Map tree-sitter node types to our chunk types
        type_mapping = {
            'function_declaration': 'function',
            'arrow_function': 'arrow_function',
            'class_declaration': 'class',
            'interface_declaration': 'interface',
            'type_alias_declaration': 'type',
            'enum_declaration': 'enum',
            'export_statement': 'export',
            'const_declaration': 'const',
            'let_declaration': 'let',
            'var_declaration': 'var',
            'method_definition': 'method'
        }
        
        if node_type not in type_mapping:
            return None
            
        start_byte = node.start_byte
        end_byte = node.end_byte
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        chunk_content = content[start_byte:end_byte]
        
        # Skip very small chunks
        if len(chunk_content.strip()) < 30:
            return None
            
        # Extract item name
        item_name = self._extract_item_name(node, chunk_content)
        
        # Determine if this is a React component
        item_type = self._classify_item_type(chunk_content, type_mapping[node_type])
        
        return TypeScriptCodeChunk(
            file_path=file_path,
            content=chunk_content,
            start_line=start_line + 1,
            end_line=end_line + 1,
            item_name=item_name,
            item_type=item_type,
            imports=self._extract_imports(chunk_content),
            exports=self._extract_exports(chunk_content),
            metadata={
                'repo_id': repo_id,
                'complexity_score': min(len(chunk_content) / 100, 10.0),
                'line_count': end_line - start_line + 1,
                'has_jsx': '<' in chunk_content and 'React' in chunk_content
            }
        )
    
    def _extract_item_name(self, node, content: str) -> str:
        """Extract the name of the item from the AST node."""
        # Try to find identifier nodes
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        
        # Fallback to regex extraction
        patterns = [
            r'function\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'const\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'class\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'interface\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'type\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'enum\s+([A-Za-z_$][A-Za-z0-9_$]*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
                
        return "unnamed_item"
    
    def _classify_item_type(self, content: str, base_type: str) -> str:
        """Classify the item type more specifically."""
        content_lower = content.lower()
        
        # Check for React patterns
        if any(pattern in content for pattern in ['React.', 'JSX.', '</', 'useState', 'useEffect']):
            if base_type in ['function', 'arrow_function', 'const']:
                return 'react_component'
        
        # Check for custom hooks
        if base_type == 'function' and content.startswith('use') and content[3].isupper():
            return 'custom_hook'
            
        # Check for API services
        if 'async' in content_lower and ('fetch' in content_lower or 'api' in content_lower):
            return 'api_service'
            
        return base_type
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements from content."""
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"];?'
        return re.findall(import_pattern, content)
    
    def _extract_api_endpoints(self, content: str) -> List[Dict[str, str]]:
        """
        Extract API endpoints from Express/Next.js routes.
        
        Args:
            content: Chunk content
            
        Returns:
            List of API endpoint dicts with method and path
        """
        endpoints = []
        
        # Express.js patterns
        express_patterns = [
            (r'router\.get\([\'"]([^\'"]+)[\'"]\s*,', 'GET'),
            (r'router\.post\([\'"]([^\'"]+)[\'"]\s*,', 'POST'),
            (r'router\.put\([\'"]([^\'"]+)[\'"]\s*,', 'PUT'),
            (r'router\.delete\([\'"]([^\'"]+)[\'"]\s*,', 'DELETE'),
            (r'router\.patch\([\'"]([^\'"]+)[\'"]\s*,', 'PATCH'),
            (r'app\.get\([\'"]([^\'"]+)[\'"]\s*,', 'GET'),
            (r'app\.post\([\'"]([^\'"]+)[\'"]\s*,', 'POST'),
            (r'app\.put\([\'"]([^\'"]+)[\'"]\s*,', 'PUT'),
            (r'app\.delete\([\'"]([^\'"]+)[\'"]\s*,', 'DELETE'),
        ]
        
        for pattern, method in express_patterns:
            matches = re.findall(pattern, content)
            for path in matches:
                endpoints.append({
                    'method': method,
                    'path': path,
                    'framework': 'express'
                })
        
        # Next.js API routes (based on file path)
        if '/api/' in content or 'NextApiRequest' in content:
            # Export handler detection
            if 'export default' in content or 'export async function' in content:
                # Method detection from handler
                if 'req.method' in content:
                    method_matches = re.findall(r'req\.method\s*===\s*[\'"](\w+)[\'"]', content)
                    for method in method_matches:
                        endpoints.append({
                            'method': method,
                            'path': 'detected_from_file_path',
                            'framework': 'nextjs'
                        })
        
        return endpoints
    
    def _extract_api_consumption(self, content: str) -> List[str]:
        """
        Extract external API calls (fetch, axios, etc.).
        
        Args:
            content: Chunk content
            
        Returns:
            List of API URLs or service names
        """
        api_calls = []
        
        # Fetch patterns
        fetch_pattern = r'fetch\([\'"]([^\'"]+)[\'"]'
        fetch_matches = re.findall(fetch_pattern, content)
        api_calls.extend(fetch_matches)
        
        # Axios patterns
        axios_patterns = [
            r'axios\.get\([\'"]([^\'"]+)[\'"]',
            r'axios\.post\([\'"]([^\'"]+)[\'"]',
            r'axios\(\s*[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in axios_patterns:
            matches = re.findall(pattern, content)
            api_calls.extend(matches)
        
        # Limit and clean
        return list(set(api_calls))[:10]
    
    def _detect_react_component_dependencies(self, content: str, imports: List[str]) -> List[str]:
        """
        Extract React component dependencies from imports.
        
        Args:
            content: Chunk content
            imports: Imported modules
            
        Returns:
            List of component dependencies
        """
        component_imports = []
        
        # Look for component-like imports (PascalCase)
        for imp in imports:
            # Extract component names from import statements
            component_matches = re.findall(r'\b([A-Z][a-zA-Z0-9]*(?:Component)?)\b', imp)
            component_imports.extend(component_matches)
        
        return list(set(component_imports))[:15]
    
    def enhance_chunk_metadata(self, chunk) -> Any:
        """
        Enhance TypeScript chunk with additional metadata.
        
        Args:
            chunk: TypeScriptCodeChunk to enhance
            
        Returns:
            Enhanced chunk
        """
        content = chunk.content
        
        # Extract API endpoints
        api_endpoints = self._extract_api_endpoints(content)
        if api_endpoints:
            chunk.metadata['api_endpoints'] = api_endpoints
        
        # Extract API consumption
        api_consumes = self._extract_api_consumption(content)
        if api_consumes:
            chunk.metadata['api_consumes'] = api_consumes
        
        # Extract imports if available
        imports = chunk.imports if hasattr(chunk, 'imports') and chunk.imports else []
        if imports:
            chunk.metadata['imports'] = imports[:15]
            
            # Extract component dependencies for React
            if chunk.item_type == 'react_component':
                component_deps = self._detect_react_component_dependencies(content, imports)
                if component_deps:
                    chunk.metadata['component_dependencies'] = component_deps
        
        return chunk
    
    def _extract_exports(self, content: str) -> List[str]:
        """Extract export statements from content."""
        export_patterns = [
            r'export\s+(?:default\s+)?(?:function|const|class|interface|type)\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'export\s+\{\s*([^}]+)\s*\}'
        ]
        
        exports = []
        for pattern in export_patterns:
            matches = re.findall(pattern, content)
            exports.extend(matches)
        
        return exports
    
    def _parse_with_regex(self, file_path: str, content: str, repo_id: str) -> TypeScriptParseResult:
        """Fallback regex parsing when tree-sitter is unavailable."""
        chunks = []
        lines = content.split('\n')
        
        # Enhanced patterns based on arda-credit-app analysis
        patterns = [
            # React function components
            (r'^export\s+function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{', 'react_component'),
            (r'^export\s+default\s+function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{', 'react_component'),
            (r'^const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*\([^)]*\)\s*=>\s*[({]', 'react_component'),
            (r'^const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*React\.forwardRef<[^>]+>\s*\(', 'react_component'),
            
            # Custom hooks
            (r'^export\s+function\s+(use[A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{', 'custom_hook'),
            (r'^export\s+const\s+(use[A-Z][a-zA-Z0-9]*)\s*=\s*\([^)]*\)\s*=>', 'custom_hook'),
            
            # TypeScript interfaces and types
            (r'^export\s+interface\s+([A-Z][a-zA-Z0-9]*)\s*\{', 'interface'),
            (r'^interface\s+([A-Z][a-zA-Z0-9]*Props)\s*\{', 'props_interface'),
            (r'^export\s+type\s+([A-Z][a-zA-Z0-9]*)\s*=', 'type_alias'),
            (r'^type\s+([A-Z][a-zA-Z0-9]*)\s*=', 'type_alias'),
            
            # Regular functions and constants
            (r'^export\s+const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=', 'export_const'),
            (r'^export\s+function\s+([a-z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{', 'function'),
            (r'^function\s+([a-z][a-zA-Z0-9]*)\s*\([^)]*\)\s*\{', 'function'),
            
            # API and service patterns
            (r'^export\s+const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\{[^}]*async', 'api_service'),
        ]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            for pattern, item_type in patterns:
                match = re.search(pattern, line)
                if match:
                    chunk = self._extract_regex_chunk(
                        lines, i, match, item_type, file_path, repo_id
                    )
                    if chunk:
                        chunks.append(chunk)
                        i = min(chunk.end_line - 1, len(lines) - 1)
                    break
            else:
                i += 1
        
        # If no patterns matched, create a whole-file chunk for substantial files
        if not chunks and len(content.strip()) > 100:
            chunks.append(TypeScriptCodeChunk(
                file_path=file_path,
                content=content,
                start_line=1,
                end_line=len(lines),
                item_name=Path(file_path).stem,
                item_type='file',
                imports=self._extract_imports(content),
                exports=self._extract_exports(content),
                metadata={
                    'repo_id': repo_id,
                    'complexity_score': min(len(content) / 200, 10.0),
                    'line_count': len(lines),
                    'fallback_whole_file': True
                }
            ))
        
        return TypeScriptParseResult(
            success=True,
            chunks=chunks,
            total_lines=len(lines),
            parsed_items=len(chunks)
        )
    
    def _extract_regex_chunk(self, lines: List[str], start_idx: int, match, 
                           item_type: str, file_path: str, repo_id: str) -> Optional[TypeScriptCodeChunk]:
        """Extract a chunk using regex matching."""
        item_name = match.group(1) if match.group(1) else f"unnamed_{item_type}"
        
        # Find chunk boundaries using brace matching
        chunk_lines = [lines[start_idx]]
        brace_count = lines[start_idx].count('{') - lines[start_idx].count('}')
        
        end_idx = start_idx
        for i in range(start_idx + 1, min(len(lines), start_idx + 200)):
            chunk_lines.append(lines[i])
            brace_count += lines[i].count('{') - lines[i].count('}')
            end_idx = i
            
            if brace_count <= 0 and '{' in lines[start_idx]:
                break
            elif item_type in ['interface', 'type_alias'] and ';' in lines[i]:
                break
        
        chunk_content = '\n'.join(chunk_lines)
        
        # Skip very small chunks
        if len(chunk_content.strip()) < 30:
            return None
        
        return TypeScriptCodeChunk(
            file_path=file_path,
            content=chunk_content,
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            item_name=item_name,
            item_type=item_type,
            imports=self._extract_imports(chunk_content),
            exports=self._extract_exports(chunk_content),
            metadata={
                'repo_id': repo_id,
                'complexity_score': min(len(chunk_content) / 100, 10.0),
                'line_count': end_idx - start_idx + 1,
                'has_jsx': '<' in chunk_content and any(jsx in chunk_content for jsx in ['React', 'JSX', '<div', '<span'])
            }
        )
    
    def validate_chunk(self, chunk: TypeScriptCodeChunk) -> bool:
        """Validate that a chunk meets quality standards."""
        if len(chunk.content.strip()) < 30:
            return False
            
        if chunk.end_line <= chunk.start_line:
            return False
            
        # Check for reasonable token count (< 30K for embedding model)
        estimated_tokens = len(chunk.content.split()) * 1.3
        if estimated_tokens > 30000:
            logger.warning(f"⚠️ Chunk {chunk.item_name} too large: ~{estimated_tokens:.0f} tokens")
            return False
            
        return True