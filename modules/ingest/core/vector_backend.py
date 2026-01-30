"""
Vector Backend Abstraction

Provides a common interface for vector database backends (Qdrant, SurrealDB).
Allows switching between backends via configuration.

Following CLAUDE.md: <500 lines, single responsibility (backend abstraction).
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Point Structure (shared between backends)
# ============================================================================

@dataclass
class VectorPoint:
    """
    Common structure for vector points across backends.
    Maps to PointStruct for Qdrant, custom structure for SurrealDB.
    """
    id: str
    vector: List[float]
    payload: Dict[str, Any]


# ============================================================================
# Vector Backend Protocol
# ============================================================================

class VectorBackend(Protocol):
    """
    Protocol defining the interface for vector database backends.
    
    This allows both Qdrant and SurrealDB implementations to be used
    interchangeably through a common interface.
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
    backend_type: Optional[str] = None,
    embedding_size: int = 4096
) -> VectorBackend:
    """
    Factory function to create vector backend based on configuration.
    
    Args:
        backend_type: Type of backend ('qdrant' or 'surrealdb'). 
                     If None, reads from VECTOR_BACKEND env var.
        embedding_size: Size of embedding vectors (default: 4096)
        
    Returns:
        Configured vector backend instance
        
    Raises:
        ValueError: If backend_type is invalid or required env vars are missing
    """
    if backend_type is None:
        backend_type = os.getenv('VECTOR_BACKEND', 'qdrant').lower()
    
    logger.info(f"🔧 Creating vector backend: {backend_type}")
    
    if backend_type == 'qdrant':
        from ..services.vector_client import QdrantVectorClient
        return QdrantVectorClient()
    
    elif backend_type == 'surrealdb':
        from ..services.surrealdb_vector_client import SurrealDBVectorClient
        return SurrealDBVectorClient(embedding_size=embedding_size)
    
    else:
        raise ValueError(
            f"Unknown vector backend type: '{backend_type}'. "
            f"Must be 'qdrant' or 'surrealdb'. "
            f"Set VECTOR_BACKEND environment variable."
        )


# ============================================================================
# Backend Type Detection
# ============================================================================

def get_backend_type() -> str:
    """
    Get the configured backend type from environment.
    
    Returns:
        Backend type string ('qdrant' or 'surrealdb')
    """
    return os.getenv('VECTOR_BACKEND', 'qdrant').lower()


def is_surrealdb_backend() -> bool:
    """Check if SurrealDB backend is configured."""
    return get_backend_type() == 'surrealdb'


def is_qdrant_backend() -> bool:
    """Check if Qdrant backend is configured."""
    return get_backend_type() == 'qdrant'
