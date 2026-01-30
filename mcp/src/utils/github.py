"""GitHub API integration helpers for fetching repository structures."""

import os
import logging
import time
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# These will be imported from server.py's global state
_repo_cache: Dict[str, Any] = {}
_repo_cache_timestamp: Optional[float] = None
_repo_cache_ttl: int = 3600  # 1 hour cache TTL


def set_repo_cache_globals(cache: Dict, timestamp: Optional[float], ttl: int):
    """
    Set global state references for repo cache.
    
    Args:
        cache: Reference to the server's _repo_cache dict
        timestamp: Reference to the server's _repo_cache_timestamp
        ttl: Cache TTL in seconds
    """
    global _repo_cache, _repo_cache_timestamp, _repo_cache_ttl
    _repo_cache = cache
    _repo_cache_timestamp = timestamp
    _repo_cache_ttl = ttl


async def fetch_github_repo_structure(repo_url: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch repository structure from GitHub API.

    Args:
        repo_url: Git repository URL (e.g., git@github.com:org/repo.git)
        github_token: Optional GitHub token for authentication

    Returns:
        Dictionary with repository structure and metadata
    """
    # Parse repo URL to extract owner and repo name
    # git@github.com:ardaglobal/arda-credit.git -> ardaglobal/arda-credit
    import re
    match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', repo_url)
    if not match:
        logger.warning(f"Could not parse GitHub URL: {repo_url}")
        return {}

    owner, repo = match.groups()
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch repository info
            repo_response = await client.get(api_base, headers=headers)
            repo_response.raise_for_status()
            repo_data = repo_response.json()

            # Fetch directory tree
            tree_url = f"{api_base}/git/trees/{repo_data['default_branch']}?recursive=1"
            tree_response = await client.get(tree_url, headers=headers)
            tree_response.raise_for_status()
            tree_data = tree_response.json()

            # Fetch README
            readme_url = f"{api_base}/readme"
            readme_content = ""
            try:
                readme_response = await client.get(readme_url, headers=headers)
                if readme_response.status_code == 200:
                    readme_data = readme_response.json()
                    import base64
                    readme_content = base64.b64decode(readme_data.get('content', '')).decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch README for {repo}: {e}")

            return {
                'name': repo,
                'owner': owner,
                'description': repo_data.get('description', ''),
                'language': repo_data.get('language', ''),
                'updated_at': repo_data.get('updated_at', ''),
                'tree': tree_data.get('tree', []),
                'readme': readme_content
            }

    except Exception as e:
        logger.error(f"Failed to fetch GitHub repo structure for {repo_url}: {e}")
        return {}


async def get_cached_repo_structures() -> Dict[str, Any]:
    """
    Get cached repository structures or fetch if cache is stale.

    Returns:
        Dictionary with structure for both repositories
    """
    global _repo_cache, _repo_cache_timestamp

    current_time = time.time()

    # Check if cache is valid
    if _repo_cache and _repo_cache_timestamp:
        if current_time - _repo_cache_timestamp < _repo_cache_ttl:
            logger.info("📦 Using cached repository structures")
            return _repo_cache

    logger.info("🔄 Fetching latest repository structures from GitHub...")

    # Get configuration
    arda_credit_url = os.getenv('ARDA_CREDIT_REPO_URL')
    arda_platform_url = os.getenv('ARDA_CREDIT_PLATFORM')
    github_token = os.getenv('GHCR_TOKEN')

    if not arda_credit_url or not arda_platform_url:
        logger.warning("⚠️  Repository URLs not configured in environment")
        return {}

    # Fetch both repositories
    arda_credit = await fetch_github_repo_structure(arda_credit_url, github_token)
    arda_platform = await fetch_github_repo_structure(arda_platform_url, github_token)

    _repo_cache = {
        'arda_credit': arda_credit,
        'arda_platform': arda_platform
    }
    _repo_cache_timestamp = current_time

    logger.info(f"✅ Repository structures cached (TTL: {_repo_cache_ttl}s)")

    return _repo_cache


def analyze_directory_structure(tree: List[Dict]) -> Dict[str, List[str]]:
    """
    Analyze repository tree to extract key directories and files.

    Args:
        tree: GitHub tree data

    Returns:
        Dictionary mapping directory categories to file paths
    """
    structure = {
        'api': [],
        'database': [],
        'frontend': [],
        'contracts': [],
        'components': [],
        'utils': [],
        'tests': [],
        'docs': []
    }

    for item in tree:
        path = item.get('path', '')

        # Categorize based on path patterns
        if 'api/' in path or path.startswith('api/'):
            structure['api'].append(path)
        elif 'db/' in path or 'database/' in path:
            structure['database'].append(path)
        elif 'src/components/' in path:
            structure['components'].append(path)
        elif 'src/pages/' in path or 'pages/' in path:
            structure['frontend'].append(path)
        elif 'contracts/' in path or path.endswith('.sol'):
            structure['contracts'].append(path)
        elif 'utils/' in path or 'lib/' in path:
            structure['utils'].append(path)
        elif 'test/' in path or path.endswith('.test.ts') or path.endswith('_test.rs'):
            structure['tests'].append(path)
        elif path.endswith('.md') or 'docs/' in path:
            structure['docs'].append(path)

    # Keep only top-level directories (limit to 10 per category)
    for category in structure:
        structure[category] = sorted(set(structure[category]))[:10]

    return structure


async def fetch_pr_metrics(
    repo_url: str,
    since_date: str,
    github_token: str
) -> List[Dict]:
    """
    Fetch PR metrics from GitHub API for analysis.

    Args:
        repo_url: Repository URL (e.g., "git@github.com:org/repo.git")
        since_date: ISO format date to fetch PRs from (e.g., "2024-01-01T00:00:00Z")
        github_token: GitHub API token for authentication

    Returns:
        List of PR dictionaries with metrics

    Raises:
        Exception: If GitHub API request fails
    """
    # Parse repo URL
    import re
    match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', repo_url)
    if not match:
        logger.warning(f"Could not parse GitHub URL: {repo_url}")
        return []

    owner, repo = match.groups()
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {github_token}"
    }

    pr_metrics = []

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Fetch merged PRs since date
            page = 1
            while page <= 5:  # Limit to 5 pages (150 PRs max)
                params = {
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 30,
                    "page": page
                }

                response = await client.get(f"{api_base}/pulls", headers=headers, params=params)
                response.raise_for_status()
                prs = response.json()

                if not prs:
                    break  # No more PRs

                for pr in prs:
                    # Only include merged PRs
                    if not pr.get("merged_at"):
                        continue

                    # Skip PRs older than since_date
                    from dateutil import parser as date_parser
                    pr_updated = date_parser.parse(pr["updated_at"])
                    since_dt = date_parser.parse(since_date)
                    if pr_updated < since_dt:
                        continue

                    # Calculate time to merge (in hours)
                    created_at = date_parser.parse(pr["created_at"])
                    merged_at = date_parser.parse(pr["merged_at"])
                    time_to_merge = (merged_at - created_at).total_seconds() / 3600

                    # Fetch review count
                    reviews_response = await client.get(f"{api_base}/pulls/{pr['number']}/reviews", headers=headers)
                    review_count = len(reviews_response.json()) if reviews_response.status_code == 200 else 0

                    # Fetch files changed
                    files_response = await client.get(f"{api_base}/pulls/{pr['number']}/files", headers=headers)
                    files_changed = []
                    if files_response.status_code == 200:
                        files_changed = [f["filename"] for f in files_response.json()]

                    pr_metrics.append({
                        "number": pr["number"],
                        "title": pr["title"],
                        "body": pr.get("body", ""),
                        "author": pr["user"]["login"],
                        "created_at": pr["created_at"],
                        "merged_at": pr["merged_at"],
                        "time_to_merge": round(time_to_merge, 2),
                        "review_count": review_count,
                        "changes": pr["additions"] + pr["deletions"],
                        "files_changed": files_changed
                    })

                page += 1

                # Rate limiting: respect X-RateLimit headers
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) < 10:
                    logger.warning("⚠️  Approaching GitHub API rate limit, stopping PR fetch")
                    break

        logger.info(f"✅ Fetched {len(pr_metrics)} PR metrics from {owner}/{repo}")
        return pr_metrics

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.error(f"Repository not found or not accessible: {owner}/{repo}")
            return []
        elif e.response.status_code == 403:
            logger.error(f"GitHub API rate limit exceeded or insufficient permissions")
            return []
        else:
            logger.error(f"GitHub API error: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to fetch PR metrics: {e}")
        raise


def detect_ai_generated_pr(pr: Dict, ai_markers: List[str]) -> bool:
    """
    Detect if a PR was AI-generated based on markers.

    Args:
        pr: PR dictionary with title and body
        ai_markers: List of regex patterns to detect AI tools

    Returns:
        True if PR appears to be AI-generated, False otherwise
    """
    # Combine title and body for searching
    text = f"{pr.get('title', '')} {pr.get('body', '')}".lower()

    # Check for AI markers
    for marker in ai_markers:
        if re.search(marker, text, re.IGNORECASE):
            return True

    return False


def find_follow_up_fixes(
    prs: List[Dict],
    window_days: int = 7
) -> List[Dict]:
    """
    Find PRs that fix issues introduced by recent PRs.

    Args:
        prs: List of PR dictionaries sorted by merge date
        window_days: Window to look for follow-up fixes (default: 7 days)

    Returns:
        List of follow-up fix relationships
    """
    from dateutil import parser as date_parser
    from datetime import timedelta

    follow_up_fixes = []

    # Sort PRs by merged_at
    sorted_prs = sorted(prs, key=lambda p: p.get("merged_at", ""))

    for i, pr in enumerate(sorted_prs):
        if not pr.get("merged_at"):
            continue

        pr_merged = date_parser.parse(pr["merged_at"])

        # Look for follow-up PRs within window
        for follow_pr in sorted_prs[i+1:]:
            if not follow_pr.get("merged_at"):
                continue

            follow_merged = date_parser.parse(follow_pr["merged_at"])
            days_diff = (follow_merged - pr_merged).days

            # Check if within window
            if days_diff > window_days:
                break  # No need to check further

            # Check if it's a fix (by title keywords)
            fix_keywords = ["fix", "bug", "hotfix", "patch", "repair", "correct"]
            title_lower = follow_pr.get("title", "").lower()

            if any(keyword in title_lower for keyword in fix_keywords):
                # Check if it touches same files
                pr_files = set(pr.get("files_changed", []))
                follow_files = set(follow_pr.get("files_changed", []))

                if pr_files and follow_files and pr_files.intersection(follow_files):
                    follow_up_fixes.append({
                        "original_pr": pr["number"],
                        "fix_pr": follow_pr["number"],
                        "days_to_fix": days_diff,
                        "original_title": pr["title"],
                        "fix_title": follow_pr["title"],
                        "shared_files": list(pr_files.intersection(follow_files))[:5]  # Sample
                    })

    return follow_up_fixes
