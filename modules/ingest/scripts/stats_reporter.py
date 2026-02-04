#!/usr/bin/env python3
"""
Statistics Reporter Script

Generates comprehensive statistics reports for vector ingestion pipeline.
Supports multiple output formats including GitHub Actions markdown summaries.

Following CLAUDE.md: <500 lines, single responsibility (statistics reporting only).

Usage:
    python stats_reporter.py --format github-actions --start-time 1234567890 --end-time 1234567900
    python stats_reporter.py --format json --output stats.json
    python stats_reporter.py --format markdown --output report.md
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.ingest.core.vector_backend import create_vector_backend
from modules.ingest.core.config import IngestionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class StatsReporter:
    """
    Generates comprehensive statistics reports for ingestion pipeline.
    
    Reports:
    - Vector counts by collection
    - Indexing progress
    - Processing time and performance metrics
    - GPU cost calculations
    - Quality metrics
    """
    
    def __init__(self):
        """Initialize stats reporter."""
        self.client = create_vector_backend()
        self.config = IngestionConfig()
    
    def collect_stats(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Collect comprehensive statistics.
        
        Args:
            start_time: Processing start time (Unix timestamp)
            end_time: Processing end time (Unix timestamp)
            
        Returns:
            Dictionary with all statistics
        """
        stats = {
            'collections': {},
            'totals': {
                'vectors': 0,
                'indexed': 0
            },
            'performance': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Collect collection statistics
        collections = list(set(self.config.collections.values()))
        
        for collection_name in collections:
            try:
                info = self.client.get_collection_info(collection_name)
                
                if not info:
                    continue
                
                lang = collection_name.split('_')[-1]
                
                # Extract stats from SurrealDB response format
                vectors_count = info.get('vectors_count', info.get('points_count', 0))
                indexed_count = info.get('indexed_vectors_count', vectors_count)
                status = info.get('status', 'unknown')
                
                collection_stats = {
                    'name': collection_name,
                    'vectors': vectors_count,
                    'indexed': indexed_count,
                    'status': status.name if hasattr(status, 'name') else str(status)
                }
                
                stats['collections'][lang] = collection_stats
                stats['totals']['vectors'] += collection_stats['vectors']
                stats['totals']['indexed'] += collection_stats['indexed']
            
            except Exception as e:
                logger.warning(f"⚠️  Could not get stats for {collection_name}: {e}")
                stats['collections'][collection_name] = {'error': str(e)}
        
        # Calculate performance metrics if timing provided
        if start_time and end_time:
            duration_sec = end_time - start_time
            stats['performance'] = self._calculate_performance(
                duration_sec,
                stats['totals']['vectors']
            )
        
        return stats
    
    def _calculate_performance(
        self,
        duration_sec: int,
        total_vectors: int
    ) -> Dict[str, Any]:
        """
        Calculate performance metrics.
        
        Args:
            duration_sec: Processing duration in seconds
            total_vectors: Total number of vectors processed
            
        Returns:
            Performance metrics dictionary
        """
        minutes = duration_sec // 60
        seconds = duration_sec % 60
        
        # GPU cost (A100-40GB: $0.000583/sec)
        gpu_cost_rate = 0.000583
        gpu_cost = duration_sec * gpu_cost_rate
        
        # Vectors per minute/second
        vectors_per_minute = int(total_vectors / (duration_sec / 60)) if duration_sec > 0 else 0
        vectors_per_second = round(total_vectors / duration_sec, 2) if duration_sec > 0 else 0
        
        # Cost per vector
        cost_per_vector = round(gpu_cost / total_vectors, 6) if total_vectors > 0 else 0
        
        return {
            'duration_sec': duration_sec,
            'duration_formatted': f"{minutes}m {seconds}s",
            'gpu_cost_usd': round(gpu_cost, 4),
            'vectors_per_minute': vectors_per_minute,
            'vectors_per_second': vectors_per_second,
            'cost_per_vector_usd': cost_per_vector
        }
    
    def generate_report(
        self,
        stats: Dict[str, Any],
        format: str = 'text',
        repo_metadata: Optional[Dict[str, Any]] = None,
        job_status: str = 'success'
    ) -> str:
        """
        Generate report in specified format.
        
        Args:
            stats: Statistics dictionary
            format: Output format ('text', 'json', 'markdown', 'github-actions')
            repo_metadata: Optional repository metadata
            job_status: Job status ('success', 'failure', 'cancelled')
            
        Returns:
            Formatted report string
        """
        if format == 'json':
            return json.dumps(stats, indent=2)
        
        elif format == 'markdown':
            return self._generate_markdown(stats, repo_metadata, job_status)
        
        elif format == 'github-actions':
            return self._generate_github_actions(stats, repo_metadata, job_status)
        
        else:  # text
            return self._generate_text(stats)
    
    def _generate_text(self, stats: Dict[str, Any]) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("\n📊 Vector Ingestion Statistics")
        lines.append("=" * 70)
        lines.append("")
        
        # Collection stats
        lines.append("📦 Collections:")
        for lang, data in stats['collections'].items():
            if 'error' not in data:
                lines.append(
                    f"  {lang.upper()}: {data['vectors']:,} vectors "
                    f"({data['indexed']:,} indexed, {data['status']})"
                )
        
        # Totals
        lines.append("")
        lines.append(f"🏆 Total: {stats['totals']['vectors']:,} vectors "
                    f"({stats['totals']['indexed']:,} indexed)")
        
        # Performance
        if stats.get('performance'):
            perf = stats['performance']
            lines.append("")
            lines.append("⚡ Performance:")
            lines.append(f"  Duration: {perf['duration_formatted']}")
            lines.append(f"  Speed: {perf['vectors_per_second']} vectors/sec")
            lines.append(f"  GPU Cost: ${perf['gpu_cost_usd']}")
            lines.append(f"  Cost per Vector: ${perf['cost_per_vector_usd']}")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _generate_markdown(
        self,
        stats: Dict[str, Any],
        repo_metadata: Optional[Dict[str, Any]],
        job_status: str
    ) -> str:
        """Generate Markdown report."""
        lines = []
        lines.append("# Vector Ingestion Report")
        lines.append("")
        
        # Status
        status_emoji = "✅" if job_status == "success" else "❌"
        lines.append(f"**Status:** {status_emoji} {job_status}")
        lines.append(f"**Timestamp:** {stats['timestamp']}")
        lines.append("")
        
        # Collections
        lines.append("## Collections")
        lines.append("")
        lines.append("| Language | Vectors | Indexed | Status |")
        lines.append("|----------|---------|---------|--------|")
        
        for lang, data in stats['collections'].items():
            if 'error' not in data:
                lines.append(
                    f"| {lang.upper()} | {data['vectors']:,} | "
                    f"{data['indexed']:,} | {data['status']} |"
                )
        
        lines.append("")
        lines.append(f"**Total:** {stats['totals']['vectors']:,} vectors "
                    f"({stats['totals']['indexed']:,} indexed)")
        
        # Performance
        if stats.get('performance'):
            perf = stats['performance']
            lines.append("")
            lines.append("## Performance Metrics")
            lines.append("")
            lines.append(f"- **Duration:** {perf['duration_formatted']}")
            lines.append(f"- **Speed:** {perf['vectors_per_second']} vectors/sec")
            lines.append(f"- **GPU Cost:** ${perf['gpu_cost_usd']}")
            lines.append(f"- **Cost per Vector:** ${perf['cost_per_vector_usd']}")
        
        # Repository metadata
        if repo_metadata:
            lines.append("")
            lines.append("## Repository Commits")
            lines.append("")
            lines.append("| Repository | Commit | Message |")
            lines.append("|------------|--------|---------|")
            
            for repo_id, data in repo_metadata.items():
                if 'error' not in data:
                    lines.append(
                        f"| {repo_id} | `{data.get('commit_sha_short', 'N/A')}` | "
                        f"{data.get('commit_message', 'N/A')[:50]} |"
                    )
        
        return "\n".join(lines)
    
    def _generate_github_actions(
        self,
        stats: Dict[str, Any],
        repo_metadata: Optional[Dict[str, Any]],
        job_status: str
    ) -> str:
        """Generate GitHub Actions summary markdown."""
        lines = []
        lines.append("# 📊 Vector Ingestion Pipeline Report")
        lines.append("")
        
        # Status emoji
        if job_status == "success":
            status_emoji = "✅"
        elif job_status == "failure":
            status_emoji = "❌"
        else:
            status_emoji = "⚠️"
        
        # Performance summary
        if stats.get('performance'):
            perf = stats['performance']
            
            lines.append("## ⚡ Performance Summary")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| **Status** | {status_emoji} {job_status} |")
            lines.append(f"| **Processing Time** | {perf['duration_formatted']} |")
            lines.append(f"| **Total Vectors** | {stats['totals']['vectors']:,} |")
            lines.append(f"| **Vectors/Second** | {perf['vectors_per_second']} |")
            lines.append(f"| **GPU Cost** | ${perf['gpu_cost_usd']} |")
            lines.append("")
        
        # Collections
        lines.append("## 📦 Vector Database Statistics")
        lines.append("")
        lines.append("| Language | Vectors Created | Indexed | Status |")
        lines.append("|----------|----------------|---------|--------|")
        
        for lang, data in stats['collections'].items():
            if 'error' not in data:
                status = "✅" if data['status'] == 'green' else "⚠️"
                lines.append(
                    f"| {lang.upper()} | {data['vectors']:,} | "
                    f"{data['indexed']:,} | {status} |"
                )
        
        lines.append("")
        
        # Index coverage
        total_vectors = stats['totals']['vectors']
        total_indexed = stats['totals']['indexed']
        if total_vectors > 0:
            coverage = (total_indexed / total_vectors) * 100
            lines.append(f"**Indexing Progress:** {total_indexed:,} / {total_vectors:,} "
                        f"vectors indexed ({coverage:.1f}%)")
        
        # Repository commits
        if repo_metadata:
            lines.append("")
            lines.append("## 📝 Repository Commits Processed")
            lines.append("")
            lines.append("| Repository | Commit SHA | Message |")
            lines.append("|------------|------------|---------|")
            
            for repo_id, data in repo_metadata.items():
                if 'error' not in data:
                    sha = data.get('commit_sha', 'N/A')[:7]
                    msg = data.get('commit_message', 'N/A')[:60]
                    lines.append(f"| **{repo_id}** | `{sha}` | {msg} |")
        
        lines.append("")
        lines.append("---")
        lines.append(f"*Generated at {stats['timestamp']}*")
        
        return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate statistics reports for vector ingestion'
    )
    
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'markdown', 'github-actions'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--output',
        help='Write report to file'
    )
    parser.add_argument(
        '--start-time',
        type=int,
        help='Processing start time (Unix timestamp)'
    )
    parser.add_argument(
        '--end-time',
        type=int,
        help='Processing end time (Unix timestamp)'
    )
    parser.add_argument(
        '--repo-metadata',
        help='Path to repository metadata JSON file'
    )
    parser.add_argument(
        '--job-status',
        choices=['success', 'failure', 'cancelled'],
        default='success',
        help='Job status (default: success)'
    )
    
    args = parser.parse_args()
    
    # Initialize reporter
    try:
        reporter = StatsReporter()
    except Exception as e:
        logger.error(f"❌ Failed to initialize reporter: {e}")
        sys.exit(1)
    
    # Collect statistics
    stats = reporter.collect_stats(
        start_time=args.start_time,
        end_time=args.end_time
    )
    
    # Load repo metadata if provided
    repo_metadata = None
    if args.repo_metadata and Path(args.repo_metadata).exists():
        with open(args.repo_metadata, 'r') as f:
            repo_metadata = json.load(f)
    
    # Generate report
    report = reporter.generate_report(
        stats,
        format=args.format,
        repo_metadata=repo_metadata,
        job_status=args.job_status
    )
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        logger.info(f"📄 Report written to {args.output}")
    else:
        print(report)
    
    sys.exit(0)


if __name__ == '__main__':
    main()

