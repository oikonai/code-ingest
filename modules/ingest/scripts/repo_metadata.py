#!/usr/bin/env python3
"""
Repository Metadata Capture Script

Captures commit SHAs, messages, and other metadata from cloned repositories.
Outputs in various formats for GitHub Actions and reporting.

Following CLAUDE.md: <500 lines, single responsibility (metadata capture only).

Usage:
    python repo_metadata.py capture --output json
    python repo_metadata.py capture --format github-actions
    python repo_metadata.py capture --repos arda-credit arda-platform
"""

import os
import sys
import argparse
import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.ingest.core.config import REPOSITORIES, REPOS_BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class RepoMetadataCapture:
    """
    Captures metadata from cloned repositories.
    
    Captures:
    - Commit SHA (full and short)
    - Commit message
    - Commit author
    - Commit date
    - Branch name
    - Remote URL
    """
    
    def __init__(self, base_dir: str = "./repos"):
        """
        Initialize metadata capture.
        
        Args:
            base_dir: Base directory containing cloned repos
        """
        self.base_dir = Path(base_dir)
    
    def capture_all(
        self,
        repo_filter: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Capture metadata from all repositories.
        
        Args:
            repo_filter: If provided, only capture from these repos. If empty list, captures nothing.
            
        Returns:
            Dictionary mapping repo_id to metadata
        """
        metadata = {}
        
        # Filter repos
        repos = REPOSITORIES
        if repo_filter is not None:  # Changed: explicitly check for None instead of truthiness
            repos = {k: v for k, v in repos.items() if k in repo_filter}
        
        logger.info(f"📝 Capturing metadata from {len(repos)} repositories...")
        
        for repo_id in repos.keys():
            repo_path = self.base_dir / repo_id
            
            if not repo_path.exists():
                logger.warning(f"⚠️  {repo_id}: Repository not found at {repo_path}")
                metadata[repo_id] = {'error': 'not_found'}
                continue
            
            try:
                repo_metadata = self.capture_repo_metadata(repo_path)
                metadata[repo_id] = repo_metadata
                logger.info(f"✅ {repo_id}: {repo_metadata['commit_sha_short']} - {repo_metadata['commit_message'][:50]}")
            except Exception as e:
                logger.error(f"❌ {repo_id}: Failed to capture metadata: {e}")
                metadata[repo_id] = {'error': str(e)}
        
        return metadata
    
    def capture_repo_metadata(self, repo_path: Path) -> Dict[str, Any]:
        """
        Capture metadata from a single repository.
        
        Args:
            repo_path: Path to git repository
            
        Returns:
            Dictionary with repository metadata
        """
        metadata = {}
        
        # Commit SHA (full)
        metadata['commit_sha'] = self._git_cmd(
            repo_path, ['rev-parse', 'HEAD']
        )
        
        # Commit SHA (short)
        metadata['commit_sha_short'] = self._git_cmd(
            repo_path, ['rev-parse', '--short', 'HEAD']
        )
        
        # Commit message
        metadata['commit_message'] = self._git_cmd(
            repo_path, ['log', '-1', '--pretty=format:%s']
        )
        
        # Commit author
        metadata['commit_author'] = self._git_cmd(
            repo_path, ['log', '-1', '--pretty=format:%an']
        )
        
        # Commit date
        metadata['commit_date'] = self._git_cmd(
            repo_path, ['log', '-1', '--pretty=format:%ci']
        )
        
        # Branch name
        metadata['branch'] = self._git_cmd(
            repo_path, ['rev-parse', '--abbrev-ref', 'HEAD']
        )
        
        # Remote URL
        try:
            metadata['remote_url'] = self._git_cmd(
                repo_path, ['config', '--get', 'remote.origin.url']
            )
        except Exception:
            metadata['remote_url'] = 'unknown'
        
        # Tag (if any)
        try:
            metadata['tag'] = self._git_cmd(
                repo_path, ['describe', '--tags', '--exact-match']
            )
        except Exception:
            metadata['tag'] = None
        
        return metadata
    
    def _git_cmd(
        self,
        repo_path: Path,
        args: List[str],
        timeout: int = 10
    ) -> str:
        """
        Execute git command and return output.
        
        Args:
            repo_path: Path to repository
            args: Git command arguments
            timeout: Command timeout in seconds
            
        Returns:
            Command output (stripped)
        """
        cmd = ['git', '-C', str(repo_path)] + args
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: {result.stderr}")
        
        return result.stdout.strip()
    
    def format_output(
        self,
        metadata: Dict[str, Dict[str, Any]],
        format: str = 'text'
    ):
        """
        Format and print metadata in specified format.
        
        Args:
            metadata: Repository metadata dictionary
            format: Output format ('text', 'json', 'github-actions')
        """
        if format == 'json':
            print(json.dumps(metadata, indent=2))
        
        elif format == 'github-actions':
            self._print_github_actions_format(metadata)
        
        elif format == 'text':
            self._print_text_format(metadata)
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _print_text_format(self, metadata: Dict[str, Dict[str, Any]]):
        """Print metadata in human-readable format."""
        logger.info("\n📋 Repository Metadata:")
        logger.info("=" * 80)
        
        for repo_id, repo_data in metadata.items():
            if 'error' in repo_data:
                logger.error(f"  ❌ {repo_id}: {repo_data['error']}")
            else:
                logger.info(f"\n  📦 {repo_id}")
                logger.info(f"     Commit: {repo_data['commit_sha_short']} ({repo_data['commit_sha']})")
                logger.info(f"     Message: {repo_data['commit_message']}")
                logger.info(f"     Author: {repo_data['commit_author']}")
                logger.info(f"     Date: {repo_data['commit_date']}")
                logger.info(f"     Branch: {repo_data['branch']}")
                if repo_data.get('tag'):
                    logger.info(f"     Tag: {repo_data['tag']}")
        
        logger.info("\n" + "=" * 80)
    
    def _print_github_actions_format(self, metadata: Dict[str, Dict[str, Any]]):
        """Print metadata in GitHub Actions format (for step outputs)."""
        # Output each repo's metadata as step outputs
        for repo_id, repo_data in metadata.items():
            if 'error' not in repo_data:
                # Convert repo_id to valid env var name (replace - with _)
                var_prefix = repo_id.replace('-', '_')
                
                print(f"{var_prefix}_sha={repo_data['commit_sha']}")
                print(f"{var_prefix}_short={repo_data['commit_sha_short']}")
                print(f"{var_prefix}_msg={repo_data['commit_message']}")
                print(f"{var_prefix}_author={repo_data['commit_author']}")
                print(f"{var_prefix}_date={repo_data['commit_date']}")
                print(f"{var_prefix}_branch={repo_data['branch']}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Capture metadata from cloned repositories'
    )
    
    parser.add_argument(
        'command',
        choices=['capture'],
        help='Command to run (currently only "capture")'
    )
    parser.add_argument(
        '--base-dir',
        default=REPOS_BASE_DIR,
        help=f'Base directory containing cloned repos (default: {REPOS_BASE_DIR} from config)'
    )
    parser.add_argument(
        '--repos',
        nargs='+',
        help='Specific repositories to capture metadata from'
    )
    parser.add_argument(
        '--repos-json',
        help='JSON file from repo_cloner.py with list of cloned repos (filters to only cloned repos)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'github-actions'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--output',
        help='Write output to file (JSON format)'
    )
    
    args = parser.parse_args()
    
    # Determine which repos to capture from
    repo_filter = args.repos
    
    # If repos-json provided, load the list of actually cloned repos
    if args.repos_json:
        try:
            with open(args.repos_json, 'r') as f:
                repos_data = json.load(f)
                # Extract successfully cloned repo names
                # Status values from repo_cloner: 'success' (newly cloned) or 'skipped' (already exists)
                cloned_repos = [
                    repo_id for repo_id, status in repos_data.items()
                    if status.get('status') in ['success', 'skipped']
                ]
                repo_filter = cloned_repos
                
                # Debug logging
                total_in_json = len(repos_data)
                logger.info(f"📋 Found {total_in_json} repos in {args.repos_json}")
                logger.info(f"📋 Filtered to {len(cloned_repos)} successfully cloned repos")
                
                if len(cloned_repos) == 0 and total_in_json > 0:
                    # Show what statuses were found
                    statuses = [status.get('status') for status in repos_data.values()]
                    logger.warning(f"⚠️ No repos with status 'success' or 'skipped'. Found statuses: {set(statuses)}")
        except Exception as e:
            logger.warning(f"⚠️ Could not load {args.repos_json}: {e}, checking all repos")
    
    # Initialize capturer
    capturer = RepoMetadataCapture(base_dir=args.base_dir)
    
    # Capture metadata
    metadata = capturer.capture_all(repo_filter=repo_filter)
    
    # Format output
    capturer.format_output(metadata, format=args.format)
    
    # Write to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"\n📄 Metadata written to {args.output}")
    
    # Exit with error if any repos failed
    error_count = sum(1 for data in metadata.values() if 'error' in data)
    sys.exit(1 if error_count > 0 else 0)


if __name__ == '__main__':
    main()

