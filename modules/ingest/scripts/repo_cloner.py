#!/usr/bin/env python3
"""
Repository Cloner Script

Automatically clones all configured Arda repositories using a single PAT token.
Handles HTTPS and SSH URLs, skips already-cloned repos, and tracks commit SHAs.

Following CLAUDE.md: <500 lines, single responsibility (repository cloning only).

Usage:
    python repo_cloner.py --pat-token <token>
    python repo_cloner.py --force-reclone
    python repo_cloner.py --repos my-backend my-frontend
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.ingest.core.config import REPOSITORIES, RepoConfig, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, REPOS_BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class RepositoryCloner:
    """
    Clones and manages configured repositories.
    
    Features:
    - Single PAT token authentication
    - HTTPS and SSH URL support
    - Skip already-cloned repos (unless force-reclone)
    - Commit SHA tracking
    - Organized directory structure
    """
    
    def __init__(self, base_dir: str = "./repos", pat_token: Optional[str] = None):
        """
        Initialize repository cloner.
        
        Args:
            base_dir: Base directory for cloning repos
            pat_token: GitHub Personal Access Token (optional, uses env var if not provided)
        """
        self.base_dir = Path(base_dir)
        self.pat_token = pat_token or os.getenv('GITHUB_TOKEN') or os.getenv('I2P_REPO_PAT')
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def clone_all(
        self,
        force_reclone: bool = False,
        repo_filter: Optional[List[str]] = None,
        min_priority: Optional[str] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Clone all configured repositories.
        
        Args:
            force_reclone: If True, delete and re-clone existing repos
            repo_filter: If provided, only clone these specific repos
            min_priority: Minimum priority threshold (high|medium|low|ALL)
                - 'high': Only high priority repos
                - 'medium': Medium + high priority repos
                - 'low': All repos (low + medium + high)
                - 'ALL': All repos (same as 'low')
            
        Returns:
            Dictionary mapping repo_id to clone status and metadata
        """
        results = {}
        
        # Filter repositories
        repos_to_clone = self._filter_repos(repo_filter, min_priority)
        
        logger.info(f"🔄 Cloning {len(repos_to_clone)} repositories...")
        
        for repo_id, repo_config in repos_to_clone.items():
            try:
                result = self.clone_repo(repo_id, repo_config, force_reclone)
                results[repo_id] = result
                
                if result['status'] == 'success':
                    logger.info(f"✅ {repo_id}: {result['message']}")
                elif result['status'] == 'skipped':
                    logger.info(f"⏭️  {repo_id}: {result['message']}")
                else:
                    logger.error(f"❌ {repo_id}: {result['message']}")
            except Exception as e:
                logger.error(f"❌ {repo_id}: Unexpected error: {e}")
                results[repo_id] = {
                    'status': 'error',
                    'message': str(e)
                }
        
        # Summary
        success_count = sum(1 for r in results.values() if r['status'] == 'success')
        skip_count = sum(1 for r in results.values() if r['status'] == 'skipped')
        error_count = sum(1 for r in results.values() if r['status'] == 'error')
        
        logger.info(f"\n📊 Summary:")
        logger.info(f"  ✅ Cloned: {success_count}")
        logger.info(f"  ⏭️  Skipped: {skip_count}")
        logger.info(f"  ❌ Errors: {error_count}")
        
        return results
    
    def clone_repo(
        self,
        repo_id: str,
        repo_config: RepoConfig,
        force_reclone: bool = False
    ) -> Dict[str, str]:
        """
        Clone a single repository.
        
        Args:
            repo_id: Repository identifier
            repo_config: Repository configuration
            force_reclone: If True, delete and re-clone if exists
            
        Returns:
            Dictionary with status, message, commit_sha, etc.
        """
        repo_path = self.base_dir / repo_id
        
        # Check if already cloned
        if repo_path.exists() and not force_reclone:
            # Get current commit SHA
            commit_sha = self._get_commit_sha(repo_path)
            return {
                'status': 'skipped',
                'message': f'Already cloned at {repo_path}',
                'commit_sha': commit_sha,
                'path': str(repo_path)
            }
        
        # Remove if force re-clone
        if repo_path.exists() and force_reclone:
            logger.info(f"  🗑️  Removing existing {repo_id}...")
            import shutil
            shutil.rmtree(repo_path)
        
        # Prepare clone URL
        clone_url = self._prepare_clone_url(repo_config.github_url)
        
        # Clone repository
        try:
            logger.info(f"  📥 Cloning {repo_id}...")
            cmd = ['git', 'clone', clone_url, str(repo_path)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                return {
                    'status': 'error',
                    'message': f'Clone failed: {result.stderr}',
                    'path': str(repo_path)
                }
            
            # Get commit SHA
            commit_sha = self._get_commit_sha(repo_path)
            commit_message = self._get_commit_message(repo_path)
            
            return {
                'status': 'success',
                'message': f'Cloned successfully to {repo_path}',
                'commit_sha': commit_sha,
                'commit_message': commit_message,
                'path': str(repo_path)
            }
        
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'message': 'Clone operation timed out',
                'path': str(repo_path)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Clone failed: {e}',
                'path': str(repo_path)
            }
    
    def _prepare_clone_url(self, github_url: str) -> str:
        """
        Prepare clone URL with authentication if needed.
        
        Args:
            github_url: Original GitHub URL
            
        Returns:
            Clone URL with authentication token if HTTPS
        """
        if github_url.startswith('https://') and self.pat_token:
            # Insert PAT token into HTTPS URL
            return github_url.replace('https://', f'https://{self.pat_token}@')
        
        return github_url
    
    def _get_commit_sha(self, repo_path: Path) -> str:
        """Get current commit SHA of repository."""
        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            return 'unknown'
    
    def _get_commit_message(self, repo_path: Path) -> str:
        """Get current commit message of repository."""
        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'log', '-1', '--pretty=format:%s'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else ''
        except Exception:
            return ''
    
    def _filter_repos(
        self,
        repo_filter: Optional[List[str]] = None,
        min_priority: Optional[str] = None
    ) -> Dict[str, RepoConfig]:
        """
        Filter repositories based on criteria.
        
        Args:
            repo_filter: Specific repo IDs to include
            min_priority: Minimum priority threshold (high|medium|low|ALL)
            
        Returns:
            Filtered dictionary of repos
        """
        repos = REPOSITORIES
        
        if repo_filter:
            repos = {k: v for k, v in repos.items() if k in repo_filter}
        
        if min_priority:
            # Normalize to lowercase
            min_priority = min_priority.lower()
            
            # 'ALL' means clone everything
            if min_priority == 'all':
                pass  # Don't filter
            
            # 'high' means only high priority
            elif min_priority == PRIORITY_HIGH:
                repos = {k: v for k, v in repos.items() if v.priority == PRIORITY_HIGH}
            
            # 'medium' means medium + high
            elif min_priority == PRIORITY_MEDIUM:
                repos = {k: v for k, v in repos.items() 
                        if v.priority in [PRIORITY_MEDIUM, PRIORITY_HIGH]}
            
            # 'low' means all priorities (low + medium + high)
            elif min_priority == PRIORITY_LOW:
                pass  # Don't filter, clone all
            
            else:
                logger.warning(f"⚠️  Unknown priority: {min_priority}, cloning all repos")
        
        return repos


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Clone configured repositories for ingestion'
    )
    parser.add_argument(
        '--pat-token',
        help='GitHub Personal Access Token (or use GITHUB_TOKEN env var)'
    )
    parser.add_argument(
        '--base-dir',
        default=REPOS_BASE_DIR,
        help=f'Base directory for cloning repositories (default: {REPOS_BASE_DIR} from config)'
    )
    parser.add_argument(
        '--force-reclone',
        action='store_true',
        help='Force re-clone even if repository already exists'
    )
    parser.add_argument(
        '--repos',
        nargs='+',
        help='Specific repositories to clone (space-separated)'
    )
    parser.add_argument(
        '--min-priority',
        choices=['high', 'medium', 'low', 'ALL'],
        help='Minimum priority threshold: high (only high), medium (medium+high), low/ALL (all repos)'
    )
    parser.add_argument(
        '--output-json',
        help='Write clone results to JSON file'
    )
    
    args = parser.parse_args()
    
    # Initialize cloner
    cloner = RepositoryCloner(
        base_dir=args.base_dir,
        pat_token=args.pat_token
    )
    
    # Clone repositories
    results = cloner.clone_all(
        force_reclone=args.force_reclone,
        repo_filter=args.repos,
        min_priority=args.min_priority
    )
    
    # Output JSON if requested
    if args.output_json:
        with open(args.output_json, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"\n📄 Results written to {args.output_json}")
    
    # Exit with error code if any clones failed
    error_count = sum(1 for r in results.values() if r['status'] == 'error')
    sys.exit(1 if error_count > 0 else 0)


if __name__ == '__main__':
    main()

