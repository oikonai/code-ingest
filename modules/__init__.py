"""
Code Ingestion System

Multi-language code ingestion pipeline for GitHub repositories.
Supports Rust, TypeScript/JavaScript, Solidity, and documentation.
"""

from .ingest import IngestionPipeline, IngestionConfig, RepositoryConfig, DEFAULT_REPOSITORIES

__all__ = [
    'IngestionPipeline',
    'IngestionConfig',
    'RepositoryConfig',
    'DEFAULT_REPOSITORIES',
]