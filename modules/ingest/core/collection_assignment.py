"""
Collection Assignment Logic for Multi-Collection Storage

Determines which collections (BY_LANGUAGE, BY_SERVICE, BY_CONCERN) a code chunk
should be stored in based on repository type, file type, and content analysis.

Following CLAUDE.md: <500 lines, single responsibility (collection assignment only).
"""

import logging
from typing import List, Any, Optional
from pathlib import Path

from .config import RepoConfig, determine_service_collection, determine_concern_collections

logger = logging.getLogger(__name__)


class CollectionAssigner:
    """
    Assigns code chunks to multiple collections based on analysis.
    
    Handles three collection types:
    1. BY_LANGUAGE - Based on programming language (e.g., code_rust, {prefix}_code_rust)
    2. BY_SERVICE - Based on repository type (e.g., frontend, backend)
    3. BY_CONCERN - Based on architectural concern (e.g., api_contracts, deployment)
    
    Collection names come from config/collections.yaml.
    """
    
    def __init__(self, config):
        """
        Initialize collection assigner.
        
        Args:
            config: IngestionConfig instance with collection mappings
        """
        self.config = config
        logger.info("🎯 Collection assigner initialized")
    
    def get_target_collections(
        self,
        chunk: Any,
        repo_config: RepoConfig,
        language: str,
        file_path: Optional[str] = None
    ) -> List[str]:
        """
        Determine all target collections for a code chunk.
        
        Args:
            chunk: Code chunk object (RustCodeChunk, TypeScriptCodeChunk, etc.)
            repo_config: Repository configuration
            language: Programming language
            file_path: Optional file path (uses chunk.file_path if not provided)
            
        Returns:
            List of collection names to store the chunk in
        """
        collections = []
        
        # Use file_path from parameter or chunk
        if file_path is None:
            file_path = getattr(chunk, 'file_path', '')
        
        # 1. BY_LANGUAGE collection (always included)
        language_collection = self._get_language_collection(language)
        if language_collection:
            collections.append(language_collection)
        
        # 2. BY_SERVICE collection
        service_collection = self._get_service_collection(repo_config)
        if service_collection and service_collection not in collections:
            collections.append(service_collection)
        
        # 3. BY_CONCERN collections (can be multiple)
        concern_collections = self._get_concern_collections(
            file_path=file_path,
            language=language,
            chunk=chunk,
            repo_config=repo_config
        )
        for concern in concern_collections:
            if concern not in collections:
                collections.append(concern)
        
        logger.debug(
            f"📌 Assigned {len(collections)} collections for {Path(file_path).name}: "
            f"{', '.join(collections)}"
        )
        
        return collections
    
    def _get_language_collection(self, language: str) -> Optional[str]:
        """
        Get BY_LANGUAGE collection name.
        
        Args:
            language: Programming language
            
        Returns:
            Collection name or None
        """
        return self.config.collections.get(language)
    
    def _get_service_collection(self, repo_config: RepoConfig) -> Optional[str]:
        """
        Get BY_SERVICE collection name from repository type.
        
        Args:
            repo_config: Repository configuration
            
        Returns:
            Collection name or None
        """
        return determine_service_collection(repo_config.repo_type, self.config.service_collections)
    
    def _get_concern_collections(
        self,
        file_path: str,
        language: str,
        chunk: Any,
        repo_config: RepoConfig
    ) -> List[str]:
        """
        Get BY_CONCERN collection names based on file analysis.
        
        Args:
            file_path: Path to the file
            language: Programming language
            chunk: Code chunk object
            repo_config: Repository configuration
            
        Returns:
            List of concern collection names
        """
        # Extract content for analysis
        content = getattr(chunk, 'content', '')
        item_type = getattr(chunk, 'item_type', 'unknown')
        
        # Use helper function from config
        concerns = determine_concern_collections(
            file_path=file_path,
            language=language,
            item_type=item_type,
            content=content,
            concern_collections=self.config.concern_collections
        )
        
        # Additional logic based on repo config
        # Get collection names from config
        api_contracts_collection = self.config.concern_collections.get('api_contracts', 'api_contracts')
        deployment_collection = self.config.concern_collections.get('deployment', 'deployment')
        
        # If repo has API endpoints, and this is an API file, add to api_contracts
        if repo_config.exposes_apis and repo_config.api_base_path:
            if 'api' in file_path.lower() or 'route' in file_path.lower():
                if api_contracts_collection not in concerns:
                    concerns.append(api_contracts_collection)
        
        # If repo has Helm charts, deployment files go to deployment collection
        if repo_config.has_helm:
            if any(pattern in file_path.lower() for pattern in ['helm', 'chart', 'values']):
                if deployment_collection not in concerns:
                    concerns.append(deployment_collection)
        
        return concerns
    
    def get_collection_stats(self, collections: List[str]) -> dict:
        """
        Get statistics about collection assignments.
        
        Args:
            collections: List of assigned collection names
            
        Returns:
            Dictionary with collection type counts
        """
        stats = {
            'by_language': 0,
            'by_service': 0,
            'by_concern': 0,
            'total': len(collections)
        }
        
        for collection in collections:
            # Check if it's a language collection
            if collection in self.config.collections.values():
                stats['by_language'] += 1
            
            # Check if it's a service collection
            if collection in self.config.service_collections.values():
                stats['by_service'] += 1
            
            # Check if it's a concern collection
            if collection in self.config.concern_collections.values():
                stats['by_concern'] += 1
        
        return stats


def get_all_collection_names(config) -> List[str]:
    """
    Get list of all possible collection names.
    
    Args:
        config: IngestionConfig instance
        
    Returns:
        List of all unique collection names
    """
    all_collections = set()
    
    # Add language collections
    all_collections.update(config.collections.values())
    
    # Add service collections
    all_collections.update(config.service_collections.values())
    
    # Add concern collections
    all_collections.update(config.concern_collections.values())
    
    return sorted(list(all_collections))

