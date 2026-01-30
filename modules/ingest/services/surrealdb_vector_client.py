"""
SurrealDB Vector Database Client

Handles connection to SurrealDB instance and manages vector operations
for the embedding pipeline.

Following CLAUDE.md guidelines:
- Under 500 lines
- Single responsibility: SurrealDB vector operations
- 4096-dimensional vectors from Qwen3-Embedding-8B
"""

import os
import uuid
import logging
import re
from typing import List, Dict, Any, Optional
from surrealdb import Surreal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class SurrealDBVectorClient:
    """
    SurrealDB client for managing vectors with 4096 dimensions.
    Matches the embedding dimensions from Qwen3-Embedding-8B.
    
    Each "collection" maps to a SurrealDB table with:
    - id field
    - vector field (array of floats)
    - payload fields (metadata)
    - HNSW index on vector field
    """
    
    def __init__(self, embedding_size: int = 4096):
        """
        Initialize SurrealDB client with credentials from .env
        
        Args:
            embedding_size: Dimension of embedding vectors (default: 4096)
        """
        self.url = os.getenv('SURREALDB_URL', 'http://localhost:8000')
        self.namespace = os.getenv('SURREALDB_NS', 'code_ingest')
        self.database = os.getenv('SURREALDB_DB', 'vectors')
        self.username = os.getenv('SURREALDB_USER', 'root')
        self.password = os.getenv('SURREALDB_PASS', 'root')
        
        self.embedding_size = embedding_size
        
        logger.info(f"🔗 Connecting to SurrealDB at {self.url}...")
        logger.info(f"   Namespace: {self.namespace}, Database: {self.database}")
        
        # Initialize synchronous client
        self.client = Surreal(self.url)
        
        try:
            # Sign in
            self.client.signin({"user": self.username, "pass": self.password})
            
            # Use namespace and database
            self.client.use(self.namespace, self.database)
            
            logger.info("✅ SurrealDB client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to connect to SurrealDB: {e}")
            raise RuntimeError(f"SurrealDB connection failed: {e}") from e
    
    def _sanitize_table_name(self, collection_name: str) -> str:
        """
        Sanitize collection name to be a valid SurrealDB table name.
        
        Args:
            collection_name: Original collection name
            
        Returns:
            Sanitized table name (alphanumeric + underscore only)
        """
        # Replace hyphens and other non-alphanumeric chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', collection_name)
        # Ensure starts with letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = f"tbl_{sanitized}"
        return sanitized
    
    def create_collection(self, collection_name: str, recreate: bool = False) -> bool:
        """
        Create a collection (table) for storing embeddings.
        
        Args:
            collection_name: Name of the collection
            recreate: Whether to delete and recreate if exists
            
        Returns:
            True if collection was created or already exists
        """
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            # Check if table exists
            result = self.client.query(
                f"INFO FOR TABLE {table_name};"
            )
            table_exists = bool(result and len(result) > 0)
            
            if table_exists and recreate:
                logger.info(f"🗑️ Deleting existing table: {table_name}")
                self.client.query(f"REMOVE TABLE {table_name};")
                table_exists = False
            
            if not table_exists:
                logger.info(f"📦 Creating table: {table_name}")
                
                # Define table with schema
                self.client.query(f"""
                    DEFINE TABLE {table_name} SCHEMAFULL;
                    DEFINE FIELD vector ON TABLE {table_name} TYPE array;
                    DEFINE FIELD payload ON TABLE {table_name} TYPE object;
                """)
                
                # Create HNSW index on vector field
                # SurrealDB HNSW syntax: DEFINE INDEX <name> ON <table> FIELDS <field> HNSW DIMENSION <n> [DIST <metric>]
                self.client.query(f"""
                    DEFINE INDEX vector_idx ON TABLE {table_name} 
                    FIELDS vector 
                    HNSW DIMENSION {self.embedding_size} 
                    DIST COSINE;
                """)
                
                logger.info(f"✅ Table '{table_name}' created with {self.embedding_size}D HNSW index")
            else:
                logger.info(f"✅ Table '{table_name}' already exists")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create table '{collection_name}': {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a collection.
        
        Returns:
            Collection info dict or None if not found
        """
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            # Query table info
            result = self.client.query(f"INFO FOR TABLE {table_name};")
            
            if not result or len(result) == 0:
                return None
            
            # Count records
            count_result = self.client.query(f"SELECT count() FROM {table_name} GROUP ALL;")
            count = 0
            if count_result and len(count_result) > 0 and isinstance(count_result[0], dict):
                count = count_result[0].get('count', 0)
            
            return {
                'name': table_name,
                'status': 'ready',
                'vectors_count': count,
                'indexed_vectors_count': count,  # SurrealDB indexes immediately
                'embedding_size': self.embedding_size
            }
            
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
                    'vector': List[float],
                    'payload': Dict[str, Any]
                }
                
        Returns:
            True if successful
        """
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            for vec in vectors:
                if len(vec['vector']) != self.embedding_size:
                    raise ValueError(
                        f"Vector dimension mismatch: expected {self.embedding_size}, "
                        f"got {len(vec['vector'])}"
                    )
                
                # Sanitize ID for SurrealDB record ID format
                record_id = vec['id'].replace('-', '_')
                
                # Upsert record using UPDATE or CREATE
                # SurrealDB syntax: UPDATE table:id SET field = value, field2 = value2
                self.client.query(
                    f"""
                    UPDATE {table_name}:`{record_id}` SET
                        vector = $vector,
                        payload = $payload
                    """,
                    {
                        'vector': vec['vector'],
                        'payload': vec.get('payload', {})
                    }
                )
            
            logger.info(f"✅ Upserted {len(vectors)} vectors to '{table_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert vectors: {e}")
            return False
    
    def upsert_points(
        self,
        collection_name: str,
        points: List
    ) -> bool:
        """
        Insert or update points in the collection.
        
        Compatible with VectorPoint objects and dict-like objects.
        
        Args:
            collection_name: Target collection
            points: List of point objects
            
        Returns:
            True if successful
        """
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            for point in points:
                # Extract fields
                point_id = point.id if hasattr(point, 'id') else str(point['id'])
                vector = point.vector if hasattr(point, 'vector') else point['vector']
                payload = point.payload if hasattr(point, 'payload') else point.get('payload', {})
                
                if len(vector) != self.embedding_size:
                    raise ValueError(
                        f"Vector dimension mismatch: expected {self.embedding_size}, "
                        f"got {len(vector)}"
                    )
                
                # Sanitize ID
                record_id = str(point_id).replace('-', '_')
                
                # Upsert record
                self.client.query(
                    f"""
                    UPDATE {table_name}:`{record_id}` SET
                        vector = $vector,
                        payload = $payload
                    """,
                    {
                        'vector': vector,
                        'payload': payload
                    }
                )
            
            logger.info(f"✅ Upserted {len(points)} points to '{table_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert points: {e}")
            return False
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors using KNN.
        
        Args:
            collection_name: Collection to search
            query_vector: Query embedding
            limit: Maximum results to return
            score_threshold: Minimum similarity score (cosine similarity, 0-1)
            filter_conditions: Optional metadata filters (not yet implemented)
            
        Returns:
            List of search results with scores and payloads
        """
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            if len(query_vector) != self.embedding_size:
                raise ValueError(
                    f"Query vector dimension mismatch: expected {self.embedding_size}, "
                    f"got {len(query_vector)}"
                )
            
            # SurrealDB vector search using KNN operator
            # Syntax: WHERE vector <|limit|> $query_vector
            # Returns records ordered by distance (closest first)
            query = f"""
                SELECT 
                    id, 
                    payload,
                    vector::similarity::cosine(vector, $query_vector) AS score
                FROM {table_name}
                WHERE vector <|{limit}|> $query_vector
                ORDER BY score DESC
            """
            
            results = self.client.query(query, {'query_vector': query_vector})
            
            # Format results
            formatted_results = []
            if results and len(results) > 0:
                for result in results[0]:  # First result set
                    # Check score threshold (cosine similarity: 1 = identical, 0 = orthogonal)
                    score = result.get('score', 0)
                    if score >= score_threshold:
                        formatted_results.append({
                            'id': str(result.get('id', '')),
                            'score': score,
                            'payload': result.get('payload', {})
                        })
            
            logger.info(f"🔍 Found {len(formatted_results)} results in '{table_name}'")
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
            table_name = self._sanitize_table_name(collection_name)
            
            for vec_id in vector_ids:
                record_id = str(vec_id).replace('-', '_')
                self.client.query(f"DELETE {table_name}:`{record_id}`;")
            
            logger.info(f"🗑️ Deleted {len(vector_ids)} vectors from '{table_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete vectors: {e}")
            return False
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics about a collection."""
        try:
            table_name = self._sanitize_table_name(collection_name)
            
            # Count records
            count_result = self.client.query(f"SELECT count() FROM {table_name} GROUP ALL;")
            count = 0
            if count_result and len(count_result) > 0 and isinstance(count_result[0], dict):
                count = count_result[0].get('count', 0)
            
            return {
                'name': table_name,
                'status': 'ready',
                'vectors_count': count,
                'indexed_vectors_count': count,
                'points_count': count,
                'config': {
                    'vector_size': self.embedding_size,
                    'distance_metric': 'cosine'
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get collection stats: {e}")
            return {}
    
    def get_collections(self) -> List[str]:
        """
        List all collection (table) names.
        
        Returns:
            List of collection names
        """
        try:
            # Query all tables in the database
            result = self.client.query("INFO FOR DB;")
            
            tables = []
            if result and len(result) > 0:
                db_info = result[0]
                if isinstance(db_info, dict) and 'tables' in db_info:
                    tables = list(db_info['tables'].keys())
            
            return tables
        except Exception as e:
            logger.error(f"❌ Failed to get collections: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check SurrealDB connection health."""
        try:
            # Try a simple query
            self.client.query("SELECT 1;")
            
            collections = self.get_collections()
            
            return {
                'status': 'healthy',
                'connected': True,
                'backend_type': 'surrealdb',
                'collections_count': len(collections),
                'collections': collections,
                'embedding_dimensions': self.embedding_size,
                'namespace': self.namespace,
                'database': self.database
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'connected': False,
                'backend_type': 'surrealdb',
                'error': str(e),
                'embedding_dimensions': self.embedding_size
            }


def main():
    """Test the SurrealDB client."""
    try:
        client = SurrealDBVectorClient()
        
        # Health check
        health = client.health_check()
        logger.info(f"🏥 Health check: {health}")
        
        # Test collection creation
        test_collection = "test_embeddings"
        success = client.create_collection(test_collection, recreate=True)
        
        if success:
            # Get collection info
            info = client.get_collection_info(test_collection)
            if info:
                logger.info(f"📊 Collection info: {info}")
            
            # Test vector insertion
            test_vectors = [
                {
                    'id': 'test-1',
                    'vector': [0.1] * 4096,
                    'payload': {'source': 'test', 'content': 'Hello world'}
                }
            ]
            
            client.upsert_vectors(test_collection, test_vectors)
            
            # Test search
            query = [0.1] * 4096
            results = client.search_vectors(test_collection, query, limit=5)
            logger.info(f"🔍 Search results: {len(results)} matches")
            if results:
                logger.info(f"   Top result score: {results[0]['score']}")
            
            # Get stats
            stats = client.get_collection_stats(test_collection)
            logger.info(f"📈 Collection stats: {stats}")
        
        logger.info("✅ SurrealDB client test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    main()
