"""
YAML and Helm Parser

Parses YAML configuration files, Kubernetes manifests, and Helm charts
with multi-level indexing for better searchability.

Following CLAUDE.md: <500 lines, single responsibility (YAML parsing only).
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

from ..core.metadata_schema import CodeItemMetadata, IndexGranularity, ServiceType, ArchitecturalLayer

logger = logging.getLogger(__name__)


class YAMLParser:
    """
    Parser for YAML files including Helm charts and K8s manifests.
    
    Supports:
    - Helm templates (K8s resources with templating)
    - Chart.yaml (chart metadata)
    - values.yaml (configuration with multi-level indexing)
    - Standalone K8s manifests
    - Generic YAML configuration files
    """
    
    def __init__(self, repo_id: str, repo_component: str):
        """
        Initialize YAML parser.
        
        Args:
            repo_id: Repository identifier
            repo_component: Component within repo (e.g., 'helm', 'config')
        """
        self.repo_id = repo_id
        self.repo_component = repo_component
    
    def parse_file(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Route to appropriate parser based on file type.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            List of metadata items extracted from file
        """
        file_name = file_path.name
        
        try:
            # Route based on file type
            if file_path.parent.name == "templates" or "template" in str(file_path):
                return self.parse_helm_template(file_path)
            elif file_name == "Chart.yaml":
                return self.parse_chart_yaml(file_path)
            elif file_name == "values.yaml":
                return self.parse_values_yaml(file_path)
            elif self._is_k8s_manifest(file_path):
                return self.parse_k8s_manifest(file_path)
            else:
                return self.parse_generic_yaml(file_path)
        except Exception as e:
            logger.error(f"Error parsing YAML file {file_path}: {e}")
            return []
    
    def parse_helm_template(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Helm template files.
        Extract each K8s resource as a separate item.

        Args:
            file_path: Path to Helm template file

        Returns:
            List of metadata for each K8s resource in template
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Helm templates contain Go template syntax ({{- ... }}) which isn't valid YAML
        # If we detect Helm templating, treat as generic YAML (store full content)
        if '{{' in content or '{%' in content:
            logger.debug(f"Helm template detected in {file_path.name}, storing as generic template")
            return [self._create_file_level_metadata(file_path, content, "helm_template")]

        # Split YAML documents (--- separator)
        try:
            documents = list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error in {file_path}: {e}. Treating as generic YAML.")
            return self.parse_generic_yaml(file_path)
        
        metadata_items = []
        for doc in documents:
            if not doc or not isinstance(doc, dict):
                continue
            
            kind = doc.get('kind', 'Unknown')
            metadata_dict = doc.get('metadata', {})
            name = metadata_dict.get('name', 'unnamed') if isinstance(metadata_dict, dict) else 'unnamed'
            
            # Extract container info
            containers = []
            env_vars = {}
            env_var_list = []
            ports = []
            service_dependencies = []
            
            if kind == "Deployment":
                spec = doc.get('spec', {})
                template = spec.get('template', {})
                pod_spec = template.get('spec', {})
                containers_spec = pod_spec.get('containers', [])
                
                for container in containers_spec:
                    if isinstance(container, dict):
                        image = container.get('image', '')
                        if image:
                            containers.append(image)
                        
                        for env in container.get('env', []):
                            if isinstance(env, dict):
                                env_name = env.get('name')
                                env_value = env.get('value', env.get('valueFrom', ''))
                                if env_name:
                                    env_vars[env_name] = str(env_value)
                                    env_var_list.append(env_name)
                                    
                                    # Detect service dependencies from env vars
                                    if '_URL' in env_name or '_HOST' in env_name or '_ENDPOINT' in env_name:
                                        # Extract service name from env var
                                        service_name = env_name.lower().replace('_url', '').replace('_host', '').replace('_endpoint', '')
                                        if service_name and service_name not in service_dependencies:
                                            service_dependencies.append(service_name)
                        
                        for port in container.get('ports', []):
                            if isinstance(port, dict):
                                port_num = port.get('containerPort')
                                if port_num:
                                    ports.append(int(port_num))
            
            # Extract service ports
            if kind == "Service":
                spec = doc.get('spec', {})
                service_ports = spec.get('ports', [])
                for p in service_ports:
                    if isinstance(p, dict):
                        port_num = p.get('port')
                        if port_num:
                            ports.append(int(port_num))
                
                # Extract selector to identify related deployments
                selector = spec.get('selector', {})
                if selector:
                    # This could be used to link services to deployments
                    pass
            
            metadata = CodeItemMetadata(
                file_path=str(file_path),
                item_name=f"{kind}/{name}",
                item_type="k8s_resource",
                language="helm",
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
                granularity=IndexGranularity.RESOURCE,
                k8s_resource_type=kind,
                container_images=containers,
                env_vars=env_var_list if env_var_list else [],
                ports=ports,
                depends_on_services=service_dependencies if service_dependencies else []
            )
            
            metadata_items.append(metadata)
        
        # If no resources extracted, create one item for the whole file
        if not metadata_items:
            metadata_items.append(self._create_file_level_metadata(file_path, content, "helm_template"))
        
        return metadata_items
    
    def parse_chart_yaml(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Chart.yaml to extract chart metadata.
        
        Args:
            file_path: Path to Chart.yaml
            
        Returns:
            List with single metadata item for the chart
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            chart_data = yaml.safe_load(content)
        
        if not isinstance(chart_data, dict):
            return self.parse_generic_yaml(file_path)
        
        chart_name = chart_data.get('name', 'unknown')
        dependencies = []
        for d in chart_data.get('dependencies', []):
            if isinstance(d, dict):
                dep_name = d.get('name')
                if dep_name:
                    dependencies.append(dep_name)
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name=f"HelmChart/{chart_name}",
            item_type="helm_chart",
            language="helm",
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
            granularity=IndexGranularity.FILE,
            helm_chart_name=chart_name,
            depends_on_services=dependencies
        )
        
        return [metadata]
    
    def parse_values_yaml(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse values.yaml with multi-level indexing.
        Index both as complete file AND individual keys for better searchability.
        
        Args:
            file_path: Path to values.yaml
            
        Returns:
            List of metadata items (full file + individual sections)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            values_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error in {file_path}: {e}")
            return [self._create_file_level_metadata(file_path, content, "helm_values")]
        
        metadata_items = []
        
        # 1. Index entire values.yaml as one item
        full_values_metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name="values.yaml",
            item_type="helm_values",
            language="helm",
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
        metadata_items.append(full_values_metadata)
        
        # 2. Index major configuration sections separately
        if isinstance(values_data, dict):
            for key, value in values_data.items():
                if isinstance(value, dict):
                    section_content = yaml.dump({key: value})
                    section_metadata = CodeItemMetadata(
                        file_path=str(file_path),
                        item_name=f"values/{key}",
                        item_type="config_section",
                        language="helm",
                        repo_id=self.repo_id,
                        repo_component=self.repo_component,
                        start_line=0,
                        end_line=0,
                        content_preview=section_content[:500],
                        full_content=section_content,
                        line_count=len(section_content.split('\n')),
                        business_domain="infrastructure",
                        service_type=ServiceType.INFRASTRUCTURE,
                        architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
                        granularity=IndexGranularity.MODULE
                    )
                    metadata_items.append(section_metadata)
        
        return metadata_items
    
    def parse_k8s_manifest(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse standalone K8s YAML manifests (not Helm templates).
        
        Args:
            file_path: Path to K8s manifest
            
        Returns:
            List of metadata for each K8s resource
        """
        # Similar logic to parse_helm_template but without Helm-specific handling
        return self.parse_helm_template(file_path)
    
    def parse_generic_yaml(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse generic YAML configuration files.
        
        Args:
            file_path: Path to YAML config file
            
        Returns:
            List with single metadata item for the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return [self._create_file_level_metadata(file_path, content, "config_file")]
    
    def _is_k8s_manifest(self, file_path: Path) -> bool:
        """
        Detect if a YAML file is a K8s manifest.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            True if file contains K8s resources
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return 'apiVersion' in data and 'kind' in data
        except Exception:
            pass
        return False
    
    def _create_file_level_metadata(
        self,
        file_path: Path,
        content: str,
        item_type: str
    ) -> CodeItemMetadata:
        """
        Create metadata for an entire YAML file.
        
        Args:
            file_path: Path to file
            content: File content
            item_type: Type of YAML file
            
        Returns:
            CodeItemMetadata for the file
        """
        return CodeItemMetadata(
            file_path=str(file_path),
            item_name=file_path.name,
            item_type=item_type,
            language="yaml",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="configuration",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE
        )

