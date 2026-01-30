"""
Collection Schema and Aliases for Arda MCP Server

Defines the structure and naming conventions for vector collections in Qdrant.
Collections are populated by the i2p ingestion system; this module provides
schema definitions and convenient aliases for accessing them.
"""

from enum import Enum
from typing import Dict, List, Optional


class CollectionType(Enum):
    """Types of collection organization patterns."""
    BY_LANGUAGE = "language"
    BY_REPO = "repo"
    BY_SERVICE = "service"
    BY_CONCERN = "concern"


# Collection Schema
# =================
# Defines all expected collections and their purposes.
# Collections are created and populated by i2p ingestion system.

COLLECTION_SCHEMA: Dict[str, Dict[str, str]] = {
    # === BY LANGUAGE ===
    "arda_code_rust": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All Rust code across Arda ecosystem"
    },
    "arda_code_typescript": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All TypeScript code across Arda ecosystem"
    },
    "arda_code_solidity": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All Solidity smart contracts"
    },
    "arda_code_python": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All Python code across Arda ecosystem"
    },
    "arda_code_yaml": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All YAML configs, K8s manifests, Helm charts"
    },
    "arda_code_terraform": {
        "type": CollectionType.BY_LANGUAGE.value,
        "description": "All Terraform IaC configurations"
    },
    
    # === BY REPOSITORY ===
    "arda_repo_platform": {
        "type": CollectionType.BY_REPO.value,
        "description": "arda-platform frontend code"
    },
    "arda_repo_credit": {
        "type": CollectionType.BY_REPO.value,
        "description": "arda-credit backend code"
    },
    "arda_repo_chat_agent": {
        "type": CollectionType.BY_REPO.value,
        "description": "arda-chat-agent middleware"
    },
    "arda_repo_infrastructure": {
        "type": CollectionType.BY_REPO.value,
        "description": "aws-iac, helm-charts, infrastructure code"
    },
    
    # === BY SERVICE TYPE ===
    "arda_frontend": {
        "type": CollectionType.BY_SERVICE.value,
        "description": "All frontend code (platform, homepage, ari-ui)"
    },
    "arda_backend": {
        "type": CollectionType.BY_SERVICE.value,
        "description": "All backend services"
    },
    "arda_middleware": {
        "type": CollectionType.BY_SERVICE.value,
        "description": "All middleware services"
    },
    "arda_infrastructure": {
        "type": CollectionType.BY_SERVICE.value,
        "description": "All infrastructure code"
    },
    
    # === BY ARCHITECTURAL CONCERN ===
    "arda_api_contracts": {
        "type": CollectionType.BY_CONCERN.value,
        "description": "All API endpoint definitions and contracts"
    },
    "arda_database_schemas": {
        "type": CollectionType.BY_CONCERN.value,
        "description": "All database models and schemas"
    },
    "arda_config": {
        "type": CollectionType.BY_CONCERN.value,
        "description": "All configuration files"
    },
    "arda_deployment": {
        "type": CollectionType.BY_CONCERN.value,
        "description": "All Helm charts, K8s manifests, deployment configs"
    },
    "arda_documentation": {
        "type": CollectionType.BY_CONCERN.value,
        "description": "All documentation, READMEs, architecture docs"
    },
}


# Collection Aliases
# ==================
# Convenient shortcuts for accessing collections by common names

COLLECTION_ALIASES: Dict[str, str] = {
    # Language aliases
    "rust": "arda_code_rust",
    "typescript": "arda_code_typescript",
    "ts": "arda_code_typescript",
    "python": "arda_code_python",
    "py": "arda_code_python",
    "yaml": "arda_code_yaml",
    "helm": "arda_code_yaml",
    "terraform": "arda_code_terraform",
    "tf": "arda_code_terraform",
    "solidity": "arda_code_solidity",
    "sol": "arda_code_solidity",
    
    # Repository aliases
    "platform": "arda_repo_platform",
    "credit": "arda_repo_credit",
    "chat": "arda_repo_chat_agent",
    "infrastructure": "arda_repo_infrastructure",
    
    # Service type aliases
    "frontend": "arda_frontend",
    "backend": "arda_backend",
    "middleware": "arda_middleware",
    "infra": "arda_infrastructure",
    
    # Concern aliases
    "api": "arda_api_contracts",
    "db": "arda_database_schemas",
    "database": "arda_database_schemas",
    "config": "arda_config",
    "deployment": "arda_deployment",
    "deploy": "arda_deployment",
    "docs": "arda_documentation",
}


def resolve_collection_name(name_or_alias: str) -> str:
    """
    Resolve a collection name or alias to the full collection name.
    
    Args:
        name_or_alias: Collection name or alias (e.g., "rust", "arda_code_rust")
    
    Returns:
        Full collection name (e.g., "arda_code_rust")
    
    Examples:
        >>> resolve_collection_name("rust")
        "arda_code_rust"
        >>> resolve_collection_name("arda_code_rust")
        "arda_code_rust"
        >>> resolve_collection_name("ts")
        "arda_code_typescript"
    """
    # If it's already a full collection name, return it
    if name_or_alias in COLLECTION_SCHEMA:
        return name_or_alias
    
    # Try to resolve as alias
    if name_or_alias in COLLECTION_ALIASES:
        return COLLECTION_ALIASES[name_or_alias]
    
    # If not found, return as-is (let caller handle validation)
    return name_or_alias


def get_collections_by_type(collection_type: CollectionType) -> List[str]:
    """
    Get all collection names of a specific type.
    
    Args:
        collection_type: The type of collections to retrieve
    
    Returns:
        List of collection names matching the type
    
    Examples:
        >>> get_collections_by_type(CollectionType.BY_LANGUAGE)
        ["arda_code_rust", "arda_code_typescript", ...]
    """
    return [
        name for name, schema in COLLECTION_SCHEMA.items()
        if schema["type"] == collection_type.value
    ]


def get_collection_info(collection_name: str) -> Optional[Dict[str, str]]:
    """
    Get schema information for a collection.
    
    Args:
        collection_name: Name of the collection
    
    Returns:
        Dictionary with type and description, or None if not found
    """
    return COLLECTION_SCHEMA.get(collection_name)


def get_all_collection_names() -> List[str]:
    """
    Get list of all defined collection names.
    
    Returns:
        List of all collection names
    """
    return list(COLLECTION_SCHEMA.keys())


# Default collections for various search patterns
DEFAULT_CODE_COLLECTIONS = [
    "arda_code_rust",
    "arda_code_typescript",
    "arda_code_solidity"
]

DEFAULT_SERVICE_COLLECTIONS = [
    "arda_frontend",
    "arda_backend",
    "arda_middleware",
    "arda_infrastructure"
]

DEFAULT_ALL_COLLECTIONS = get_all_collection_names()

