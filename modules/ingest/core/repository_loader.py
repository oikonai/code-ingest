"""
Repository Configuration Loader

Loads repository configurations from YAML file and converts to RepoConfig objects.
Following CLAUDE.md: <500 lines, single responsibility (load and validate repo config).
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from .config import RepoConfig, RepoType, Language, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW

logger = logging.getLogger(__name__)


# Mapping from string values in YAML to enum values
REPO_TYPE_MAPPING = {
    'frontend': RepoType.FRONTEND,
    'backend': RepoType.BACKEND,
    'middleware': RepoType.MIDDLEWARE,
    'mcp_server': RepoType.MCP_SERVER,
    'infrastructure': RepoType.INFRASTRUCTURE,
    'tool': RepoType.TOOL,
    'documentation': RepoType.DOCUMENTATION,
}

LANGUAGE_MAPPING = {
    'rust': Language.RUST,
    'typescript': Language.TYPESCRIPT,
    'python': Language.PYTHON,
    'solidity': Language.SOLIDITY,
    'yaml': Language.YAML,
    'helm': Language.HELM,
    'terraform': Language.TERRAFORM,
    'dockerfile': Language.DOCKERFILE,
    'markdown': Language.MARKDOWN,
    'sql': Language.SQL,
    'javascript': Language.JAVASCRIPT,
    'jsx': Language.JSX,
    'tsx': Language.TSX,
}


def _resolve_config_path(config_path: Optional[Path] = None) -> Path:
    """
    Resolve the configuration file path.
    
    Priority:
    1. Explicit config_path parameter
    2. REPOSITORIES_CONFIG environment variable
    3. Default: config/repositories.yaml (relative to project root)
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        Resolved Path object
    """
    if config_path:
        return config_path
    
    # Check environment variable
    env_path = os.getenv('REPOSITORIES_CONFIG')
    if env_path:
        return Path(env_path)
    
    # Default path: config/repositories.yaml from project root
    # Assume project root is 4 levels up from this file
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / 'config' / 'repositories.yaml'


def _validate_repo_type(repo_type_str: str, repo_id: str) -> RepoType:
    """
    Validate and convert repo_type string to enum.
    
    Args:
        repo_type_str: String value from YAML
        repo_id: Repository ID for error messages
        
    Returns:
        RepoType enum value
        
    Raises:
        ValueError: If repo_type is invalid
    """
    if repo_type_str not in REPO_TYPE_MAPPING:
        valid_types = ', '.join(REPO_TYPE_MAPPING.keys())
        raise ValueError(
            f"Invalid repo_type '{repo_type_str}' for repository '{repo_id}'. "
            f"Valid values: {valid_types}"
        )
    return REPO_TYPE_MAPPING[repo_type_str]


def _validate_languages(language_strs: List[str], repo_id: str) -> List[Language]:
    """
    Validate and convert language strings to enums.
    
    Args:
        language_strs: List of language strings from YAML
        repo_id: Repository ID for error messages
        
    Returns:
        List of Language enum values
        
    Raises:
        ValueError: If any language is invalid
    """
    languages = []
    for lang_str in language_strs:
        if lang_str not in LANGUAGE_MAPPING:
            valid_languages = ', '.join(sorted(LANGUAGE_MAPPING.keys()))
            raise ValueError(
                f"Invalid language '{lang_str}' for repository '{repo_id}'. "
                f"Valid values: {valid_languages}"
            )
        languages.append(LANGUAGE_MAPPING[lang_str])
    return languages


def _validate_priority(priority_str: str, repo_id: str) -> str:
    """
    Validate priority string.
    
    Args:
        priority_str: Priority string from YAML
        repo_id: Repository ID for error messages
        
    Returns:
        Validated priority string
        
    Raises:
        ValueError: If priority is invalid
    """
    valid_priorities = [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]
    if priority_str not in valid_priorities:
        raise ValueError(
            f"Invalid priority '{priority_str}' for repository '{repo_id}'. "
            f"Valid values: {', '.join(valid_priorities)}"
        )
    return priority_str


def _build_repo_config(repo_data: Dict[str, Any]) -> RepoConfig:
    """
    Build a RepoConfig object from YAML data.
    
    Args:
        repo_data: Dictionary from YAML for a single repository
        
    Returns:
        RepoConfig object
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Extract and validate required fields
    repo_id = repo_data.get('id')
    if not repo_id:
        raise ValueError("Repository missing required field: 'id'")
    
    github_url = repo_data.get('github_url')
    if not github_url:
        raise ValueError(f"Repository '{repo_id}' missing required field: 'github_url'")
    
    repo_type_str = repo_data.get('repo_type')
    if not repo_type_str:
        raise ValueError(f"Repository '{repo_id}' missing required field: 'repo_type'")
    
    language_strs = repo_data.get('languages')
    if not language_strs or not isinstance(language_strs, list):
        raise ValueError(
            f"Repository '{repo_id}' missing or invalid required field: 'languages' "
            "(must be a list)"
        )
    
    components = repo_data.get('components')
    if not components or not isinstance(components, list):
        raise ValueError(
            f"Repository '{repo_id}' missing or invalid required field: 'components' "
            "(must be a list)"
        )
    
    priority_str = repo_data.get('priority')
    if not priority_str:
        raise ValueError(f"Repository '{repo_id}' missing required field: 'priority'")
    
    # Validate and convert enums
    repo_type = _validate_repo_type(repo_type_str, repo_id)
    languages = _validate_languages(language_strs, repo_id)
    priority = _validate_priority(priority_str, repo_id)
    
    # Extract optional fields
    has_helm = repo_data.get('has_helm', False)
    helm_path = repo_data.get('helm_path')
    service_dependencies = repo_data.get('service_dependencies', [])
    exposes_apis = repo_data.get('exposes_apis', False)
    api_base_path = repo_data.get('api_base_path')
    
    # Build RepoConfig
    return RepoConfig(
        github_url=github_url,
        repo_type=repo_type,
        languages=languages,
        components=components,
        has_helm=has_helm,
        helm_path=helm_path,
        service_dependencies=service_dependencies,
        exposes_apis=exposes_apis,
        api_base_path=api_base_path,
        priority=priority
    )


