"""
Vector Ingestion System

Multi-language code ingestion pipeline for Arda repositories.
Supports Rust, TypeScript/JavaScript, Solidity, and documentation.
"""

from .core.pipeline import IngestionPipeline
from .core.config import (
    IngestionConfig, 
    RepositoryConfig, 
    DEFAULT_REPOSITORIES,
    REPOSITORIES,
    REPOS_BASE_DIR
)

# For backward compatibility
MultiLanguageIngestionPipeline = IngestionPipeline

__all__ = [
    'IngestionPipeline',
    'IngestionConfig',
    'RepositoryConfig',
    'DEFAULT_REPOSITORIES',
    'REPOSITORIES',
    'REPOS_BASE_DIR',
    'MultiLanguageIngestionPipeline',  # Backward compatibility
]
