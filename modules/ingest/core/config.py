"""
Ingestion Pipeline Configuration

Configuration classes and constants for the multi-language ingestion system.
Following CLAUDE.md: <500 lines, single responsibility (configuration only).

Repository list is loaded from config/repositories.yaml (or REPOSITORIES_CONFIG env var).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ===== PRIORITY CONSTANTS =====
# Single source of truth for repository priority values
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"


class RepoType(Enum):
    """Type classification for repositories"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    MIDDLEWARE = "middleware"
    MCP_SERVER = "mcp_server"
    INFRASTRUCTURE = "infrastructure"
    TOOL = "tool"
    DOCUMENTATION = "documentation"


class Language(Enum):
    """Supported programming and configuration languages"""
    RUST = "rust"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    SOLIDITY = "solidity"
    YAML = "yaml"
    HELM = "helm"
    TERRAFORM = "terraform"
    DOCKERFILE = "dockerfile"
    MARKDOWN = "markdown"
    SQL = "sql"
    JAVASCRIPT = "javascript"
    JSX = "jsx"
    TSX = "tsx"


@dataclass
class RepoConfig:
    """Configuration for a single repository"""
    github_url: str
    repo_type: RepoType
    languages: List[Language]
    components: List[str]  # Subdirectories to index
    has_helm: bool = False
    helm_path: Optional[str] = None  # Path to helm charts within repo
    service_dependencies: List[str] = field(default_factory=list)  # Services this depends on
    exposes_apis: bool = False
    api_base_path: Optional[str] = None
    priority: str = PRIORITY_MEDIUM  # Use constants: PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW


