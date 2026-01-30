"""
Solidity AST Parser

Single responsibility: Parse Solidity smart contract files using tree-sitter to extract 
syntactically coherent code units (contracts, interfaces, libraries, functions, events, etc.).

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
class SolidityCodeChunk:
    """Represents a syntactically coherent Solidity code chunk."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    item_name: str
    item_type: str  # contract, interface, library, function, modifier, event, struct, enum, error
    imports: List[str]
    metadata: Dict[str, Any]

@dataclass
class SolidityParseResult:
    """Result of parsing a Solidity file."""
    success: bool
    chunks: List[SolidityCodeChunk]
    error_message: Optional[str] = None
    total_lines: int = 0
    parsed_items: int = 0

class SolidityASTParser:
    """
    Solidity AST parser using tree-sitter for syntactically accurate parsing.
    
    Extracts: contracts, interfaces, libraries, functions, modifiers, events, structs, enums, errors
    """
    
    def __init__(self):
        """Initialize the Solidity parser."""
        # Initialize tree-sitter for Solidity - no fallback allowed
        try:
            import tree_sitter
            import tree_sitter_solidity as ts_sol
            
            self.sol_language = tree_sitter.Language(ts_sol.language())
            self.parser = tree_sitter.Parser(self.sol_language)
            logger.info("✅ Tree-sitter Solidity parser initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize tree-sitter Solidity: {e}")
            raise RuntimeError(f"Tree-sitter Solidity is required but failed to initialize: {e}") from e
    
    def parse_file(self, file_path: str, content: str, repo_id: str) -> SolidityParseResult:
        """Parse a Solidity file and extract code chunks using tree-sitter AST."""
        try:
            return self._parse_with_tree_sitter(file_path, content, repo_id)
        except Exception as e:
            logger.error(f"❌ Failed to parse {file_path}: {e}")
            return SolidityParseResult(
                success=False,
                chunks=[],
                error_message=str(e),
                total_lines=len(content.split('\n'))
            )
    
    def _parse_with_tree_sitter(self, file_path: str, content: str, repo_id: str) -> SolidityParseResult:
        """Parse using tree-sitter AST."""
        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node
            
            chunks = []
            lines = content.split('\n')
            
            # Extract top-level items and nested items
            for child in root_node.children:
                chunk = self._extract_solidity_chunk(child, content, lines, file_path, repo_id)
                if chunk:
                    chunks.append(chunk)
                
                # For contracts, interfaces, and libraries, also extract their inner elements
                if child.type in ['contract_declaration', 'interface_declaration', 'library_declaration']:
                    for inner_child in child.children:
                        if inner_child.type == 'contract_body':
                            for body_child in inner_child.children:
                                inner_chunk = self._extract_solidity_chunk(body_child, content, lines, file_path, repo_id)
                                if inner_chunk:
                                    chunks.append(inner_chunk)
            
            return SolidityParseResult(
                success=True,
                chunks=chunks,
                total_lines=len(lines),
                parsed_items=len(chunks)
            )
            
        except Exception as e:
            logger.error(f"❌ Tree-sitter parsing failed for {file_path}: {e}")
            raise e  # No regex fallback - fail fast
    
    def _extract_solidity_chunk(self, node, content: str, lines: List[str], 
                               file_path: str, repo_id: str) -> Optional[SolidityCodeChunk]:
        """Extract a Solidity chunk from a tree-sitter node."""
        node_type = node.type
        
        # Map tree-sitter node types to our chunk types
        type_mapping = {
            'contract_declaration': 'contract',
            'interface_declaration': 'interface', 
            'library_declaration': 'library',
            'function_definition': 'function',
            'modifier_definition': 'modifier',
            'event_definition': 'event',
            'struct_definition': 'struct',
            'enum_definition': 'enum',
            'error_definition': 'error',
            'state_variable_declaration': 'state_variable',
            'constructor_definition': 'constructor',
            'fallback_receive_definition': 'fallback',
            'using_for_declaration': 'using_for'
        }
        
        if node_type not in type_mapping:
            return None
            
        start_byte = node.start_byte
        end_byte = node.end_byte
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        chunk_content = content[start_byte:end_byte]
        
        # Skip very small chunks
        if len(chunk_content.strip()) < 20:
            return None
            
        # Extract item name
        item_name = self._extract_solidity_item_name(node, chunk_content)
        
        # Classify item type more specifically
        item_type = self._classify_solidity_item_type(chunk_content, type_mapping[node_type])
        
        return SolidityCodeChunk(
            file_path=file_path,
            content=chunk_content,
            start_line=start_line + 1,
            end_line=end_line + 1,
            item_name=item_name,
            item_type=item_type,
            imports=self._extract_solidity_imports(chunk_content),
            metadata={
                'repo_id': repo_id,
                'complexity_score': min(len(chunk_content) / 80, 10.0),
                'line_count': end_line - start_line + 1,
                'is_library_code': self._is_library_code(file_path),
                'contract_type': self._detect_contract_type(chunk_content),
                'has_events': 'event ' in chunk_content,
                'has_modifiers': 'modifier ' in chunk_content,
                'has_inheritance': 'is ' in chunk_content or 'override' in chunk_content
            }
        )
    
    def _extract_solidity_item_name(self, node, content: str) -> str:
        """Extract the name of the Solidity item from the AST node."""
        # For different node types, the identifier is in different positions
        if node.type in ['contract_declaration', 'interface_declaration', 'library_declaration']:
            # Second child is usually the identifier (after 'contract'/'interface'/'library' keyword)
            for child in node.children:
                if child.type == 'identifier':
                    return content[child.start_byte:child.end_byte]
                    
        elif node.type in ['function_definition', 'modifier_definition']:
            # Second child is usually the identifier (after 'function'/'modifier' keyword)
            for child in node.children:
                if child.type == 'identifier':
                    return content[child.start_byte:child.end_byte]
                    
        elif node.type in ['event_definition', 'error_definition']:
            # Second child is usually the identifier (after 'event'/'error' keyword)
            for child in node.children:
                if child.type == 'identifier':
                    return content[child.start_byte:child.end_byte]
                    
        elif node.type in ['struct_definition', 'enum_definition']:
            # Second child is usually the identifier (after 'struct'/'enum' keyword)
            for child in node.children:
                if child.type == 'identifier':
                    return content[child.start_byte:child.end_byte]
                    
        elif node.type == 'constructor_definition':
            return 'constructor'
            
        elif node.type == 'state_variable_declaration':
            # For state variables, find the variable name (last identifier usually)
            identifiers = []
            for child in node.children:
                if child.type == 'identifier':
                    identifiers.append(content[child.start_byte:child.end_byte])
            if identifiers:
                return identifiers[-1]  # Last identifier is usually the variable name
        
        # Fallback: try to extract from content using regex
        node_content = content[node.start_byte:node.end_byte]
        patterns = [
            r'contract\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'interface\s+([A-Za-z_$][A-Za-z0-9_$]*)',  
            r'library\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'function\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'modifier\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'event\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'struct\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'enum\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'error\s+([A-Za-z_$][A-Za-z0-9_$]*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, node_content)
            if match:
                return match.group(1)
                
        return "unnamed_item"
    
    def _classify_solidity_item_type(self, content: str, base_type: str) -> str:
        """Classify the Solidity item type more specifically."""
        content_lower = content.lower()
        
        # Detect specific contract patterns
        if base_type == 'contract':
            if 'abstract contract' in content_lower:
                return 'abstract_contract'
            elif any(pattern in content_lower for pattern in ['erc20', 'erc721', 'erc1155']): 
                return 'token_contract'
            elif 'ownable' in content_lower or 'accesscontrol' in content_lower:
                return 'access_contract'
            elif 'proxy' in content_lower or 'upgradeable' in content_lower:
                return 'proxy_contract'
        
        # Detect function visibility and type
        elif base_type == 'function':
            if 'constructor' in content_lower:
                return 'constructor'
            elif 'external' in content_lower:
                return 'external_function'
            elif 'public' in content_lower:
                return 'public_function'
            elif 'internal' in content_lower:
                return 'internal_function'
            elif 'private' in content_lower:
                return 'private_function'
        
        return base_type
    
    def _extract_solidity_imports(self, content: str) -> List[str]:
        """Extract import statements from Solidity content."""
        import_pattern = r'import\s+.*?["\']([^"\']+)["\'];?'
        return re.findall(import_pattern, content)
    
    def _is_library_code(self, file_path: str) -> bool:
        """Detect if this is library/dependency code vs application code."""
        library_indicators = [
            'node_modules', 'lib/', 'libraries/', 'vendor/', 
            'openzeppelin', 'forge-std', 'sp1-contracts'
        ]
        return any(indicator in file_path.lower() for indicator in library_indicators)
    
    def _detect_contract_type(self, content: str) -> str:
        """Detect the type/purpose of the contract."""
        content_lower = content.lower()
        
        if any(token in content_lower for token in ['erc20', 'erc721', 'erc1155']):
            return 'token'
        elif any(gov in content_lower for gov in ['governor', 'voting', 'proposal']):
            return 'governance'
        elif any(defi in content_lower for defi in ['swap', 'pool', 'liquidity', 'lending']):
            return 'defi'
        elif any(access in content_lower for access in ['ownable', 'accesscontrol', 'roles']):
            return 'access_control'
        elif any(util in content_lower for util in ['library', 'utils', 'helper']):
            return 'utility'
        elif any(test in content_lower for test in ['test', 'mock', 'fake']):
            return 'test'
        else:
            return 'application'
    
    
    def validate_chunk(self, chunk: SolidityCodeChunk) -> bool:
        """Validate that a Solidity chunk meets quality standards."""
        if len(chunk.content.strip()) < 20:
            return False
            
        if chunk.end_line <= chunk.start_line:
            return False
        
        # Skip library code for core application focus
        if chunk.metadata.get('is_library_code', False):
            # Only keep important library interfaces/contracts
            important_patterns = ['interface', 'abstract', 'IERC', 'Ownable', 'AccessControl']
            if not any(pattern in chunk.content for pattern in important_patterns):
                return False
            
        # Check for reasonable token count (< 30K for embedding model)
        estimated_tokens = len(chunk.content.split()) * 1.3
        if estimated_tokens > 30000:
            logger.warning(f"⚠️ Solidity chunk {chunk.item_name} too large: ~{estimated_tokens:.0f} tokens")
            return False
            
        return True