"""
MCP Server Configuration

Loads collection names and aliases from shared config/collections.yaml.
This ensures MCP searches the same collections that ingest writes to.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _apply_prefix(prefix: Optional[str], suffix: str) -> str:
    """Build full collection name from prefix and suffix. No prefix => suffix as-is."""
    if prefix and str(prefix).strip():
        return f"{str(prefix).strip()}_{suffix}"
    return suffix


def load_collections_config() -> Dict:
    """
    Load collections configuration from config/collections.yaml.
    
    Returns:
        Dictionary with 'language', 'service', 'concern', 'aliases', 'default' keys.
        Returns empty dicts if file not found (MCP will discover from Qdrant).
    """
    try:
        # Check COLLECTIONS_CONFIG env var first
        config_path = os.getenv('COLLECTIONS_CONFIG', 'config/collections.yaml')
        
        # Try relative to MCP server location, then up to workspace root
        if not Path(config_path).is_absolute():
            # Try relative to mcp/ directory (workspace root)
            workspace_root = Path(__file__).parent.parent.parent
            config_path = workspace_root / config_path
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"Collections config not found at {config_path}")
            logger.info("MCP will discover collections from Qdrant and use no aliases")
            return {
                'language': {},
                'service': {},
                'concern': {},
                'aliases': {},
                'default': None
            }
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            logger.warning(f"Collections config at {config_path} is empty")
            return {
                'language': {},
                'service': {},
                'concern': {},
                'aliases': {},
                'default': None
            }
        
        prefix = (data.get('collection_prefix') or '') or None
        if prefix is not None:
            prefix = str(prefix).strip() or None
        
        def apply(suffix: str) -> str:
            return _apply_prefix(prefix, suffix)
        
        raw_lang = data.get('language_collections', {})
        raw_svc = data.get('service_collections', {})
        raw_concern = data.get('concern_collections', {})
        raw_aliases = data.get('aliases', {})
        
        result = {
            'language': {k: apply(v) for k, v in raw_lang.items() if v},
            'service': {k: apply(v) for k, v in raw_svc.items() if v},
            'concern': {k: apply(v) for k, v in raw_concern.items() if v},
            'aliases': {k: apply(v) for k, v in raw_aliases.items() if v},
            'default': apply(data['default_collection']) if data.get('default_collection') else None,
            'prefix': data.get('collection_prefix')
        }
        
        logger.info(f"✅ Loaded collections config from {config_path}")
        logger.info(f"   Languages: {len(result['language'])} collections")
        logger.info(f"   Services: {len(result['service'])} collections")
        logger.info(f"   Concerns: {len(result['concern'])} collections")
        logger.info(f"   Aliases: {len(result['aliases'])} shortcuts")
        if result['default']:
            logger.info(f"   Default collection: {result['default']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to load collections config: {e}")
        logger.info("MCP will discover collections from Qdrant")
        return {
            'language': {},
            'service': {},
            'concern': {},
            'aliases': {},
            'default': None
        }


def build_collection_schema(config: Dict) -> Dict[str, Dict[str, str]]:
    """
    Build COLLECTION_SCHEMA from loaded config.
    
    Args:
        config: Config dict from load_collections_config()
    
    Returns:
        Dict mapping collection_name -> {'type': ..., 'description': ...}
    """
    schema = {}
    
    # Add language collections
    for lang, collection_name in config.get('language', {}).items():
        if collection_name and collection_name not in schema:
            schema[collection_name] = {
                'type': 'language',
                'description': f'{lang.title()} code across all repositories'
            }
    
    # Add service collections
    for service, collection_name in config.get('service', {}).items():
        if collection_name and collection_name not in schema:
            schema[collection_name] = {
                'type': 'service',
                'description': f'{service.replace("_", " ").title()} services'
            }
    
    # Add concern collections
    for concern, collection_name in config.get('concern', {}).items():
        if collection_name and collection_name not in schema:
            schema[collection_name] = {
                'type': 'concern',
                'description': f'{concern.replace("_", " ").title()}'
            }
    
    return schema


def get_default_collection(config: Dict) -> str:
    """
    Get default collection for search tools.
    
    Args:
        config: Config dict from load_collections_config()
    
    Returns:
        Default collection name (from config or first language collection)
    """
    # Use explicit default if set
    if config.get('default'):
        return config['default']
    
    # Otherwise use first language collection
    language_collections = config.get('language', {})
    if language_collections:
        return list(language_collections.values())[0]
    
    # Fallback to generic name
    return 'code'
