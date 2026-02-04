"""
Vector Backend Abstraction

Provides a common interface for the SurrealDB vector database backend.

Following CLAUDE.md: <500 lines, single responsibility (backend abstraction).
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Point Structure
# ============================================================================

@dataclass
class VectorPoint:
    """
    Common structure for vector points.
    Used by SurrealDB backend for vector storage operations.
    """
    id: str
    vector: List[float]
    payload: Dict[str, Any]


# ============================================================================
# Vector Backend Protocol
# ============================================================================

class VectorBackend(Protocol):
    """
    Protocol defining the interface for the SurrealDB vector database backend.
    
    Provides a consistent interface for vector storage and search operations.
    """
    
    @property
    def embedding_size(self) -> int:
        """Get the expected embedding dimension size."""
        ...
    
    def create_collection(self, collection_name: str, recreate: bool = False) -> bool:
        """
        Create a collection for storing embeddings.
        
        Args:
            collection_name: Name of the collection
            recreate: Whether to delete and recreate if exists
            
        Returns:
            True if collection was created or already exists
        """
        ...
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a collection.
        
        Returns:
            Collection info dict or None if not found
        """
        ...
    
    def upsert_vectors(
        self, 
        collection_name: str, 
        vectors: List[Dict[str, Any]]
    ) -> bool:
        """
        Insert or update vectors in the collection.
        
        Args:
            collection_name: Target collection
            vectors: List of vector dictionaries with format:
                {
                    'id': str,
                    'vector': List[float],
                    'payload': Dict[str, Any]
                }
                
        Returns:
            True if successful
        """
        ...
    
    def upsert_points(
        self,
        collection_name: str,
        points: List[VectorPoint]
    ) -> bool:
        """
        Insert or update points in the collection.
        
        Similar to upsert_vectors but uses VectorPoint structure.
        Used by StorageManager for batch operations.
        
        Args:
            collection_name: Target collection
            points: List of VectorPoint objects
            
        Returns:
            True if successful
        """
        ...
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            collection_name: Collection to search
            query_vector: Query embedding
            limit: Maximum results to return
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters
            
        Returns:
            List of search results with format:
                {
                    'id': str,
                    'score': float,
                    'payload': Dict[str, Any]
                }
        """
        ...
    
    def delete_vectors(
        self,
        collection_name: str,
        vector_ids: List[str]
    ) -> bool:
        """
        Delete vectors by IDs.
        
        Args:
            collection_name: Target collection
            vector_ids: List of vector IDs to delete
            
        Returns:
            True if successful
        """
        ...
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics about a collection.
        
        Returns:
            Statistics dictionary with keys like:
                - status
                - vectors_count
                - indexed_vectors_count
        """
        ...
    
    def get_collections(self) -> List[str]:
        """
        List all collection names.
        
        Returns:
            List of collection names
        """
        ...
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check backend connection health.
        
        Returns:
            Health status dictionary with keys:
                - status: 'healthy' or 'unhealthy'
                - connected: bool
                - collections_count: int
                - backend_type: str
        """
        ...


# ============================================================================
# Backend Factory
# ============================================================================

def create_vector_backend(
    embedding_size: int = 4096
) -> VectorBackend:
    """
    Factory function to create SurrealDB vector backend.
    
    Args:
        embedding_size: Size of embedding vectors (default: 4096)
        
    Returns:
        Configured SurrealDB vector backend instance
        
    Raises:
        RuntimeError: If SurrealDB connection fails or required env vars are missing
    """
    logger.info("🔧 Creating SurrealDB vector backend")
    
    from ..services.surrealdb_vector_client import SurrealDBVectorClient
    return SurrealDBVectorClient(embedding_size=embedding_size)