def load_repositories(
    config_path: Optional[Path] = None,
    fallback_to_defaults: bool = False
) -> tuple[Dict[str, RepoConfig], Optional[str]]:
    """
    Load repository configurations from YAML file.
    
    Args:
        config_path: Optional explicit path to config file
        fallback_to_defaults: If True, return empty dict on file not found;
                             if False, raise error
        
    Returns:
        Tuple of (repositories dict keyed by id, repos_base_dir or None)
        
    Raises:
        FileNotFoundError: If config file not found and fallback_to_defaults=False
        ValueError: If YAML is invalid or contains errors
        yaml.YAMLError: If YAML parsing fails
    """
    config_file = _resolve_config_path(config_path)
    
    # Check if file exists
    if not config_file.exists():
        if fallback_to_defaults:
            logger.warning(
                f"⚠️  Repository config file not found at {config_file}. "
                "Using in-code defaults."
            )
            return {}, None
        else:
            raise FileNotFoundError(
                f"Repository configuration file not found: {config_file}. "
                f"Create the file or set REPOSITORIES_CONFIG environment variable."
            )
    
    # Load YAML
    logger.info(f"📖 Loading repository configuration from {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML file {config_file}: {e}")
    
    if not config_data or not isinstance(config_data, dict):
        raise ValueError(f"Invalid YAML structure in {config_file}: expected a dictionary")
    
    # Extract repos_base_dir
    repos_base_dir = config_data.get('repos_base_dir')
    
    # Extract repositories list
    repos_list = config_data.get('repositories')
    if not repos_list:
        logger.warning(f"⚠️  No repositories defined in {config_file}")
        return {}, repos_base_dir
    
    if not isinstance(repos_list, list):
        raise ValueError(
            f"Invalid 'repositories' field in {config_file}: expected a list"
        )
    
    # Build repository dict
    repositories = {}
    seen_ids = set()
    
    for idx, repo_data in enumerate(repos_list):
        if not isinstance(repo_data, dict):
            raise ValueError(
                f"Invalid repository entry at index {idx} in {config_file}: "
                "expected a dictionary"
            )
        
        try:
            repo_config = _build_repo_config(repo_data)
            repo_id = repo_data['id']
            
            # Check for duplicate IDs
            if repo_id in seen_ids:
                raise ValueError(
                    f"Duplicate repository ID '{repo_id}' in {config_file}"
                )
            
            seen_ids.add(repo_id)
            repositories[repo_id] = repo_config
            
        except (ValueError, KeyError) as e:
            raise ValueError(
                f"Error loading repository at index {idx} in {config_file}: {e}"
            )
    
    logger.info(f"✅ Loaded {len(repositories)} repositories from {config_file}")
    
    return repositories, repos_base_dir
