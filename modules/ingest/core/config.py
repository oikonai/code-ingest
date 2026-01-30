"""
Ingestion Pipeline Configuration

Configuration classes and constants for the multi-language ingestion system.
Following CLAUDE.md: <500 lines, single responsibility (configuration only).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum


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


# Comprehensive repository configurations for all Arda Global repos
REPOSITORIES = {
    # === FRONTEND ===
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
    
    "ari-ui": RepoConfig(
        github_url="https://github.com/ardaglobal/ari-ui",
        repo_type=RepoType.FRONTEND,
        languages=[Language.TYPESCRIPT, Language.YAML],
        components=["bot", "handlers", "config"],
        has_helm=True,
        service_dependencies=["arda-chat-agent"],
        priority=PRIORITY_HIGH
    ),
    
    "arda-homepage": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-homepage",
        repo_type=RepoType.FRONTEND,
        languages=[Language.TYPESCRIPT, Language.YAML],
        components=["pages", "components"],
        has_helm=False,
        priority=PRIORITY_MEDIUM
    ),
    
    # === BACKEND ===
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
    
    # === MIDDLEWARE ===
    "arda-chat-agent": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-chat-agent",
        repo_type=RepoType.MIDDLEWARE,
        languages=[Language.TYPESCRIPT, Language.PYTHON, Language.YAML, Language.HELM],
        components=["agent", "api", "config"],
        has_helm=True,
        helm_path="helm/",
        service_dependencies=["arda-credit", "fastmcp-proxy"],
        exposes_apis=True,
        priority=PRIORITY_HIGH
    ),
    
    "arda-ingest": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-ingest",
        repo_type=RepoType.MIDDLEWARE,
        languages=[Language.PYTHON, Language.RUST, Language.YAML, Language.HELM],
        components=["ingest", "processors", "config"],
        has_helm=True,
        helm_path="helm/",
        service_dependencies=["arda-knowledge-hub"],
        priority=PRIORITY_HIGH
    ),
    
    "arda-collateral-intel": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-collateral-intel",
        repo_type=RepoType.MIDDLEWARE,
        languages=[Language.PYTHON, Language.RUST, Language.YAML, Language.HELM],
        components=["api", "lib", "db", "scripts", "helm"],
        has_helm=True,
        helm_path="helm/",
        service_dependencies=[],
        priority=PRIORITY_HIGH
    ),
    
    "fastmcp-proxy": RepoConfig(
        github_url="https://github.com/ardaglobal/fastmcp-proxy",
        repo_type=RepoType.MIDDLEWARE,
        languages=[Language.PYTHON, Language.YAML, Language.HELM],
        components=["proxy", "config"],
        has_helm=True,
        helm_path="helm/",
        exposes_apis=True,
        priority=PRIORITY_HIGH
    ),
    
    # === MCP SERVERS ===
    "mcp-ardaglobal-code": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-ardaglobal-code",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON, Language.TYPESCRIPT],
        components=["server", "tools", "config"],
        has_helm=False,
        service_dependencies=["i2p"],
        priority=PRIORITY_HIGH
    ),
    
    "mcp-arda-api": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-arda-api",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON, Language.TYPESCRIPT],
        components=["server", "tools"],
        service_dependencies=["arda-credit"],
        priority=PRIORITY_HIGH
    ),
    
    "mcp-arda-vector-documents": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-arda-vector-documents",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_HIGH
    ),
    
    "mcp-knowledge-graph": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-knowledge-graph",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_MEDIUM
    ),
    
    "mcp-arda-knowlege-hub": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-arda-knowlege-hub",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        service_dependencies=["arda-knowledge-hub"],
        has_helm=False,
        priority=PRIORITY_HIGH
    ),
    
    "mcp-sec-edgar": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-sec-edgar",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "mcp-pyth": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-pyth",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "mcp-fred": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-fred",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "mcp-perplexity": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-perplexity",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "mcp-grok": RepoConfig(
        github_url="https://github.com/ardaglobal/mcp-grok",
        repo_type=RepoType.MCP_SERVER,
        languages=[Language.PYTHON],
        components=["server"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    # === INFRASTRUCTURE ===
    "aws-iac": RepoConfig(
        github_url="https://github.com/ardaglobal/aws-iac",
        repo_type=RepoType.INFRASTRUCTURE,
        languages=[Language.TERRAFORM, Language.YAML],
        components=["modules", "environments"],
        has_helm=False,
        priority=PRIORITY_HIGH
    ),
    
    "helm-charts": RepoConfig(
        github_url="https://github.com/ardaglobal/helm-charts",
        repo_type=RepoType.INFRASTRUCTURE,
        languages=[Language.YAML, Language.HELM],
        components=["charts"],
        has_helm=True,
        priority=PRIORITY_HIGH
    ),
    
    "base-containers": RepoConfig(
        github_url="https://github.com/ardaglobal/base-containers",
        repo_type=RepoType.INFRASTRUCTURE,
        languages=[Language.DOCKERFILE, Language.YAML],
        components=["dockerfiles"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "local-panel": RepoConfig(
        github_url="https://github.com/ardaglobal/local-panel",
        repo_type=RepoType.INFRASTRUCTURE,
        languages=[Language.YAML],
        components=["."],  # Index all directories
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    # === TOOLS ===
    "i2p": RepoConfig(
        github_url="https://github.com/ardaglobal/i2p",
        repo_type=RepoType.TOOL,
        languages=[Language.PYTHON, Language.YAML],
        components=["ingest", "core", "config"],
        has_helm=False,
        priority=PRIORITY_HIGH
    ),
    
    "qmdb": RepoConfig(
        github_url="https://github.com/ardaglobal/qmdb",
        repo_type=RepoType.TOOL,
        languages=[Language.PYTHON, Language.SQL],
        components=["src"],
        has_helm=False,
        priority=PRIORITY_LOW
    ),
    
    "arda-dev-metrics": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-dev-metrics",
        repo_type=RepoType.TOOL,
        languages=[Language.PYTHON, Language.TYPESCRIPT],
        components=["frontend", "backend"],
        has_helm=False,
        priority=PRIORITY_MEDIUM
    ),
    
    # === DOCUMENTATION ===
    "docs": RepoConfig(
        github_url="https://github.com/ardaglobal/docs",
        repo_type=RepoType.DOCUMENTATION,
        languages=[Language.MARKDOWN, Language.YAML],
        components=["guides", "api-docs", "architecture"],
        has_helm=False,
        priority=PRIORITY_MEDIUM
    ),

    "arda-knowledge-hub": RepoConfig(
        github_url="https://github.com/ardaglobal/arda-knowledge-hub",
        repo_type=RepoType.DOCUMENTATION,
        languages=[Language.PYTHON, Language.TYPESCRIPT, Language.YAML],
        components=["guides", "api-docs", "architecture"],
        has_helm=True,
        priority=PRIORITY_MEDIUM
    ),

    "aig": RepoConfig(
        github_url="https://github.com/ardaglobal/aig",
        repo_type=RepoType.DOCUMENTATION,
        languages=[Language.MARKDOWN],
        components=["."],  # Index all markdown content
        has_helm=False,
        priority=PRIORITY_HIGH
    ),
}


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


# Service dependency graph for relationship mapping
SERVICE_DEPENDENCIES = {
    "arda-platform": ["arda-credit", "arda-chat-agent", "fastmcp-proxy"],
    "arda-chat-agent": ["arda-credit", "fastmcp-proxy", "mcp-arda-api"],
    "ari-ui": ["arda-chat-agent"],
    "arda-ingest": ["arda-knowledge-hub"],
    "mcp-ardaglobal-code": ["i2p"],
    "mcp-arda-api": ["arda-credit"],
    "mcp-arda-knowlege-hub": ["arda-knowledge-hub"],
}


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
