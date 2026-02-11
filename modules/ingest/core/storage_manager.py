"""
Storage Manager for Vector Database Operations

Handles vector storage operations with SurrealDB vector database.
Following CLAUDE.md: <500 lines, single responsibility (storage operations only).
"""

import logging
import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Any
from .vector_backend import VectorPoint

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages vector storage operations with SurrealDB.

    Responsibilities:
    - Setup collections
    - Store code chunk vectors
    - Store documentation vectors
    - Validate vector dimensions
    """

    def __init__(self, vector_client, embedding_size: int = 4096):
        """
        Initialize storage manager.

        Args:
            vector_client: SurrealDB vector client instance
            embedding_size: Expected embedding dimension
        """
        self.vector_client = vector_client
        self.embedding_size = embedding_size
        logger.info(f"💾 Storage manager initialized (dimension: {embedding_size})")

    def setup_collections(self, collections: Dict[str, str]) -> bool:
        """
        Setup all required vector database collections.

        Args:
            collections: Dict mapping language to collection name

        Returns:
            True if all collections setup successfully
        """
        # Get all unique collection names from config
        from .collection_assignment import get_all_collection_names
        from .config import IngestionConfig
        
        config = IngestionConfig()
        all_collection_names = get_all_collection_names(config)
        
        logger.info(f"📦 Setting up {len(all_collection_names)} collections...")
        
        for collection_name in all_collection_names:
            logger.info(f"📦 Setting up collection: {collection_name}")
            success = self.vector_client.create_collection(
                collection_name=collection_name,
                recreate=False
            )

            if not success:
                logger.error(f"❌ Failed to setup collection: {collection_name}")
                return False

        logger.info("✅ All collections ready")
        return True

    def store_code_vectors(
        self,
        chunks: List[Any],  # RustCodeChunk objects
        embeddings: List[List[float]],
        collection_name: str,
        language: str
    ) -> int:
        """
        Store code chunk vectors in vector database (single collection).
        
        DEPRECATED: Use store_code_vectors_multi_collection() for multi-collection support.

        Args:
            chunks: List of code chunk objects
            embeddings: Corresponding embedding vectors
            collection_name: Target collection
            language: Programming language

        Returns:
            Number of vectors stored successfully
        """
        return self.store_code_vectors_multi_collection(
            chunks, embeddings, [collection_name], language
        )
    
    def store_code_vectors_multi_collection(
        self,
        chunks: List[Any],  # RustCodeChunk objects
        embeddings: List[List[float]],
        collection_names: List[str],
        language: str
    ) -> int:
        """
        Store code chunk vectors in multiple vector database collections.

        Args:
            chunks: List of code chunk objects
            embeddings: Corresponding embedding vectors
            collection_names: List of target collections
            language: Programming language

        Returns:
            Number of vectors stored successfully
        """
        if len(chunks) != len(embeddings):
            logger.error(
                f"❌ Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings"
            )
            return 0

        if not collection_names:
            logger.warning("⚠️ No collection names provided, skipping storage")
            return 0

        # Current timestamp for indexed_at
        indexed_at = datetime.utcnow().isoformat() + 'Z'

        vectors = []

        for chunk, embedding in zip(chunks, embeddings):
            # Create unique hash from chunk location
            chunk_hash = hashlib.sha256(
                f"{chunk.file_path}:{chunk.item_name}:{chunk.start_line}".encode()
            ).hexdigest()

            # Build enhanced payload with all metadata
            payload = {
                # Core identification
                "file_path": chunk.file_path,
                "item_name": chunk.item_name,
                "item_type": chunk.item_type,
                "language": language,
                "repo_id": chunk.metadata.get('repo_id', 'unknown'),
                "repo_component": chunk.metadata.get('repo_component', 'unknown'),
                "github_url": chunk.metadata.get('github_url', ''),
                "repo_org": chunk.metadata.get('repo_org', ''),
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                
                # Classification
                "business_domain": chunk.metadata.get('business_domain', 'unknown'),
                "complexity_score": chunk.metadata.get('complexity_score', 0.0),
                "line_count": chunk.metadata.get('line_count', 0),
                
                # Service and architecture
                "service_type": chunk.metadata.get('service_type'),
                
                # Content preview
                "content_preview": (
                    chunk.content[:200] + "..."
                    if len(chunk.content) > 200
                    else chunk.content
                ),
                
                # Dependencies and relationships
                "imports": chunk.metadata.get('imports', []),
                "api_endpoints": chunk.metadata.get('api_endpoints', []),
                "api_consumes": chunk.metadata.get('api_consumes', []),
                "depends_on_services": chunk.metadata.get('depends_on_services', []),
                
                # Infrastructure metadata
                "k8s_resource_type": chunk.metadata.get('k8s_resource_type'),
                "helm_chart_name": chunk.metadata.get('helm_chart_name'),
                "container_images": chunk.metadata.get('container_images', []),
                "env_vars": chunk.metadata.get('env_vars', []),
                "ports": chunk.metadata.get('ports', []),
                
                # Embedding metadata
                "embedding_model": "Qwen3-Embedding-8B",
                "embedding_dimensions": self.embedding_size,
                "indexed_at": indexed_at
            }

            vectors.append({
                'id': chunk_hash,
                'vector': embedding,
                'payload': payload
            })

        # Store in all target collections
        total_stored = 0
        for collection_name in collection_names:
            success = self.vector_client.upsert_vectors(collection_name, vectors)
            if success:
                total_stored += len(vectors)
                logger.debug(f"✅ Stored {len(vectors)} vectors in {collection_name}")
            else:
                logger.error(f"❌ Failed to store vectors in {collection_name}")
        
        return len(vectors) if total_stored > 0 else 0

    def store_doc_vectors(
        self,
        doc_chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        collection_name: str
    ) -> int:
        """
        Store documentation vectors in vector database (single collection).
        
        DEPRECATED: Use store_doc_vectors_multi_collection() for multi-collection support.

        Args:
            doc_chunks: List of documentation chunk dictionaries
            embeddings: Corresponding embedding vectors
            collection_name: Target collection

        Returns:
            Number of vectors stored successfully
        """
        return self.store_doc_vectors_multi_collection(
            doc_chunks, embeddings, [collection_name]
        )
    
    def store_doc_vectors_multi_collection(
        self,
        doc_chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        collection_names: List[str]
    ) -> int:
        """
        Store documentation vectors in multiple vector database collections.

        Args:
            doc_chunks: List of documentation chunk dictionaries
            embeddings: Corresponding embedding vectors
            collection_names: List of target collections

        Returns:
            Number of vectors stored successfully
        """
        if len(doc_chunks) != len(embeddings):
            logger.error(
                f"❌ Mismatch: {len(doc_chunks)} doc chunks vs {len(embeddings)} embeddings"
            )
            return 0

        if not collection_names:
            logger.warning("⚠️ No collection names provided, skipping storage")
            return 0

        # Current timestamp for indexed_at
        indexed_at = datetime.utcnow().isoformat() + 'Z'

        points = []

        for doc_chunk, embedding in zip(doc_chunks, embeddings):
            point = VectorPoint(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    'content': doc_chunk.get('content_preview', ''),
                    'file_path': doc_chunk.get('file_path', ''),
                    'item_name': doc_chunk.get('section_title', 'Documentation'),
                    'item_type': doc_chunk.get('chunk_type', 'section'),
                    'language': 'documentation',
                    'repo_id': doc_chunk.get('repo_id', 'unknown'),
                    'repo_component': doc_chunk.get('repo_component', 'documentation'),
                    'github_url': doc_chunk.get('github_url', ''),
                    'repo_org': doc_chunk.get('repo_org', ''),
                    'business_domain': doc_chunk.get('business_domain', 'general'),
                    'service_type': doc_chunk.get('service_type'),
                    'doc_type': doc_chunk.get('doc_type', 'general'),
                    'line_count': doc_chunk.get('line_count', 0),
                    'char_count': doc_chunk.get('char_count', 0),
                    'importance_score': doc_chunk.get('importance_score', 0.5),
                    # Embedding metadata
                    'embedding_model': 'Qwen3-Embedding-8B',
                    'embedding_dimensions': self.embedding_size,
                    'indexed_at': indexed_at
                }
            )
            points.append(point)

        # Store in all target collections
        total_stored = 0
        for collection_name in collection_names:
            try:
                self.vector_client.upsert_points(
                    collection_name=collection_name,
                    points=points
                )
                total_stored += len(points)
                logger.debug(f"✅ Stored {len(points)} doc vectors in {collection_name}")
            except Exception as e:
                logger.error(f"❌ Failed to store documentation batch in {collection_name}: {e}")
        
        return len(points) if total_stored > 0 else 0

    def validate_vector_dimensions(self, embeddings: List[List[float]]) -> bool:
        """
        Validate that all embeddings have correct dimensions.

        Args:
            embeddings: List of embedding vectors

        Returns:
            True if all valid, False if any mismatch
        """
        for i, embedding in enumerate(embeddings):
            if len(embedding) != self.embedding_size:
                logger.error(
                    f"❌ Vector {i+1} dimension mismatch: "
                    f"expected {self.embedding_size}, got {len(embedding)}"
                )
                return False

        return True
