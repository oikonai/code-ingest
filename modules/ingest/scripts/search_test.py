#!/usr/bin/env python3
"""
Vector Search Test Script

Tests vector search functionality across multiple language collections.
Used for validation after ingestion and in CI/CD pipelines.

Following CLAUDE.md: <500 lines, single responsibility (search testing only).

Usage:
    python search_test.py --query "authentication service"
    python search_test.py --query "loan approval" --limit 10 --languages rust typescript
    python search_test.py --query "test" --format json --output results.json
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.ingest import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class SearchTester:
    """
    Tests vector search across multiple language collections.
    
    Features:
    - Cross-language semantic search
    - Configurable result limits
    - Multiple output formats
    - Search quality metrics
    """
    
    def __init__(self):
        """Initialize search tester with ingestion pipeline."""
        try:
            self.pipeline = IngestionPipeline()
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise
    
    def test_search(
        self,
        query: str,
        languages: Optional[List[str]] = None,
        limit: int = 5,
        score_threshold: float = 0.3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Test search across specified languages.
        
        Args:
            query: Search query text
            languages: List of languages to search (None = all)
            limit: Maximum results per language
            score_threshold: Minimum similarity score
            
        Returns:
            Dictionary mapping language to search results
        """
        logger.info(f"🔍 Searching for: '{query}'")
        
        if languages:
            logger.info(f"   Languages: {', '.join(languages)}")
        else:
            logger.info(f"   Languages: all")
        
        try:
            results = self.pipeline.search_across_languages(
                query=query,
                languages=languages,
                limit=limit
            )
            
            # Filter by score threshold if needed
            filtered_results = {}
            for lang, lang_results in results.items():
                filtered = [
                    r for r in lang_results
                    if r.get('score', 0) >= score_threshold
                ]
                if filtered:
                    filtered_results[lang] = filtered
            
            return filtered_results
        
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            raise
    
    def format_results(
        self,
        results: Dict[str, List[Dict[str, Any]]],
        format: str = 'text'
    ) -> str:
        """
        Format search results in specified format.
        
        Args:
            results: Search results dictionary
            format: Output format ('text', 'json', 'summary')
            
        Returns:
            Formatted results string
        """
        if format == 'json':
            return json.dumps(results, indent=2, default=str)
        
        elif format == 'summary':
            return self._format_summary(results)
        
        else:  # text
            return self._format_text(results)
    
    def _format_text(self, results: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format results as detailed text."""
        lines = []
        lines.append("\n🔍 Search Results")
        lines.append("=" * 80)
        
        total_results = sum(len(r) for r in results.values())
        if total_results == 0:
            lines.append("\n❌ No results found")
            lines.append("=" * 80)
            return "\n".join(lines)
        
        for lang, lang_results in results.items():
            lines.append(f"\n📦 {lang.upper()} ({len(lang_results)} results):")
            lines.append("-" * 80)
            
            for i, result in enumerate(lang_results, 1):
                payload = result.get('payload', {})
                score = result.get('score', 0)
                
                item_name = payload.get('item_name', 'unknown')
                file_path = payload.get('file_path', 'unknown')
                repo_id = payload.get('repo_id', 'unknown')
                item_type = payload.get('item_type', 'unknown')
                
                lines.append(f"\n  {i}. {item_name} (score: {score:.3f})")
                lines.append(f"     Type: {item_type}")
                lines.append(f"     Repo: {repo_id}")
                lines.append(f"     File: {file_path}")
                
                # Show content preview if available
                content_preview = payload.get('content_preview', '')
                if content_preview:
                    preview = content_preview[:100].replace('\n', ' ')
                    lines.append(f"     Preview: {preview}...")
        
        lines.append("\n" + "=" * 80)
        lines.append(f"\n🏆 Total: {total_results} results across {len(results)} languages")
        
        return "\n".join(lines)
    
    def _format_summary(self, results: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format results as summary (for CI/CD)."""
        lines = []
        
        total_results = sum(len(r) for r in results.values())
        
        if total_results == 0:
            lines.append("❌ No results found")
            return "\n".join(lines)
        
        lines.append(f"✅ Found {total_results} results:")
        
        for lang, lang_results in results.items():
            lines.append(f"  • {lang}: {len(lang_results)} results")
            
            # Show top 3 results
            for i, result in enumerate(lang_results[:3], 1):
                payload = result.get('payload', {})
                item_name = payload.get('item_name', 'unknown')
                score = result.get('score', 0)
                lines.append(f"    {i}. {item_name} (score: {score:.3f})")
        
        return "\n".join(lines)
    
    def calculate_metrics(
        self,
        results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Calculate search quality metrics.
        
        Args:
            results: Search results dictionary
            
        Returns:
            Dictionary with quality metrics
        """
        metrics = {
            'total_results': 0,
            'languages_with_results': 0,
            'avg_score': 0.0,
            'min_score': 1.0,
            'max_score': 0.0,
            'results_by_language': {}
        }
        
        all_scores = []
        
        for lang, lang_results in results.items():
            count = len(lang_results)
            metrics['total_results'] += count
            
            if count > 0:
                metrics['languages_with_results'] += 1
                metrics['results_by_language'][lang] = count
                
                for result in lang_results:
                    score = result.get('score', 0)
                    all_scores.append(score)
                    metrics['min_score'] = min(metrics['min_score'], score)
                    metrics['max_score'] = max(metrics['max_score'], score)
        
        if all_scores:
            metrics['avg_score'] = round(sum(all_scores) / len(all_scores), 3)
        
        return metrics


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Test vector search functionality'
    )
    
    parser.add_argument(
        '--query',
        required=True,
        help='Search query text'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        choices=['rust', 'typescript', 'solidity', 'documentation', 'yaml', 'terraform'],
        help='Languages to search (default: all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Maximum results per language (default: 5)'
    )
    parser.add_argument(
        '--score-threshold',
        type=float,
        default=0.3,
        help='Minimum similarity score (default: 0.3)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'summary'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--output',
        help='Write results to file'
    )
    parser.add_argument(
        '--show-metrics',
        action='store_true',
        help='Show quality metrics'
    )
    
    args = parser.parse_args()
    
    # Initialize tester
    try:
        tester = SearchTester()
    except Exception as e:
        logger.error(f"❌ Failed to initialize search tester: {e}")
        sys.exit(1)
    
    # Execute search
    try:
        results = tester.test_search(
            query=args.query,
            languages=args.languages,
            limit=args.limit,
            score_threshold=args.score_threshold
        )
    except Exception as e:
        logger.error(f"❌ Search test failed: {e}")
        sys.exit(1)
    
    # Format results
    formatted = tester.format_results(results, format=args.format)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(formatted)
        logger.info(f"\n📄 Results written to {args.output}")
    else:
        print(formatted)
    
    # Show metrics if requested
    if args.show_metrics:
        metrics = tester.calculate_metrics(results)
        print("\n📊 Search Quality Metrics:")
        print(json.dumps(metrics, indent=2))
    
    # Exit with success if we found results
    total_results = sum(len(r) for r in results.values())
    sys.exit(0 if total_results > 0 else 1)


if __name__ == '__main__':
    main()

