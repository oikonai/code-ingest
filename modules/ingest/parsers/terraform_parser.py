"""
Terraform/IaC Parser

Parses Terraform configuration files and extracts infrastructure resources
with multi-level indexing (individual resources + full files).

Following CLAUDE.md: <500 lines, single responsibility (Terraform parsing only).
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
import logging

from ..core.metadata_schema import CodeItemMetadata, IndexGranularity, ServiceType, ArchitecturalLayer

logger = logging.getLogger(__name__)


class TerraformParser:
    """
    Parser for Terraform/IaC files.
    
    Supports:
    - .tf files (resource definitions)
    - .tfvars files (variable values)
    - Multi-level indexing (individual resources + full file)
    """
    
    def __init__(self, repo_id: str, repo_component: str = "infrastructure"):
        """
        Initialize Terraform parser.
        
        Args:
            repo_id: Repository identifier
            repo_component: Component within repo (default: 'infrastructure')
        """
        self.repo_id = repo_id
        self.repo_component = repo_component
    
    def parse_file(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Terraform .tf or .tfvars files.
        
        Args:
            file_path: Path to Terraform file
            
        Returns:
            List of metadata items (individual resources + full file)
        """
        try:
            if file_path.suffix == '.tfvars':
                return self.parse_tfvars(file_path)
            else:
                return self.parse_tf(file_path)
        except Exception as e:
            logger.error(f"Error parsing Terraform file {file_path}: {e}")
            return []
    
    def parse_tf(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Terraform .tf files and extract resource blocks.
        
        Args:
            file_path: Path to .tf file
            
        Returns:
            List of metadata for each resource + full file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata_items = []
        
        # Extract resource blocks
        # Pattern: resource "type" "name" { ... }
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        resources = re.findall(resource_pattern, content)
        
        for resource_type, resource_name in resources:
            # Try to extract the full resource block
            # This is a simplified approach - full HCL parsing would be more robust
            resource_block_pattern = (
                rf'resource\s+"{re.escape(resource_type)}"\s+"{re.escape(resource_name)}"\s*\{{[^}}]*\}}'
            )
            match = re.search(resource_block_pattern, content, re.DOTALL)
            
            if match:
                resource_content = match.group(0)
            else:
                # Fallback: try to extract with nested braces
                resource_content = self._extract_block_with_braces(
                    content,
                    f'resource "{resource_type}" "{resource_name}"'
                )
            
            if resource_content:
                # Calculate line numbers
                start_pos = content.find(resource_content)
                if start_pos != -1:
                    start_line = content[:start_pos].count('\n') + 1
                    end_line = start_line + resource_content.count('\n')
                else:
                    start_line = 0
                    end_line = 0
                
                # Extract dependencies
                dependencies = self._extract_resource_dependencies(resource_content)
                
                # Detect if this is a database resource
                is_database = self._detect_database_resource(resource_type, resource_content)
                
                metadata = CodeItemMetadata(
                    file_path=str(file_path),
                    item_name=f"{resource_type}.{resource_name}",
                    item_type="terraform_resource",
                    language="terraform",
                    repo_id=self.repo_id,
                    repo_component=self.repo_component,
                    start_line=start_line,
                    end_line=end_line,
                    content_preview=resource_content[:500],
                    full_content=resource_content,
                    line_count=resource_content.count('\n') + 1,
                    business_domain="database" if is_database else "infrastructure",
                    service_type=ServiceType.INFRASTRUCTURE,
                    architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
                    granularity=IndexGranularity.RESOURCE,
                    depends_on_services=dependencies
                )
                metadata_items.append(metadata)
        
        # Also extract data sources
        data_pattern = r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        data_sources = re.findall(data_pattern, content)
        
        for data_type, data_name in data_sources:
            data_block_pattern = (
                rf'data\s+"{re.escape(data_type)}"\s+"{re.escape(data_name)}"\s*\{{[^}}]*\}}'
            )
            match = re.search(data_block_pattern, content, re.DOTALL)
            
            if match:
                data_content = match.group(0)
            else:
                data_content = self._extract_block_with_braces(
                    content,
                    f'data "{data_type}" "{data_name}"'
                )
            
            if data_content:
                metadata = CodeItemMetadata(
                    file_path=str(file_path),
                    item_name=f"data.{data_type}.{data_name}",
                    item_type="terraform_data",
                    language="terraform",
                    repo_id=self.repo_id,
                    repo_component=self.repo_component,
                    start_line=0,
                    end_line=0,
                    content_preview=data_content[:500],
                    full_content=data_content,
                    line_count=data_content.count('\n') + 1,
                    business_domain="infrastructure",
                    service_type=ServiceType.INFRASTRUCTURE,
                    architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
                    granularity=IndexGranularity.RESOURCE
                )
                metadata_items.append(metadata)
        
        # Extract modules
        module_pattern = r'module\s+"([^"]+)"\s*\{'
        modules = re.findall(module_pattern, content)
        
        for module_name in modules:
            module_content = self._extract_block_with_braces(
                content,
                f'module "{module_name}"'
            )
            
            if module_content:
                metadata = CodeItemMetadata(
                    file_path=str(file_path),
                    item_name=f"module.{module_name}",
                    item_type="terraform_module",
                    language="terraform",
                    repo_id=self.repo_id,
                    repo_component=self.repo_component,
                    start_line=0,
                    end_line=0,
                    content_preview=module_content[:500],
                    full_content=module_content,
                    line_count=module_content.count('\n') + 1,
                    business_domain="infrastructure",
                    service_type=ServiceType.INFRASTRUCTURE,
                    architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
                    granularity=IndexGranularity.MODULE
                )
                metadata_items.append(metadata)
        
        # Also index entire file for comprehensive coverage
        full_file_metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name=file_path.name,
            item_type="terraform_file",
            language="terraform",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="infrastructure",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE
        )
        metadata_items.append(full_file_metadata)
        
        return metadata_items
    
    def parse_tfvars(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Terraform .tfvars files (variable values).
        
        Args:
            file_path: Path to .tfvars file
            
        Returns:
            List with single metadata item for the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name=file_path.name,
            item_type="terraform_vars",
            language="terraform",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="infrastructure",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE
        )
        
        return [metadata]
    
    def _extract_resource_dependencies(self, resource_content: str) -> List[str]:
        """
        Extract resource dependencies from Terraform resource block.
        
        Args:
            resource_content: Content of the resource block
            
        Returns:
            List of referenced resource identifiers
        """
        dependencies = []
        
        # Pattern for resource references: resource_type.resource_name
        ref_pattern = r'([a-z_]+)\s*\.\s*([a-z_][a-z0-9_]*)'
        matches = re.findall(ref_pattern, resource_content)
        
        for resource_type, resource_name in matches:
            # Filter out common HCL constructs that aren't resource references
            if resource_type not in ['var', 'local', 'data', 'each', 'self', 'count', 'path', 'terraform']:
                dep_id = f"{resource_type}.{resource_name}"
                if dep_id not in dependencies:
                    dependencies.append(dep_id)
        
        return dependencies
    
    def _detect_database_resource(self, resource_type: str, resource_content: str) -> bool:
        """
        Detect if resource is a database resource.
        
        Args:
            resource_type: Terraform resource type
            resource_content: Resource block content
            
        Returns:
            True if it's a database resource
        """
        # Database resource types
        db_resource_types = [
            'aws_db_instance', 'aws_rds_cluster', 'aws_dynamodb_table',
            'google_sql_database_instance', 'azurerm_postgresql_server',
            'aws_elasticache_cluster', 'aws_redshift_cluster'
        ]
        
        if any(db_type in resource_type for db_type in db_resource_types):
            return True
        
        # Check content for database-related keywords
        db_keywords = ['database', 'postgres', 'mysql', 'redis', 'mongodb', 'dynamodb']
        content_lower = resource_content.lower()
        return any(keyword in content_lower for keyword in db_keywords)
    
    def _extract_block_with_braces(self, content: str, block_start: str) -> Optional[str]:
        """
        Extract a block from content by matching opening and closing braces.
        
        Args:
            content: Full file content
            block_start: Starting pattern (e.g., 'resource "aws_instance" "example"')
            
        Returns:
            Extracted block content, or None if not found
        """
        start_pos = content.find(block_start)
        if start_pos == -1:
            return None
        
        # Find the opening brace
        brace_pos = content.find('{', start_pos)
        if brace_pos == -1:
            return None
        
        # Count braces to find matching closing brace
        brace_count = 1
        pos = brace_pos + 1
        
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        
        if brace_count == 0:
            return content[start_pos:pos]
        
        return None

