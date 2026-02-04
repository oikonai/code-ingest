"""
Core Ingestion Pipeline Components

Main orchestration and processing logic for the ingestion system.
"""

from .pipeline import IngestionPipeline
from .config import (
    IngestionConfig, 
    RepositoryConfig, 
    DEFAULT_REPOSITORIES,
    REPOSITORIES,
    REPOS_BASE_DIR
)
from .vector_backend import (
    create_vector_backend,
    VectorBackend,
    VectorPoint
)
from .checkpoint_manager import CheckpointManager
from .embedding_service import EmbeddingService
from .storage_manager import StorageManager
from .batch_processor import BatchProcessor
from .file_processor import FileProcessor

__all__ = [
    'IngestionPipeline',
    'IngestionConfig',
    'RepositoryConfig',
    'DEFAULT_REPOSITORIES',
    'REPOSITORIES',
    'REPOS_BASE_DIR',
    'create_vector_backend',
    'VectorBackend',
    'VectorPoint',
    'CheckpointManager',
    'EmbeddingService',
    'StorageManager',
    'BatchProcessor',
    'FileProcessor',
]