@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline."""

    # Repository base directory (defaults to ./repos, can be overridden)
    # Note: This is also loaded from repositories.yaml and available as REPOS_BASE_DIR module variable
    repos_base_dir: str = "./repos"

    # Cloudflare AI Gateway + DeepInfra endpoint
    # Format: https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/custom-{slug}/v1/openai
    # Note: OpenAI client appends /embeddings to form full path
    cloudflare_base_url: str = "https://gateway.ai.cloudflare.com/v1/2de868ad9edb1b11250bc516705e1639/aig/custom-deepinfra/v1/openai"

    # Embedding model configuration
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"

    # DEPRECATED: Modal TEI endpoint (kept for reference)
    # modal_endpoint: str = "https://ardaglobal--embed.modal.run"

    # Checkpoint configuration
    checkpoint_file: Path = field(default_factory=lambda: Path("./ingestion_checkpoint.json"))

    # Batch processing configuration
    batch_size: int = 50  # Batch size for embedding requests
    rate_limit: int = 4  # Max concurrent requests
    max_batch_retries: int = 3  # Retry failed batches up to 3 times

    # Embedding configuration
    embedding_size: int = 4096  # Qwen3-Embedding-8B dimension

    # Timeout configuration (seconds)
    embedding_timeout: int = 60  # Cloudflare AI Gateway is much faster than Modal
    warmup_timeout: int = 60  # No cold starts with Cloudflare AI Gateway

    # Collection names by language (BY_LANGUAGE)
    collections: Dict[str, str] = field(default_factory=lambda: {
        'rust': 'arda_code_rust',
        'typescript': 'arda_code_typescript',
        'javascript': 'arda_code_typescript',  # Same as TS
        'jsx': 'arda_code_typescript',          # Same as TS
        'tsx': 'arda_code_typescript',          # Same as TS
        'python': 'arda_code_python',          # Python code
        'solidity': 'arda_code_solidity',
        'documentation': 'arda_documentation',
        'yaml': 'arda_code_yaml',               # YAML configs
        'helm': 'arda_code_yaml',               # Helm charts (same as YAML)
        'terraform': 'arda_code_terraform',     # Infrastructure as Code
        'infrastructure': 'arda_infrastructure', # K8s, containers, etc.
        'cicd': 'arda_cicd',                    # CI/CD workflows
        'mixed': 'arda_code_mixed'              # Cross-language semantic search
    })

    # BY_SERVICE collection mappings
    service_collections: Dict[str, str] = field(default_factory=lambda: {
        'frontend': 'arda_frontend',
        'backend': 'arda_backend',
        'middleware': 'arda_middleware',
        'mcp_server': 'arda_middleware',  # MCP servers treated as middleware
        'infrastructure': 'arda_infrastructure',
        'tool': 'arda_infrastructure',  # Tools treated as infrastructure
        'documentation': 'arda_documentation'
    })

    # BY_CONCERN collection mappings
    concern_collections: Dict[str, str] = field(default_factory=lambda: {
        'api_contracts': 'arda_api_contracts',
        'database_schemas': 'arda_database_schemas',
        'config': 'arda_config',
        'deployment': 'arda_deployment'
    })

    # Business domain classification patterns
    domain_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        'finance': ['balance', 'transaction', 'payment', 'credit', 'loan', 'pool', 'financial'],
        'auth': ['auth', 'login', 'session', 'magic_link', 'token', 'verification'],
        'ui': ['component', 'modal', 'form', 'button', 'layout', 'page', 'view'],
        'contracts': ['contract', 'solidity', 'ethereum', 'blockchain', 'verifier'],
        'trading': ['trading', 'marketplace', 'deal', 'investment', 'portfolio'],
        'kyc': ['kyc', 'identity', 'verification', 'compliance', 'investor'],
        'notifications': ['notification', 'email', 'alert', 'message']
    })

    # File processing configuration
    skip_dirs: set = field(default_factory=lambda: {
        'target', '.git', 'node_modules', '__pycache__',
        '.pytest_cache', 'dist', 'build', 'public'
    })

    max_file_size: int = 500_000  # 500KB max file size

    # Checkpoint configuration - unified across all languages
    checkpoint_frequency: int = 10  # Save checkpoint every N files processed


@dataclass
class RepositoryConfig:
    """Configuration for a single repository to ingest (legacy - for backward compatibility)."""

    path: str
    repo_id: str
    primary_language: str
    description: str

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'path': self.path,
            'repo_id': self.repo_id,
            'primary_language': self.primary_language,
            'description': self.description
        }


# ===== REPOSITORY CONFIGURATION LOADING =====
# Load repository configurations from YAML file
# Path: config/repositories.yaml (or REPOSITORIES_CONFIG env var)

def _load_repositories_from_config() -> tuple[Dict[str, RepoConfig], Optional[str]]:
    """
    Load repositories from YAML config file.
    
    Returns:
        Tuple of (repositories dict, repos_base_dir)
    """
    try:
        # Avoid circular import by importing here
        from .repository_loader import load_repositories
        
        repos, repos_base_dir = load_repositories(fallback_to_defaults=True)
        return repos, repos_base_dir
    except Exception as e:
        logger.error(f"Failed to load repository configuration: {e}")
        logger.warning("Using in-code fallback configuration")
        return _get_fallback_repositories(), None


def _get_fallback_repositories() -> Dict[str, RepoConfig]:
    """
    Fallback repository configuration in case YAML loading fails.
    
    Returns minimal set of repositories for backward compatibility.
    """
    return {
        "arda-platform": RepoConfig(
            github_url="https://github.com/ardaglobal/arda-platform",
            repo_type=RepoType.FRONTEND,
            languages=[Language.TYPESCRIPT, Language.YAML],
            components=["pages", "components", "api", "config"],
            has_helm=True,
            helm_path="helm/",
            service_dependencies=["arda-credit", "arda-chat-agent", "fastmcp-proxy"],
            priority=PRIORITY_HIGH
        ),
        "arda-credit": RepoConfig(
            github_url="https://github.com/ardaglobal/arda-credit",
            repo_type=RepoType.BACKEND,
            languages=[Language.RUST, Language.YAML, Language.HELM],
            components=["api", "lib", "db", "scripts", "helm"],
            has_helm=True,
            helm_path="helm/",
            service_dependencies=[],
            exposes_apis=True,
            api_base_path="/api/credit",
            priority=PRIORITY_HIGH
        ),
    }


# Load repositories from YAML config file
_LOADED_REPOS, _REPOS_BASE_DIR = _load_repositories_from_config()

# Primary repository configuration (loaded from YAML or fallback)
REPOSITORIES: Dict[str, RepoConfig] = _LOADED_REPOS

# Repository base directory (loaded from YAML or default)
REPOS_BASE_DIR: str = _REPOS_BASE_DIR or "./repos"


# Legacy default repositories (kept for backward compatibility)
DEFAULT_REPOSITORIES = [
    RepositoryConfig(
        path='./repos/arda-platform',
        repo_id='arda-platform',
        primary_language='typescript',
        description='Turborepo monorepo: Platform (auth gateway port 3002), Credit App (investment matching port 3000), IDR (document negotiation port 3001), shared UI packages'
    ),
    RepositoryConfig(
        path='./repos/arda-credit',
        repo_id='arda-credit',
        primary_language='rust',
        description='Rust backend with financial APIs, smart contracts, CLI tools'
    ),
    RepositoryConfig(
        path='./repos/arda-knowledge-hub',
        repo_id='arda-knowledge-hub',
        primary_language='documentation',
        description='Central knowledge repository and wiki: research, technical knowledge, AI knowledge graph, domains, concepts'
    ),
    RepositoryConfig(
        path='./repos/arda-chat-agent',
        repo_id='arda-chat-agent',
        primary_language='typescript',
        description='JavaScript/TypeScript chat agent implementation for Arda platform'
    ),
    RepositoryConfig(
        path='./repos/ari-ui',
        repo_id='ari-ui',
        primary_language='typescript',
        description='JavaScript/TypeScript chat bot implementation for Arda platform'
    )
]


# Service dependency graph for relationship mapping (derived from REPOSITORIES)
# This is kept for backward compatibility but can be derived dynamically
def get_service_dependencies() -> Dict[str, List[str]]:
    """
    Derive service dependencies from repository configurations.
    
    Returns:
        Dictionary mapping repo_id to list of service dependencies
    """
    return {
        repo_id: repo_config.service_dependencies
        for repo_id, repo_config in REPOSITORIES.items()
        if repo_config.service_dependencies
    }


# Static service dependencies (for backward compatibility)
SERVICE_DEPENDENCIES = get_service_dependencies()


# File patterns for indexing by language
FILE_PATTERNS = {
    Language.RUST: ["**/*.rs", "Cargo.toml", "Cargo.lock"],
    Language.TYPESCRIPT: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "package.json", "tsconfig.json"],
    Language.PYTHON: ["**/*.py", "requirements.txt", "pyproject.toml", "setup.py"],
    Language.SOLIDITY: ["**/*.sol"],
    Language.YAML: ["**/*.yaml", "**/*.yml"],
    Language.HELM: ["Chart.yaml", "values.yaml", "templates/**/*.yaml"],
    Language.TERRAFORM: ["**/*.tf", "**/*.tfvars"],
    Language.DOCKERFILE: ["Dockerfile", "*.dockerfile", "**/*.dockerfile"],
    Language.MARKDOWN: ["**/*.md", "README.md"],
    Language.SQL: ["**/*.sql"],
}


# CI/CD patterns to include
CICD_PATTERNS = [
    ".github/workflows/**/*.yml",
    ".github/workflows/**/*.yaml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
]


# File extension to language mapping
EXTENSION_MAPPING = {
    '.rs': 'rust',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.js': 'javascript',
    '.jsx': 'jsx',
    '.sol': 'solidity',
    '.md': 'documentation',
    '.markdown': 'documentation',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.tf': 'terraform',
    '.tfvars': 'terraform',
    '.py': 'python',
    '.sql': 'sql',
}


# ===== COLLECTION MAPPING HELPER FUNCTIONS =====

def determine_service_collection(repo_type: RepoType) -> str:
    """
    Determine the BY_SERVICE collection name from repository type.
    
    Args:
        repo_type: RepoType enum value
        
    Returns:
        Collection name for the service
    """
    mapping = {
        RepoType.FRONTEND: 'arda_frontend',
        RepoType.BACKEND: 'arda_backend',
        RepoType.MIDDLEWARE: 'arda_middleware',
        RepoType.MCP_SERVER: 'arda_middleware',  # MCP servers are middleware
        RepoType.INFRASTRUCTURE: 'arda_infrastructure',
        RepoType.TOOL: 'arda_infrastructure',  # Tools are infrastructure
        RepoType.DOCUMENTATION: 'arda_documentation'
    }
    return mapping.get(repo_type, 'arda_infrastructure')


def determine_concern_collections(
    file_path: str,
    language: str,
    item_type: str,
    content: str = ""
) -> List[str]:
    """
    Determine which BY_CONCERN collections this file should be added to.
    
    Args:
        file_path: Path to the file
        language: Programming language
        item_type: Type of code item (function, class, etc.)
        content: File content for pattern matching
        
    Returns:
        List of concern collection names
    """
    concerns = []
    file_path_lower = file_path.lower()
    content_lower = content.lower() if content else ""
    
    # API Contracts - OpenAPI/Swagger specs, API route definitions
    if any(pattern in file_path_lower for pattern in ['openapi', 'swagger', 'api.yaml', 'api.yml']):
        concerns.append('arda_api_contracts')
    elif language in ['rust', 'typescript', 'python']:
        # Look for API route handlers
        if any(pattern in content_lower for pattern in [
            'router.', 'app.get', 'app.post', '#[get', '#[post',
            'fastapi', 'axum', 'express'
        ]):
            concerns.append('arda_api_contracts')
    
    # Database Schemas - SQL files, ORM models, migrations
    if any(pattern in file_path_lower for pattern in [
        'schema', 'migration', 'models.', 'entities.', '.sql'
    ]):
        concerns.append('arda_database_schemas')
    elif any(pattern in content_lower for pattern in [
        'create table', 'alter table', 'sqlalchemy', 'prisma', 'diesel'
    ]):
        concerns.append('arda_database_schemas')
    
    # Config - Configuration files
    if any(pattern in file_path_lower for pattern in [
        'config', 'settings', '.env', 'values.yaml'
    ]):
        concerns.append('arda_config')
    
    # Deployment - K8s manifests, Helm charts, Terraform, Docker
    if any(pattern in file_path_lower for pattern in [
        'helm', 'k8s', 'kubernetes', 'deployment', 'service.yaml',
        'dockerfile', 'docker-compose', '.tf', 'terraform'
    ]):
        concerns.append('arda_deployment')
    elif language in ['yaml', 'terraform']:
        concerns.append('arda_deployment')
    
    return concerns
