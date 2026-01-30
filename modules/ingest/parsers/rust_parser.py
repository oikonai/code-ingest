"""
Rust AST Parser

Single responsibility: Parse Rust source files using tree-sitter to extract 
syntactically coherent code units (fn, struct, enum, impl, trait, mod).

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
class RustCodeChunk:
    """Represents a syntactically coherent Rust code chunk."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    item_name: str
    item_type: str  # fn, struct, enum, trait, impl, mod, const, static, type
    use_statements: List[str]
    doc_comments: List[str]
    metadata: Dict[str, Any]

@dataclass
class ParseResult:
    """Result of parsing a Rust file."""
    success: bool
    chunks: List[RustCodeChunk]
    error_message: Optional[str] = None
    total_lines: int = 0
    parsed_items: int = 0

class RustASTParser:
    """
    Rust AST parser using tree-sitter for syntactically accurate parsing.
    
    Extracts top-level items: fn, struct, enum, impl, trait, mod, const, static, type
    Includes relevant use statements and doc comments for each chunk.
    """
    
    def __init__(self):
        """Initialize the Rust AST parser."""
        self.tree_sitter_available = self._check_tree_sitter()
        if not self.tree_sitter_available:
            logger.warning("tree-sitter not available, falling back to regex parsing")
    
    def _check_tree_sitter(self) -> bool:
        """Check if tree-sitter and tree-sitter-rust are available."""
        try:
            import tree_sitter
            import tree_sitter_rust as ts_rust
            rust_language = tree_sitter.Language(ts_rust.language())
            return True
        except Exception as e:
            logger.warning(f"Tree-sitter unavailable: {e}")
            return False
    
    def parse_file(self, file_path: str, content: str, repo_id: str) -> ParseResult:
        """
        Parse a Rust file and extract code chunks.
        
        Args:
            file_path: Path to the Rust file
            content: File content as string
            repo_id: Repository identifier
            
        Returns:
            ParseResult with extracted chunks or error information
        """
        if not content.strip():
            return ParseResult(success=False, chunks=[], error_message="Empty file")
        
        try:
            if self.tree_sitter_available:
                return self._parse_with_tree_sitter(file_path, content, repo_id)
            else:
                return self._parse_with_regex(file_path, content, repo_id)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return ParseResult(
                success=False, 
                chunks=[], 
                error_message=str(e),
                total_lines=len(content.split('\n'))
            )
    
    def _parse_with_tree_sitter(self, file_path: str, content: str, repo_id: str) -> ParseResult:
        """Parse using tree-sitter for accurate AST analysis."""
        import tree_sitter
        import tree_sitter_rust
        
        # Initialize parser using tree-sitter-rust directly  
        import tree_sitter_rust as ts_rust
        
        rust_language = tree_sitter.Language(ts_rust.language())
        parser = tree_sitter.Parser(rust_language)
        
        # Parse content
        tree = parser.parse(bytes(content, 'utf-8'))
        root_node = tree.root_node
        
        if root_node.has_error:
            return ParseResult(
                success=False,
                chunks=[],
                error_message="Syntax errors in Rust file",
                total_lines=len(content.split('\n'))
            )
        
        # Extract use statements for context
        use_statements = self._extract_use_statements(root_node, content)
        
        # Extract top-level items
        chunks = []
        for child in root_node.children:
            chunk = self._process_tree_sitter_node(
                child, content, file_path, repo_id, use_statements
            )
            if chunk:
                chunks.append(chunk)
        
        return ParseResult(
            success=True,
            chunks=chunks,
            total_lines=len(content.split('\n')),
            parsed_items=len(chunks)
        )
    
    def _extract_use_statements(self, root_node, content: str) -> List[str]:
        """Extract use statements from the root node."""
        use_statements = []
        
        def find_use_statements(node):
            if node.type == 'use_declaration':
                use_text = content[node.start_byte:node.end_byte]
                use_statements.append(use_text.strip())
            
            for child in node.children:
                find_use_statements(child)
        
        find_use_statements(root_node)
        return use_statements[:10]  # Limit to avoid bloat
    
    def _process_tree_sitter_node(self, node, content: str, file_path: str, 
                                 repo_id: str, use_statements: List[str]) -> Optional[RustCodeChunk]:
        """Process a tree-sitter node into a code chunk."""
        # Map tree-sitter node types to our item types
        node_type_map = {
            'function_item': 'fn',
            'struct_item': 'struct', 
            'enum_item': 'enum',
            'trait_item': 'trait',
            'impl_item': 'impl',
            'mod_item': 'mod',
            'const_item': 'const',
            'static_item': 'static',
            'type_item': 'type'
        }
        
        if node.type not in node_type_map:
            return None
        
        item_type = node_type_map[node.type]
        
        # Extract content
        chunk_content = content[node.start_byte:node.end_byte]
        
        # Calculate line numbers
        content_before = content[:node.start_byte]
        start_line = content_before.count('\n') + 1
        end_line = start_line + chunk_content.count('\n')
        
        # Extract item name
        item_name = self._extract_item_name(node, content, item_type)
        
        # Extract doc comments
        doc_comments = self._extract_doc_comments(node, content)
        
        # Include relevant use statements
        relevant_uses = self._filter_relevant_uses(use_statements, chunk_content)
        
        # Add use statements to chunk if not already present
        if relevant_uses and not any(use in chunk_content for use in relevant_uses):
            chunk_content = '\n'.join(relevant_uses[:3]) + '\n\n' + chunk_content
        
        return RustCodeChunk(
            file_path=file_path,
            content=chunk_content,
            start_line=start_line,
            end_line=end_line,
            item_name=item_name,
            item_type=item_type,
            use_statements=relevant_uses,
            doc_comments=doc_comments,
            metadata={
                'visibility': self._extract_visibility(node, content),
                'is_async': 'async' in chunk_content[:50],
                'is_unsafe': 'unsafe' in chunk_content[:50],
                'line_count': end_line - start_line + 1,
                'byte_size': len(chunk_content)
            }
        )
    
    def _extract_item_name(self, node, content: str, item_type: str) -> str:
        """Extract the name of a Rust item from its AST node."""
        # Look for identifier nodes
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
            elif child.type == 'type_identifier':
                return content[child.start_byte:child.end_byte]
        
        # Fallback to regex extraction
        chunk_text = content[node.start_byte:node.end_byte]
        import re
        
        patterns = {
            'fn': r'fn\s+(\w+)',
            'struct': r'struct\s+(\w+)',
            'enum': r'enum\s+(\w+)', 
            'trait': r'trait\s+(\w+)',
            'impl': r'impl(?:\s*<[^>]*>)?\s+(?:(\w+)|.*?for\s+(\w+))',
            'mod': r'mod\s+(\w+)',
            'const': r'const\s+(\w+)',
            'static': r'static\s+(\w+)',
            'type': r'type\s+(\w+)'
        }
        
        if item_type in patterns:
            match = re.search(patterns[item_type], chunk_text)
            if match:
                return match.group(1) or match.group(2) if match.lastindex > 1 else match.group(1)
        
        return f"unnamed_{item_type}"
    
    def _extract_doc_comments(self, node, content: str) -> List[str]:
        """Extract documentation comments for an item."""
        doc_comments = []
        
        # Look for comment nodes before this item
        if hasattr(node, 'prev_sibling') and node.prev_sibling:
            prev = node.prev_sibling
            if prev.type == 'line_comment' and content[prev.start_byte:prev.end_byte].startswith('///'):
                comment_text = content[prev.start_byte:prev.end_byte]
                doc_comments.append(comment_text.strip())
        
        return doc_comments
    
    def _extract_visibility(self, node, content: str) -> str:
        """Extract visibility modifier (pub, pub(crate), etc.)."""
        chunk_text = content[node.start_byte:min(node.start_byte + 100, node.end_byte)]
        
        if chunk_text.strip().startswith('pub(crate)'):
            return 'pub(crate)'
        elif chunk_text.strip().startswith('pub'):
            return 'pub'
        else:
            return 'private'
    
    def _filter_relevant_uses(self, use_statements: List[str], chunk_content: str) -> List[str]:
        """Filter use statements that are relevant to the chunk."""
        relevant = []
        
        for use_stmt in use_statements:
            # Extract the imported items/modules
            if '::' in use_stmt:
                parts = use_stmt.replace('use ', '').replace(';', '').split('::')
                for part in parts:
                    clean_part = part.strip().split(' ')[0].split('{')[0]
                    if clean_part and clean_part in chunk_content:
                        relevant.append(use_stmt)
                        break
        
        return relevant[:5]  # Limit to avoid bloat
    
    def _parse_with_regex(self, file_path: str, content: str, repo_id: str) -> ParseResult:
        """Fallback regex-based parsing when tree-sitter is not available."""
        import re
        
        chunks = []
        lines = content.split('\n')
        
        # Extract use statements
        use_statements = []
        for line in lines:
            if line.strip().startswith('use ') and line.strip().endswith(';'):
                use_statements.append(line.strip())
        
        # Patterns for top-level items
        patterns = [
            (r'^(pub\s+)?fn\s+(\w+)', 'fn'),
            (r'^(pub\s+)?struct\s+(\w+)', 'struct'),
            (r'^(pub\s+)?enum\s+(\w+)', 'enum'),
            (r'^(pub\s+)?trait\s+(\w+)', 'trait'),
            (r'^impl(?:\s*<[^>]*>)?\s+(?:(\w+)|.*?for\s+(\w+))', 'impl'),
            (r'^(pub\s+)?mod\s+(\w+)', 'mod'),
            (r'^(pub\s+)?const\s+(\w+)', 'const'),
            (r'^(pub\s+)?static\s+(\w+)', 'static'),
            (r'^(pub\s+)?type\s+(\w+)', 'type')
        ]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            for pattern, item_type in patterns:
                match = re.match(pattern, line)
                if match:
                    chunk = self._extract_regex_chunk(
                        lines, i, match, item_type, file_path, use_statements
                    )
                    if chunk:
                        chunks.append(chunk)
                        i = chunk.end_line  # Skip to end of this item
                    break
            else:
                i += 1
        
        return ParseResult(
            success=True,
            chunks=chunks,
            total_lines=len(lines),
            parsed_items=len(chunks)
        )
    
    def _extract_regex_chunk(self, lines: List[str], start_idx: int, match, 
                           item_type: str, file_path: str, use_statements: List[str]) -> Optional[RustCodeChunk]:
        """Extract a chunk using regex-based parsing."""
        item_name = match.group(2) if match.lastindex >= 2 else match.group(1)
        if not item_name:
            item_name = f"unnamed_{item_type}"
        
        # Find the end of this item (simple brace matching)
        chunk_lines = [lines[start_idx]]
        brace_count = lines[start_idx].count('{') - lines[start_idx].count('}')
        
        end_idx = start_idx
        for i in range(start_idx + 1, min(len(lines), start_idx + 200)):
            chunk_lines.append(lines[i])
            brace_count += lines[i].count('{') - lines[i].count('}')
            end_idx = i
            
            if brace_count <= 0 and '{' in lines[start_idx]:
                break
            elif item_type in ['const', 'static', 'type'] and lines[i].strip().endswith(';'):
                break
        
        chunk_content = '\n'.join(chunk_lines)
        
        # Add relevant use statements
        relevant_uses = self._filter_relevant_uses(use_statements, chunk_content)
        if relevant_uses:
            chunk_content = '\n'.join(relevant_uses[:3]) + '\n\n' + chunk_content
        
        return RustCodeChunk(
            file_path=file_path,
            content=chunk_content,
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            item_name=item_name,
            item_type=item_type,
            use_statements=relevant_uses,
            doc_comments=[],  # Not extracted in regex mode
            metadata={
                'visibility': 'pub' if 'pub' in lines[start_idx] else 'private',
                'line_count': end_idx - start_idx + 1,
                'parsing_method': 'regex'
            }
        )
    
    def _extract_api_endpoints(self, content: str) -> List[Dict[str, str]]:
        """
        Extract API endpoints from Axum route handlers.
        
        Looks for attributes like #[get("/path")], #[post("/path")], etc.
        
        Args:
            content: Chunk content
            
        Returns:
            List of API endpoint dicts with method and path
        """
        endpoints = []
        
        # Pattern for Axum-style route attributes
        axum_patterns = [
            (r'#\[get\("([^"]+)"\)\]', 'GET'),
            (r'#\[post\("([^"]+)"\)\]', 'POST'),
            (r'#\[put\("([^"]+)"\)\]', 'PUT'),
            (r'#\[delete\("([^"]+)"\)\]', 'DELETE'),
            (r'#\[patch\("([^"]+)"\)\]', 'PATCH'),
        ]
        
        for pattern, method in axum_patterns:
            matches = re.findall(pattern, content)
            for path in matches:
                endpoints.append({
                    'method': method,
                    'path': path,
                    'framework': 'axum'
                })
        
        # Pattern for Actix-web style routes
        actix_patterns = [
            (r'\.route\("([^"]+)",\s*web::get\(\)', 'GET'),
            (r'\.route\("([^"]+)",\s*web::post\(\)', 'POST'),
            (r'\.route\("([^"]+)",\s*web::put\(\)', 'PUT'),
            (r'\.route\("([^"]+)",\s*web::delete\(\)', 'DELETE'),
        ]
        
        for pattern, method in actix_patterns:
            matches = re.findall(pattern, content)
            for path in matches:
                endpoints.append({
                    'method': method,
                    'path': path,
                    'framework': 'actix-web'
                })
        
        return endpoints
    
    def _extract_function_calls(self, content: str) -> List[str]:
        """
        Extract function calls from code content.
        
        Args:
            content: Chunk content
            
        Returns:
            List of function names called
        """
        # Pattern to find function calls (simplified)
        # Matches: function_name( or module::function(
        pattern = r'([a-z_][a-z0-9_]*(?:::[a-z_][a-z0-9_]*)*)\s*\('
        matches = re.findall(pattern, content.lower())
        
        # Filter out common keywords and self
        keywords = {'if', 'while', 'for', 'match', 'return', 'self', 'super'}
        function_calls = [m for m in matches if m not in keywords]
        
        # Remove duplicates and return
        return list(set(function_calls))
    
    def _detect_database_operations(self, content: str) -> bool:
        """
        Detect if chunk contains database operations.
        
        Args:
            content: Chunk content
            
        Returns:
            True if database operations detected
        """
        content_lower = content.lower()
        db_patterns = [
            'sqlx::', 'diesel::', 'tokio_postgres::',
            'query!', 'query_as!', 'execute!',
            'select ', 'insert ', 'update ', 'delete from'
        ]
        return any(pattern in content_lower for pattern in db_patterns)
    
    def _extract_imports_from_use_statements(self, use_statements: List[str]) -> List[str]:
        """
        Extract clean import names from use statements.
        
        Args:
            use_statements: List of use statement strings
            
        Returns:
            List of imported module/item names
        """
        imports = []
        for stmt in use_statements:
            # Extract the import path from "use path::to::item;"
            match = re.search(r'use\s+(.+?);', stmt)
            if match:
                import_path = match.group(1).strip()
                # Remove aliases (as X)
                import_path = re.sub(r'\s+as\s+\w+', '', import_path)
                imports.append(import_path)
        return imports
    
    def enhance_chunk_metadata(self, chunk: RustCodeChunk) -> RustCodeChunk:
        """
        Enhance chunk with additional metadata (API endpoints, dependencies, etc.).
        
        Args:
            chunk: Code chunk to enhance
            
        Returns:
            Enhanced chunk with additional metadata
        """
        # Extract API endpoints
        api_endpoints = self._extract_api_endpoints(chunk.content)
        if api_endpoints:
            chunk.metadata['api_endpoints'] = api_endpoints
        
        # Extract function dependencies
        function_calls = self._extract_function_calls(chunk.content)
        if function_calls:
            chunk.metadata['calls_functions'] = function_calls[:20]  # Limit to 20
        
        # Detect database operations
        if self._detect_database_operations(chunk.content):
            chunk.metadata['has_database_ops'] = True
        
        # Extract clean imports
        if chunk.use_statements:
            imports = self._extract_imports_from_use_statements(chunk.use_statements)
            chunk.metadata['imports'] = imports[:15]  # Limit to 15
        
        return chunk
    
    def validate_chunk(self, chunk: RustCodeChunk, max_tokens: int = 30000) -> bool:
        """
        Validate that a chunk meets the requirements.
        
        Args:
            chunk: The chunk to validate
            max_tokens: Maximum tokens allowed (≤30k to stay under 32k limit from PRD)
            
        Returns:
            True if chunk is valid, False otherwise
        """
        # More accurate token estimation for code (1 token ≈ 3-4 characters)
        estimated_tokens = len(chunk.content) // 3
        
        if estimated_tokens > max_tokens:
            logger.warning(f"Chunk {chunk.item_name} exceeds token limit: {estimated_tokens}")
            return False
        
        if not chunk.content.strip():
            return False
        
        if not chunk.item_name or chunk.item_name.isspace():
            return False
        
        return True