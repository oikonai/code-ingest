"""
Enhanced Metadata Schema for Multi-Language Ingestion

Defines comprehensive metadata structures for all code items, including
infrastructure, dependencies, APIs, and service relationships.

Following CLAUDE.md: <500 lines, single responsibility (metadata schema only).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ServiceType(Enum):
    """Service type classification"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    MIDDLEWARE = "middleware"
    SMART_CONTRACT = "smart_contract"
    INFRASTRUCTURE = "infrastructure"
    TOOLING = "tooling"


class ArchitecturalLayer(Enum):
    """Architectural layer classification"""
    PRESENTATION = "presentation"
    BUSINESS = "business"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"


class IndexGranularity(Enum):
    """Granularity level for indexed items"""
    FILE = "file"          # Entire file as one chunk
    MODULE = "module"      # Module/class level
    FUNCTION = "function"  # Individual functions
    RESOURCE = "resource"  # K8s resource in YAML


@dataclass
class CodeItemMetadata:
    """
    Enhanced metadata for all indexed code items.
    
    Supports:
    - Multi-language code (Rust, TypeScript, Python, Solidity)
    - Infrastructure (YAML, Helm, Terraform, Dockerfiles)
    - CI/CD workflows
    - Service dependencies and relationships
    - API mapping and consumption
    """
    
    # ===== Core Identification =====
    file_path: str
    item_name: str
    item_type: str  # function|class|module|k8s_resource|helm_chart|terraform_resource|workflow|etc
    language: str
    repo_id: str
    repo_component: str
    start_line: int
    end_line: int
    
    # ===== Content =====
    content_preview: str
    full_content: str
    line_count: int
    
    # ===== Classification =====
    business_domain: str = "general"
    complexity_score: float = 0.0
    
    # ===== NEW: Service and Architecture Classification =====
    service_type: Optional[ServiceType] = None
    architectural_layer: Optional[ArchitecturalLayer] = None
    granularity: IndexGranularity = IndexGranularity.FUNCTION
    
    # ===== NEW: Dependencies and Relationships =====
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    calls_functions: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    
    # ===== NEW: API Information (for backend services) =====
    api_endpoints: List[Dict[str, str]] = field(default_factory=list)
    # Example: [{"method": "POST", "path": "/api/auth", "handler": "auth_handler"}]
    api_consumes: List[str] = field(default_factory=list)  # External APIs called
    
    # ===== NEW: Infrastructure Specific =====
    k8s_resource_type: Optional[str] = None  # Deployment|Service|ConfigMap|etc
    helm_chart_name: Optional[str] = None
    deployed_services: List[str] = field(default_factory=list)
    environment: Optional[str] = None  # dev|staging|prod
    depends_on_services: List[str] = field(default_factory=list)
    
    # ===== NEW: Container/Deployment Info =====
    container_images: List[str] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    ports: List[int] = field(default_factory=list)
    
    # ===== NEW: Smart Contract Specific =====
    contract_type: Optional[str] = None  # ERC20|ERC721|Custom
    blockchain_network: Optional[str] = None
    
    # ===== NEW: CI/CD Specific =====
    workflow_name: Optional[str] = None
    workflow_triggers: List[str] = field(default_factory=list)
    workflow_jobs: List[str] = field(default_factory=list)
    
    # ===== NEW: Documentation =====
    has_readme: bool = False
    documentation_links: List[str] = field(default_factory=list)
    
    # ===== Embedding =====
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metadata to dictionary for storage in vector database.
        
        Returns:
            Dictionary with all metadata fields
        """
        return {
            # Core identification
            'file_path': self.file_path,
            'item_name': self.item_name,
            'item_type': self.item_type,
            'language': self.language,
            'repo_id': self.repo_id,
            'repo_component': self.repo_component,
            'start_line': self.start_line,
            'end_line': self.end_line,
            
            # Content
            'content_preview': self.content_preview,
            'full_content': self.full_content,
            'line_count': self.line_count,
            
            # Classification
            'business_domain': self.business_domain,
            'complexity_score': self.complexity_score,
            
            # Service and architecture
            'service_type': self.service_type.value if self.service_type else None,
            'architectural_layer': self.architectural_layer.value if self.architectural_layer else None,
            'granularity': self.granularity.value if self.granularity else IndexGranularity.FUNCTION.value,
            
            # Dependencies
            'imports': self.imports,
            'exports': self.exports,
            'calls_functions': self.calls_functions,
            'called_by': self.called_by,
            
            # API information
            'api_endpoints': self.api_endpoints,
            'api_consumes': self.api_consumes,
            
            # Infrastructure
            'k8s_resource_type': self.k8s_resource_type,
            'helm_chart_name': self.helm_chart_name,
            'deployed_services': self.deployed_services,
            'environment': self.environment,
            'depends_on_services': self.depends_on_services,
            
            # Container/deployment
            'container_images': self.container_images,
            'env_vars': self.env_vars,
            'ports': self.ports,
            
            # Smart contracts
            'contract_type': self.contract_type,
            'blockchain_network': self.blockchain_network,
            
            # CI/CD
            'workflow_name': self.workflow_name,
            'workflow_triggers': self.workflow_triggers,
            'workflow_jobs': self.workflow_jobs,
            
            # Documentation
            'has_readme': self.has_readme,
            'documentation_links': self.documentation_links,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeItemMetadata':
        """
        Create CodeItemMetadata from dictionary.
        
        Args:
            data: Dictionary with metadata fields
            
        Returns:
            CodeItemMetadata instance
        """
        # Convert enum string values back to enums
        service_type = None
        if data.get('service_type'):
            service_type = ServiceType(data['service_type'])
        
        architectural_layer = None
        if data.get('architectural_layer'):
            architectural_layer = ArchitecturalLayer(data['architectural_layer'])
        
        granularity = IndexGranularity(data.get('granularity', 'function'))
        
        return cls(
            # Core identification
            file_path=data['file_path'],
            item_name=data['item_name'],
            item_type=data['item_type'],
            language=data['language'],
            repo_id=data['repo_id'],
            repo_component=data['repo_component'],
            start_line=data['start_line'],
            end_line=data['end_line'],
            
            # Content
            content_preview=data['content_preview'],
            full_content=data['full_content'],
            line_count=data['line_count'],
            
            # Classification
            business_domain=data.get('business_domain', 'general'),
            complexity_score=data.get('complexity_score', 0.0),
            
            # Service and architecture
            service_type=service_type,
            architectural_layer=architectural_layer,
            granularity=granularity,
            
            # Dependencies
            imports=data.get('imports', []),
            exports=data.get('exports', []),
            calls_functions=data.get('calls_functions', []),
            called_by=data.get('called_by', []),
            
            # API information
            api_endpoints=data.get('api_endpoints', []),
            api_consumes=data.get('api_consumes', []),
            
            # Infrastructure
            k8s_resource_type=data.get('k8s_resource_type'),
            helm_chart_name=data.get('helm_chart_name'),
            deployed_services=data.get('deployed_services', []),
            environment=data.get('environment'),
            depends_on_services=data.get('depends_on_services', []),
            
            # Container/deployment
            container_images=data.get('container_images', []),
            env_vars=data.get('env_vars', {}),
            ports=data.get('ports', []),
            
            # Smart contracts
            contract_type=data.get('contract_type'),
            blockchain_network=data.get('blockchain_network'),
            
            # CI/CD
            workflow_name=data.get('workflow_name'),
            workflow_triggers=data.get('workflow_triggers', []),
            workflow_jobs=data.get('workflow_jobs', []),
            
            # Documentation
            has_readme=data.get('has_readme', False),
            documentation_links=data.get('documentation_links', []),
            
            # Embedding
            embedding=data.get('embedding'),
        )

