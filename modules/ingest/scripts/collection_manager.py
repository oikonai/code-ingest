#!/usr/bin/env python3
"""
Vector Database Collection Manager

CLI tool for managing Qdrant collections: cleanup, status, and creation.
Replaces verbose inline Python scripts in GitHub Actions workflows.

Following CLAUDE.md: <500 lines, single responsibility (collection management only).

Usage:
    python collection_manager.py cleanup
    python collection_manager.py status
    python collection_manager.py status --format json
    python collection_manager.py create --collection code_python
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.ingest.services.vector_client import QdrantVectorClient
from modules.ingest.core.config import IngestionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Manages Qdrant vector database collections.
    
    Features:
    - Clean/recreate all collections
    - Get comprehensive collection statistics
    - Create new collections
    - Health checks
    """
    
    def __init__(self):
        """Initialize collection manager with vector client."""
        self.client = QdrantVectorClient()
        self.config = IngestionConfig()
    
    def cleanup_all(self, collections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Clean up (recreate) all or specified collections.
        
        Args:
            collections: List of collection names to clean, or None for all
            
        Returns:
            Dictionary with cleanup results
        """
        # Default to all collections
        if collections is None:
            collections = list(self.config.collections.values())
            # Remove duplicates
            collections = list(set(collections))
        
        logger.info(f"🗑️  Cleaning {len(collections)} collections...")
        
        results = {}
        for collection in collections:
            try:
                logger.info(f"  ♻️  Recreating {collection}...")
                self.client.create_collection(collection, recreate=True)
                results[collection] = 'success'
                logger.info(f"  ✅ {collection} recreated")
            except Exception as e:
                logger.error(f"  ❌ Failed to recreate {collection}: {e}")
                results[collection] = f'error: {e}'
        
        success_count = sum(1 for v in results.values() if v == 'success')
        logger.info(f"\n✅ Cleaned {success_count}/{len(collections)} collections")
        
        return {
            'total': len(collections),
            'success': success_count,
            'failed': len(collections) - success_count,
            'results': results
        }
    
    def get_status(self, format: str = 'text') -> Dict[str, Any]:
        """
        Get comprehensive status of all collections.
        
        Args:
            format: Output format ('text', 'json', 'github-actions')
            
        Returns:
            Dictionary with collection statistics
        """
        # Get unique collections
        collections = list(set(self.config.collections.values()))
        
        stats = {
            'collections': {},
            'total_vectors': 0,
            'total_indexed': 0
        }
        
        for collection_name in collections:
            try:
                info = self.client.client.get_collection(collection_name)
                
                # Extract language from collection name
                lang = collection_name.split('_')[-1]
                
                stats['collections'][lang] = {
                    'name': collection_name,
                    'vectors': info.points_count or 0,
                    'indexed': info.indexed_vectors_count or 0,
                    'status': info.status.name if hasattr(info.status, 'name') else str(info.status)
                }
                
                stats['total_vectors'] += info.points_count or 0
                stats['total_indexed'] += info.indexed_vectors_count or 0
            
            except Exception as e:
                logger.warning(f"⚠️  Could not get status for {collection_name}: {e}")
                stats['collections'][collection_name] = {
                    'error': str(e)
                }
        
        # Format output
        if format == 'json':
            print(json.dumps(stats, indent=2))
        elif format == 'github-actions':
            self._print_github_actions_format(stats)
        else:
            self._print_text_format(stats)
        
        return stats
    
    def _print_text_format(self, stats: Dict[str, Any]):
        """Print statistics in human-readable text format."""
        logger.info("\n📊 Vector Database Status:")
        logger.info("=" * 60)
        
        for lang, data in stats['collections'].items():
            if 'error' in data:
                logger.error(f"  ❌ {lang}: {data['error']}")
            else:
                vectors = data['vectors']
                indexed = data['indexed']
                status = data['status']
                logger.info(
                    f"  📦 {lang.upper()}: {vectors:,} vectors "
                    f"({indexed:,} indexed, {status})"
                )
        
        logger.info(f"\n🏆 Total: {stats['total_vectors']:,} vectors "
                   f"({stats['total_indexed']:,} indexed)")
        logger.info("=" * 60)
    
    def _print_github_actions_format(self, stats: Dict[str, Any]):
        """Print statistics in GitHub Actions format (for step outputs)."""
        for lang, data in stats['collections'].items():
            if 'error' not in data:
                print(f"{lang}_vectors={data['vectors']}")
                print(f"{lang}_indexed={data['indexed']}")
        
        print(f"total_vectors={stats['total_vectors']}")
        print(f"total_indexed={stats['total_indexed']}")
    
    def create_collection(
        self,
        collection_name: str,
        recreate: bool = False
    ) -> bool:
        """
        Create a new collection.
        
        Args:
            collection_name: Name of collection to create
            recreate: If True, delete and recreate if exists
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"📦 Creating collection: {collection_name}")
            self.client.create_collection(collection_name, recreate=recreate)
            logger.info(f"✅ Collection {collection_name} created")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create {collection_name}: {e}")
            return False
    
    def health_check(self) -> bool:
        """
        Perform health check on vector database.
        
        Returns:
            True if healthy
        """
        try:
            # Try to list collections
            collections = self.client.client.get_collections()
            
            logger.info("✅ Vector database is healthy")
            logger.info(f"  Collections: {len(collections.collections)}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Vector database health check failed: {e}")
            return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Manage Qdrant vector database collections'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up (recreate) collections')
    cleanup_parser.add_argument(
        '--collections',
        nargs='+',
        help='Specific collections to clean (default: all)'
    )
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get collection status')
    status_parser.add_argument(
        '--format',
        choices=['text', 'json', 'github-actions'],
        default='text',
        help='Output format (default: text)'
    )
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a collection')
    create_parser.add_argument(
        '--collection',
        required=True,
        help='Collection name'
    )
    create_parser.add_argument(
        '--recreate',
        action='store_true',
        help='Recreate if already exists'
    )
    
    # Health command
    subparsers.add_parser('health', help='Check vector database health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize manager
    try:
        manager = CollectionManager()
    except Exception as e:
        logger.error(f"❌ Failed to initialize collection manager: {e}")
        logger.error("   Check QDRANT_URL and QDRANT_API_KEY environment variables")
        sys.exit(1)
    
    # Execute command
    if args.command == 'cleanup':
        result = manager.cleanup_all(collections=args.collections)
        sys.exit(0 if result['failed'] == 0 else 1)
    
    elif args.command == 'status':
        manager.get_status(format=args.format)
        sys.exit(0)
    
    elif args.command == 'create':
        success = manager.create_collection(
            args.collection,
            recreate=args.recreate
        )
        sys.exit(0 if success else 1)
    
    elif args.command == 'health':
        healthy = manager.health_check()
        sys.exit(0 if healthy else 1)


if __name__ == '__main__':
    main()

