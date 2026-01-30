"""
Documentation Parser for I2P System

Parses Markdown documentation files to extract architectural knowledge,
API documentation, system overviews, and implementation guidance that
provides critical context for meta-reasoning about existing systems.
"""

import logging
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import markdown
from markdown.extensions import toc, tables, fenced_code
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

@dataclass
class DocumentationChunk:
    """Represents a documentation chunk for vectorization."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    item_name: str
    item_type: str
    use_statements: list
    doc_comments: list
    metadata: Dict[str, Any]

class DocumentationParser:
    """
    Parser for Markdown documentation files that extracts structured
    architectural and implementation knowledge.
    """
    
    def __init__(self):
        # Initialize markdown parser with common extensions
        self.md = markdown.Markdown(extensions=[
            'toc',
            'tables', 
            'fenced_code',
            'codehilite'
        ])
        
        # Document type classification patterns
        self.doc_types = {
            'architecture': ['architecture', 'overview', 'design', 'system'],
            'api': ['api', 'endpoint', 'swagger', 'integration'],
            'authentication': ['auth', 'login', 'magic-link', 'session', 'jwt'],
            'deployment': ['deploy', 'setup', 'install', 'config'],
            'development': ['dev', 'contributing', 'coding', 'guidelines'],
            'integration': ['integration', 'guide', 'example', 'tutorial']
        }
        
        # Section importance weights for chunking
        self.section_weights = {
            'overview': 0.9,
            'architecture': 0.9, 
            'authentication': 0.8,
            'api': 0.8,
            'integration': 0.7,
            'setup': 0.6,
            'example': 0.5
        }
        
        logger.info("📚 Documentation parser initialized")
    
    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a markdown file into structured chunks for vectorization.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            List of document chunks with metadata
        """
        try:
            path_obj = Path(file_path)
            
            # Skip vendor/library documentation
            if self._should_skip_file(file_path):
                logger.debug(f"⏭️ Skipping vendor documentation: {file_path}")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.debug(f"⏭️ Skipping empty file: {file_path}")
                return []
            
            # Parse markdown structure
            html_content = self.md.convert(content)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract document metadata
            doc_metadata = self._extract_document_metadata(file_path, content)
            
            # Extract sections for intelligent chunking
            sections = self._extract_sections(content, soup)
            
            # Create chunks from sections
            chunks = self._create_chunks(sections, doc_metadata, file_path)
            
            logger.info(f"📖 Parsed {path_obj.name}: {len(chunks)} chunks, type: {doc_metadata['doc_type']}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Failed to parse documentation {file_path}: {e}")
            return []
    
    def _should_skip_file(self, file_path: str) -> bool:
        """Determine if a documentation file should be skipped"""
        skip_patterns = [
            # Third-party library docs
            '/lib/',
            '/node_modules/',
            '/vendor/',
            'openzeppelin-contracts',
            'forge-std',
            'sp1-contracts/contracts/lib',
            
            # Generated/temporary docs
            '/tmp/',
            '/build/',
            '/dist/',
            
            # Generic files
            'LICENSE',
            'CHANGELOG',
            'CONTRIBUTING.md',
            'CODE_OF_CONDUCT'
        ]
        
        return any(pattern in file_path for pattern in skip_patterns)
    
    def _extract_document_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
        """Extract metadata about the document type and context"""
        
        path_obj = Path(file_path)
        filename = path_obj.name.lower()
        
        # Determine document type
        doc_type = 'general'
        for doc_category, keywords in self.doc_types.items():
            if any(keyword in filename or keyword in content.lower()[:500] 
                   for keyword in keywords):
                doc_type = doc_category
                break
        
        # Extract repository context
        repo_component = self._extract_repo_component(file_path)
        business_domain = self._extract_business_domain(file_path, content)
        
        # Extract title from content
        title = self._extract_title(content) or path_obj.stem
        
        return {
            'doc_type': doc_type,
            'title': title,
            'filename': path_obj.name,
            'repo_component': repo_component,
            'business_domain': business_domain,
            'file_size': len(content),
            'line_count': len(content.split('\n'))
        }
    
    def _extract_repo_component(self, file_path: str) -> str:
        """Extract which repository component this doc belongs to"""
        # Generic component detection based on path patterns
        if '/api/' in file_path or '/apis/' in file_path:
            return 'api'
        elif '/contracts/' in file_path or '/contract/' in file_path:
            return 'contracts'
        elif '/docs/' in file_path or '/documentation/' in file_path:
            return 'documentation'
        elif '/cli/' in file_path or '/commands/' in file_path:
            return 'cli'
        elif '/db/' in file_path or '/database/' in file_path:
            return 'database'
        elif '/frontend/' in file_path or '/ui/' in file_path or '/app/' in file_path:
            return 'frontend'
        else:
            return 'core'
    
    def _extract_business_domain(self, file_path: str, content: str) -> str:
        """Extract business domain from path and content"""
        
        # Domain keywords in content
        domain_keywords = {
            'auth': ['authentication', 'login', 'magic-link', 'session', 'jwt', 'auth'],
            'finance': ['loan', 'payment', 'withdrawal', 'balance', 'usdc', 'transaction'],
            'contracts': ['solidity', 'smart contract', 'ethereum', 'blockchain'],
            'kyc': ['kyc', 'verification', 'compliance', 'identity'],
            'api': ['endpoint', 'rest', 'graphql', 'swagger', 'api'],
            'deployment': ['deploy', 'kubernetes', 'docker', 'helm', 'production']
        }
        
        content_lower = content.lower()[:1000]  # Check first 1000 chars
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return domain
        
        # Fallback to path-based detection
        if 'auth' in file_path.lower():
            return 'auth'
        elif 'integration' in file_path.lower():
            return 'integration'
        elif 'architecture' in file_path.lower():
            return 'architecture'
        
        return 'general'
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Extract document title from markdown content"""
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        return None
    
    def _extract_sections(self, content: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract document sections for intelligent chunking"""
        
        sections = []
        current_section = {
            'title': 'Introduction',
            'level': 1,
            'content': '',
            'code_blocks': [],
            'importance': 0.6
        }
        
        lines = content.split('\n')
        in_code_block = False
        code_block_content = []
        code_block_language = None
        
        for line in lines:
            # Handle code blocks
            if line.startswith('```'):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_block_language = line[3:].strip() or 'text'
                    code_block_content = []
                else:
                    # End of code block
                    in_code_block = False
                    current_section['code_blocks'].append({
                        'language': code_block_language,
                        'content': '\n'.join(code_block_content)
                    })
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            # Handle section headers
            if line.startswith('#'):
                # Save previous section if it has content
                if current_section['content'].strip():
                    sections.append(current_section)
                
                # Start new section
                level = len(line.split()[0])  # Count # characters
                title = line.lstrip('#').strip()
                
                current_section = {
                    'title': title,
                    'level': level,
                    'content': '',
                    'code_blocks': [],
                    'importance': self._calculate_section_importance(title)
                }
            else:
                # Add line to current section
                current_section['content'] += line + '\n'
        
        # Add final section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _calculate_section_importance(self, title: str) -> float:
        """Calculate importance score for a section based on title"""
        title_lower = title.lower()
        
        for keyword, weight in self.section_weights.items():
            if keyword in title_lower:
                return weight
        
        # Higher importance for sections with key terms
        high_value_terms = ['existing', 'current', 'architecture', 'system', 'implementation']
        if any(term in title_lower for term in high_value_terms):
            return 0.8
        
        return 0.5  # Default importance
    
    def _create_chunks(self, sections: List[Dict[str, Any]], doc_metadata: Dict[str, Any], 
                      file_path: str) -> List[Dict[str, Any]]:
        """Create vector-ready chunks from document sections"""
        
        chunks = []
        
        # Create overview chunk with document metadata
        overview_content = self._create_overview_chunk(sections, doc_metadata)
        chunks.append(self._create_chunk_metadata(
            content=overview_content,
            chunk_type='overview',
            section_title=doc_metadata['title'],
            doc_metadata=doc_metadata,
            file_path=file_path,
            importance=0.9
        ))
        
        # Create chunks with intelligent grouping for better context
        grouped_chunks = self._group_sections_intelligently(sections, doc_metadata)
        
        for chunk_data in grouped_chunks:
            chunks.append(self._create_chunk_metadata(
                content=chunk_data['content'],
                chunk_type=chunk_data['chunk_type'],
                section_title=chunk_data['title'],
                doc_metadata=doc_metadata,
                file_path=file_path,
                importance=chunk_data['importance'],
                section_level=chunk_data.get('section_level', 1)
            ))
            
        # Process code blocks separately (now handled in grouping)
        # Code blocks are already included in grouped chunks
        
        return chunks
    
    def _create_overview_chunk(self, sections: List[Dict[str, Any]], 
                              doc_metadata: Dict[str, Any]) -> str:
        """Create a comprehensive overview chunk of the document"""
        
        overview_parts = [
            f"# Documentation: {doc_metadata['title']}",
            f"Document Type: {doc_metadata['doc_type']}",
            f"Repository Component: {doc_metadata['repo_component']}",
            f"Business Domain: {doc_metadata['business_domain']}",
            ""
        ]
        
        # Add table of contents
        if len(sections) > 1:
            overview_parts.append("## Document Structure:")
            for section in sections:
                indent = "  " * (section['level'] - 1)
                overview_parts.append(f"{indent}- {section['title']}")
            overview_parts.append("")
        
        # Add summary of high-importance sections
        high_importance_sections = [s for s in sections if s['importance'] > 0.7]
        if high_importance_sections:
            overview_parts.append("## Key Content:")
            for section in high_importance_sections[:3]:  # Top 3 important sections
                # Get first paragraph as summary
                first_paragraph = section['content'].split('\n\n')[0].strip()[:200]
                if first_paragraph:
                    overview_parts.append(f"**{section['title']}**: {first_paragraph}...")
        
        return "\n".join(overview_parts)
    
    def _format_section_content(self, section: Dict[str, Any]) -> str:
        """Format section content for vectorization"""
        
        content_parts = [
            f"# {section['title']} (Documentation Section)",
            ""
        ]
        
        # Add section content
        content_parts.append(section['content'].strip())
        
        # Add code block references if any
        if section['code_blocks']:
            content_parts.append("")
            content_parts.append("Code Examples:")
            for i, code_block in enumerate(section['code_blocks']):
                content_parts.append(f"- {code_block['language']} code block ({len(code_block['content'])} lines)")
        
        return "\n".join(content_parts)
    
    def _format_code_block(self, code_block: Dict[str, Any], 
                          section: Dict[str, Any]) -> str:
        """Format code block for vectorization"""
        
        return f"""# Code Example: {section['title']}

Language: {code_block['language']}
Context: {section['title']} documentation section

```{code_block['language']}
{code_block['content']}
```

This code example demonstrates implementation patterns for {section['title'].lower()} functionality."""
    
    def _group_sections_intelligently(self, sections: List[Dict[str, Any]],
                                     doc_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Group sections intelligently respecting markdown semantic structure.
        Strategy: Split at Level 2 (##) boundaries for complete, meaningful topics.
        """
        grouped_chunks = []

        # Group sections by Level 2 boundaries
        # This keeps each major topic (##) with all its subsections (###) together
        current_group = []
        current_level2_start = None

        for i, section in enumerate(sections):
            section_content = self._format_section_content(section)
            section_chars = len(section_content)

            # Skip very small sections unless high importance
            if section_chars < 200 and section['importance'] < 0.7:
                continue

            # Level 1 sections (# Title) - treat as standalone if substantial
            if section['level'] == 1:
                # Finalize previous group if exists
                if current_group:
                    grouped_chunks.append(self._finalize_group(current_group, max(s['importance'] for s in current_group)))
                    current_group = []

                # Add level 1 as standalone if substantial, otherwise skip (usually just title)
                if section_chars > 300:
                    grouped_chunks.append(self._finalize_group([section], section['importance']))
                continue

            # Level 2 sections (## Major Topic) - start new group
            elif section['level'] == 2:
                # Finalize previous Level 2 group
                if current_group:
                    grouped_chunks.append(self._finalize_group(current_group, max(s['importance'] for s in current_group)))

                # Start new group with this Level 2 section
                current_group = [section]
                current_level2_start = i

            # Level 3+ sections (### Subsection) - add to current Level 2 group
            elif section['level'] >= 3:
                if current_group:
                    # Add to current group
                    current_group.append(section)

                    # Check if group is getting too large (>8k chars for docs)
                    group_size = sum(len(self._format_section_content(s)) for s in current_group)
                    if group_size > 8000:
                        # Split large groups at Level 3 boundaries
                        # Keep first part (Level 2 + some Level 3s)
                        grouped_chunks.append(self._finalize_group(current_group[:-1], max(s['importance'] for s in current_group[:-1])))
                        # Start new group with remaining Level 3
                        current_group = [section]
                else:
                    # Orphaned Level 3 section (no parent Level 2)
                    grouped_chunks.append(self._finalize_group([section], section['importance']))

        # Finalize any remaining group
        if current_group:
            grouped_chunks.append(self._finalize_group(current_group, max(s['importance'] for s in current_group)))

        return grouped_chunks
    
    def _finalize_group(self, sections: List[Dict[str, Any]], importance: float) -> Dict[str, Any]:
        """Finalize a group of sections into a single chunk"""
        if len(sections) == 1:
            section = sections[0]
            return {
                'content': self._format_section_content(section),
                'chunk_type': 'section',
                'title': section['title'],
                'importance': section['importance'],
                'section_level': section['level']
            }
        else:
            # Multi-section chunk
            combined_content = []
            titles = []
            
            for section in sections:
                titles.append(section['title'])
                combined_content.append(self._format_section_content(section))
            
            return {
                'content': '\n\n---\n\n'.join(combined_content),
                'chunk_type': 'multi_section',
                'title': f"{titles[0]} + {len(titles)-1} more sections",
                'importance': importance,
                'section_level': min(s['level'] for s in sections)
            }

    def _create_chunk_metadata(self, content: str, chunk_type: str, section_title: str,
                              doc_metadata: Dict[str, Any], file_path: str, 
                              importance: float, **extra_metadata) -> Dict[str, Any]:
        """Create standardized chunk metadata for vectorization"""
        
        # Generate unique chunk hash
        chunk_hash = hashlib.md5(
            f"{file_path}:{section_title}:{chunk_type}".encode()
        ).hexdigest()
        
        # Return dictionary structure expected by ingestion pipeline
        line_count = len(content.split('\n'))
        
        return {
            'file_path': file_path,
            'content_preview': content,  # Full content for docs
            'line_count': line_count,
            'section_title': section_title,
            'chunk_type': chunk_type,
            'repo_component': doc_metadata['repo_component'],
            'business_domain': doc_metadata['business_domain'],
            'doc_type': doc_metadata['doc_type'],
            'chunk_hash': chunk_hash,
            'importance_score': importance,
            'char_count': len(content)
        }
    
    def get_parser_stats(self) -> Dict[str, Any]:
        """Get statistics about parsed documentation"""
        return {
            'parser_type': 'documentation',
            'supported_extensions': ['.md', '.markdown'],
            'chunk_types': ['overview', 'section', 'code_example'],
            'business_domains': list(self.doc_types.keys())
        }