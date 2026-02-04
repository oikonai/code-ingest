"""
Collection Schema and Aliases - Config-Driven

Loads collection names and aliases from shared config/collections.yaml.
This ensures MCP searches the same collections that ingest writes to.

Collections are created and populated by the ingestion system.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional

from .config import load_collections_config, build_collection_schema, get_default_collection

logger = logging.getLogger(__name__)


class CollectionType(Enum):
    """Types of collection organization patterns."""
    LANGUAGE = "language"
    SERVICE = "service"
    CONCERN = "concern"
    UNKNOWN = "unknown"


# Load configuration from shared YAML
_COLLECTIONS_CONFIG = load_collections_config()

# Build schema from config
COLLECTION_SCHEMA: Dict[str, Dict[str, str]] = build_collection_schema(_COLLECTIONS_CONFIG)

# Aliases from config
COLLECTION_ALIASES: Dict[str, str] = _COLLECTIONS_CONFIG.get('aliases', {})

# Default collection for search tools
DEFAULT_COLLECTION = get_default_collection(_COLLECTIONS_CONFIG)

# Default collections for various search patterns
DEFAULT_CODE_COLLECTIONS = list(_COLLECTIONS_CONFIG.get('language', {}).values()) or ['code']
DEFAULT_SERVICE_COLLECTIONS = list(_COLLECTIONS_CONFIG.get('service', {}).values()) or []
DEFAULT_ALL_COLLECTIONS = list(set(
    list(_COLLECTIONS_CONFIG.get('language', {}).values()) +
    list(_COLLECTIONS_CONFIG.get('service', {}).values()) +
    list(_COLLECTIONS_CONFIG.get('concern', {}).values())
))


def resolve_collection_name(name_or_alias: str) -> str:
    """
    Resolve a collection name or alias to the full collection name.
    
    Args:
        name_or_alias: Collection name or alias (e.g., "rust", "code_rust", "myproject_code_rust")
        
    Returns:
        Full collection name (e.g., "code_rust" or with prefix from config)
        
    Examples:
        >>> resolve_collection_name("rust")
        "code_rust"
        >>> resolve_collection_name("code_rust")
        "code_rust"
        >>> resolve_collection_name("ts")
        "code_typescript"
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
        >>> get_collections_by_type(CollectionType.LANGUAGE)
        ["code_rust", "code_typescript", ...] (or with prefix from config)
    """
    return [
        name for name, schema in COLLECTION_SCHEMA.items()
        if schema.get("type") == collection_type.value
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
    Get list of all defined collection names from config.
    
    Returns:
        List of all collection names
    """
    return list(COLLECTION_SCHEMA.keys())


def add_discovered_collection(collection_name: str) -> None:
    """
    Add a collection discovered from vector database to the schema.
    
    This is used when MCP finds collections in the vector database that aren't in the config.
    
    Args:
        collection_name: Name of the discovered collection
    """
    if collection_name not in COLLECTION_SCHEMA:
        COLLECTION_SCHEMA[collection_name] = {
            'type': CollectionType.UNKNOWN.value,
            'description': f'Discovered collection: {collection_name}'
        }
        logger.info(f"Added discovered collection to schema: {collection_name}")
