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


def _derive_repo_id_from_url(github_url: str) -> str:
    """Derive repo id (name) from GitHub URL. Last path segment, no trailing slash."""
    if not github_url or 'github.com' not in github_url:
        return ''
    return (github_url.rstrip('/').split('/')[-1] or '')


def _build_repo_config(repo_data: Dict[str, Any]) -> RepoConfig:
    """
    Build a RepoConfig object from YAML data.

    Only github_url is required. id, repo_type, languages, components, and priority
    are derived or defaulted when missing (minimal entry support).
    
    Args:
        repo_data: Dictionary from YAML for a single repository
        
    Returns:
        RepoConfig object
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    github_url = repo_data.get('github_url')
    if not github_url or not isinstance(github_url, str):
        raise ValueError("Repository missing required field: 'github_url'")
    if 'github.com' not in github_url:
        raise ValueError(
            f"Repository 'github_url' must be a GitHub URL (got: {github_url[:50]}...)"
        )
    path_segments = github_url.rstrip('/').split('/')
    if not path_segments or not path_segments[-1]:
        raise ValueError(
            f"Repository 'github_url' must include repo name in path (got: {github_url})"
        )

    repo_id = repo_data.get('id')
    if not repo_id:
        repo_id = _derive_repo_id_from_url(github_url)
    if not repo_id:
        raise ValueError("Could not derive repository id from 'github_url'")

    repo_type_str = repo_data.get('repo_type')
    if repo_type_str:
        repo_type = _validate_repo_type(repo_type_str, repo_id)
    else:
        repo_type = RepoType.BACKEND

    language_strs = repo_data.get('languages')
    if language_strs and isinstance(language_strs, list):
        languages = _validate_languages(language_strs, repo_id)
    else:
        languages = [Language.RUST, Language.YAML]

    components = repo_data.get('components')
    if not components or not isinstance(components, list):
        components = ['.']
    else:
        components = list(components)

    priority_str = repo_data.get('priority')
    if priority_str:
        priority = _validate_priority(priority_str, repo_id)
    else:
        priority = PRIORITY_MEDIUM

    has_helm = repo_data.get('has_helm', False)
    helm_path = repo_data.get('helm_path')
    service_dependencies = repo_data.get('service_dependencies', [])
    exposes_apis = repo_data.get('exposes_apis', False)
    api_base_path = repo_data.get('api_base_path')

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
        if not repo_data.get('github_url'):
            raise ValueError(
                f"Repository entry at index {idx} in {config_file} missing required 'github_url'"
            )

        try:
            repo_id = repo_data.get('id') or _derive_repo_id_from_url(
                repo_data['github_url']
            )
            if not repo_id:
                raise ValueError(
                    f"Could not derive id from github_url at index {idx}"
                )

            repo_config = _build_repo_config(repo_data)

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

    repositories = _merge_discovered_config(repositories, config_file)
    repositories = _merge_relationships_config(repositories, config_file)

    logger.info(f"✅ Loaded {len(repositories)} repositories from {config_file}")
    
    return repositories, repos_base_dir


def _resolve_discovered_path(base_config_file: Path) -> Path:
    """Resolve path to repositories-discovered.yaml. Env REPOSITORIES_DISCOVERED_CONFIG overrides."""
    env_path = os.getenv('REPOSITORIES_DISCOVERED_CONFIG')
    if env_path:
        return Path(env_path)
    return base_config_file.parent / 'repositories-discovered.yaml'


def _merge_discovered_config(
    repositories: Dict[str, RepoConfig], base_config_file: Path
) -> Dict[str, RepoConfig]:
    """Overlay discovered config (has_helm, helm_path, languages, repo_type) when file exists."""
    discovered_path = _resolve_discovered_path(base_config_file)
    if not discovered_path.exists():
        return repositories

    try:
        with open(discovered_path, 'r') as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Could not load discovered config {discovered_path}: {e}")
        return repositories

    if not data or not isinstance(data, dict):
        return repositories
    repos_overlay = data.get('repos') or data.get('repositories')
    if not repos_overlay or not isinstance(repos_overlay, dict):
        return repositories

    logger.info(f"📖 Merging discovered config from {discovered_path}")
    result = {}
    for repo_id, config in repositories.items():
        over = repos_overlay.get(repo_id) if isinstance(repos_overlay.get(repo_id), dict) else None
        if not over:
            result[repo_id] = config
            continue
        repo_type = _validate_repo_type(over['repo_type'], repo_id) if 'repo_type' in over else config.repo_type
        languages = _validate_languages(over['languages'], repo_id) if 'languages' in over else config.languages
        has_helm = over['has_helm'] if 'has_helm' in over else config.has_helm
        helm_path = over['helm_path'] if 'helm_path' in over else config.helm_path
        result[repo_id] = RepoConfig(
            github_url=config.github_url,
            repo_type=repo_type,
            languages=languages,
            components=config.components,
            has_helm=has_helm,
            helm_path=helm_path,
            service_dependencies=config.service_dependencies,
            exposes_apis=config.exposes_apis,
            api_base_path=config.api_base_path,
            priority=config.priority,
        )
    return result


def _resolve_relationships_path(base_config_file: Path) -> Path:
    """Resolve path to repositories-relationships.yaml. Env REPOSITORIES_RELATIONSHIPS_CONFIG overrides."""
    env_path = os.getenv('REPOSITORIES_RELATIONSHIPS_CONFIG')
    if env_path:
        return Path(env_path)
    return base_config_file.parent / 'repositories-relationships.yaml'


def _merge_relationships_config(
    repositories: Dict[str, RepoConfig], base_config_file: Path
) -> Dict[str, RepoConfig]:
    """Overlay service_dependencies from relationships file when present. User-set deps in base win."""
    rel_path = _resolve_relationships_path(base_config_file)
    if not rel_path.exists():
        return repositories

    try:
        with open(rel_path, 'r') as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Could not load relationships config {rel_path}: {e}")
        return repositories

    if not data or not isinstance(data, dict):
        return repositories
    repos_overlay = data.get('repos') or data.get('repositories')
    if not repos_overlay or not isinstance(repos_overlay, dict):
        return repositories

    logger.info(f"📖 Merging relationships from {rel_path}")
    result = {}
    for repo_id, config in repositories.items():
        over = repos_overlay.get(repo_id) if isinstance(repos_overlay.get(repo_id), dict) else None
        if not over or 'service_dependencies' not in over:
            result[repo_id] = config
            continue
        # User override wins: only use derived when base did not set service_dependencies
        use_deps = config.service_dependencies if config.service_dependencies else (over.get('service_dependencies') or [])
        result[repo_id] = RepoConfig(
            github_url=config.github_url,
            repo_type=config.repo_type,
            languages=config.languages,
            components=config.components,
            has_helm=config.has_helm,
            helm_path=config.helm_path,
            service_dependencies=use_deps,
            exposes_apis=config.exposes_apis,
            api_base_path=config.api_base_path,
            priority=config.priority,
        )
    return result
