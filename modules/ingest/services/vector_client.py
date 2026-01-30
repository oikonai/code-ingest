"""
Qdrant Vector Database Client

Handles connection to Qdrant cloud instance and manages vector operations
for the embedding pipeline.

Following AGENTS.md guidelines:
- Under 400 lines
- Single responsibility: Qdrant vector operations
- 4096-dimensional vectors from Qwen3-Embedding-8B
"""

import os
import uuid
import logging
from typing import List, Dict, Any, Optional, Union
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    CollectionInfo,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    QueryRequest
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class QdrantVectorClient:
    """
    Qdrant client for managing vectors with 4096 dimensions.
    Matches the embedding dimensions from Qwen3-Embedding-8B.
    """
    
    def __init__(self):
        """Initialize Qdrant client with credentials from .env"""
        self.url = os.getenv('QDRANT_URL')
        self.api_key = os.getenv('QDRANT_API_KEY')
        
        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        
        logger.info(f"🔗 Connecting to Qdrant at {self.url[:50]}...")
        
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=120  # Increased from 60s to 120s for better reliability
        )
        
        # Vector dimensions from Qwen3-Embedding-8B
        self.embedding_size = 4096
        
        logger.info("✅ Qdrant client initialized")
    
    def create_collection(self, collection_name: str, recreate: bool = False) -> bool:
        """
        Create a collection for storing embeddings.
        
        Args:
            collection_name: Name of the collection
            recreate: Whether to delete and recreate if exists
            
        Returns:
            True if collection was created or already exists
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_exists = any(c.name == collection_name for c in collections)
            
            if collection_exists and recreate:
                logger.info(f"🗑️ Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
                collection_exists = False
            
            if not collection_exists:
                logger.info(f"📦 Creating collection: {collection_name}")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_size,  # 4096 dimensions
                        distance=Distance.COSINE   # Cosine similarity
                    )
                )
                logger.info(f"✅ Collection '{collection_name}' created with {self.embedding_size}D vectors")
            else:
                logger.info(f"✅ Collection '{collection_name}' already exists")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create collection '{collection_name}': {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        """Get information about a collection."""
        try:
            return self.client.get_collection(collection_name)
        except Exception as e:
            logger.error(f"❌ Failed to get collection info: {e}")
            return None
    
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
                    'vector': List[float],  # 4096 dimensions
                    'payload': Dict[str, Any]  # metadata
                }
                
        Returns:
            True if successful
        """
        try:
            points = []
            
            for vec in vectors:
                if len(vec['vector']) != self.embedding_size:
                    raise ValueError(
                        f"Vector dimension mismatch: expected {self.embedding_size}, "
                        f"got {len(vec['vector'])}"
                    )
                
                # Convert string IDs to UUID if needed
                point_id = vec['id']
                if isinstance(point_id, str):
                    try:
                        point_id = uuid.UUID(point_id)
                    except ValueError:
                        # Generate UUID from string hash
                        point_id = uuid.uuid5(uuid.NAMESPACE_URL, point_id)
                
                points.append(PointStruct(
                    id=str(point_id),
                    vector=vec['vector'],
                    payload=vec.get('payload', {})
                ))
            
            result = self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.info(f"✅ Upserted {len(points)} vectors to '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert vectors: {e}")
            return False
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Optional[Filter] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            collection_name: Collection to search
            query_vector: Query embedding (4096 dimensions)
            limit: Maximum results to return
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters
            
        Returns:
            List of search results with scores and payloads
        """
        try:
            if len(query_vector) != self.embedding_size:
                raise ValueError(
                    f"Query vector dimension mismatch: expected {self.embedding_size}, "
                    f"got {len(query_vector)}"
                )
            
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter_conditions
            ).points
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'score': result.score,
                    'payload': result.payload
                })
            
            logger.info(f"🔍 Found {len(formatted_results)} results in '{collection_name}'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def delete_vectors(
        self,
        collection_name: str,
        vector_ids: List[str]
    ) -> bool:
        """Delete vectors by IDs."""
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=vector_ids
            )
            logger.info(f"🗑️ Deleted {len(vector_ids)} vectors from '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete vectors: {e}")
            return False
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics about a collection."""
        try:
            info = self.client.get_collection(collection_name)
            return {
                'status': info.status,
                'vectors_count': info.vectors_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'points_count': info.points_count,
                'segments_count': info.segments_count,
                'config': {
                    'vector_size': info.config.params.vectors.size,
                    'distance_metric': info.config.params.vectors.distance.value
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get collection stats: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """Check Qdrant connection health."""
        try:
            collections = self.client.get_collections()
            return {
                'status': 'healthy',
                'connected': True,
                'collections_count': len(collections.collections),
                'collections': [c.name for c in collections.collections],
                'embedding_dimensions': self.embedding_size
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e),
                'embedding_dimensions': self.embedding_size
            }

def main():
    """Test the Qdrant client."""
    try:
        client = QdrantVectorClient()
        
        # Health check
        health = client.health_check()
        logger.info(f"🏥 Health check: {health}")
        
        # Test collection creation
        test_collection = "test-embeddings"
        success = client.create_collection(test_collection, recreate=True)
        
        if success:
            # Get collection info
            info = client.get_collection_info(test_collection)
            if info:
                logger.info(f"📊 Collection info: {info.vectors_count} vectors, status: {info.status}")
            
            # Test vector insertion
            test_vectors = [
                {
                    'id': 'test-1',
                    'vector': [0.1] * 4096,  # 4096 dimensions
                    'payload': {'source': 'test', 'content': 'Hello world'}
                }
            ]
            
            client.upsert_vectors(test_collection, test_vectors)
            
            # Test search
            query = [0.1] * 4096
            results = client.search_vectors(test_collection, query, limit=5)
            logger.info(f"🔍 Search results: {len(results)} matches")
            
            # Get stats
            stats = client.get_collection_stats(test_collection)
            logger.info(f"📈 Collection stats: {stats}")
            
        logger.info("✅ Qdrant client test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()