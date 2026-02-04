#!/usr/bin/env python3
"""
Repository discovery script.

Scans cloned repos and writes config/repositories-discovered.yaml with
has_helm, helm_path, languages, and repo_type. Run after cloning to enrich
minimal repository config. Loader merges this file when present.

Usage:
    python repo_discovery.py
    python repo_discovery.py --config /path/to/repositories.yaml
"""

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import yaml
from modules.ingest.core.repository_loader import load_repositories, _resolve_config_path, _resolve_discovered_path
from modules.ingest.core.repo_discovery import RepoDiscovery

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Discover repo metadata (Helm, languages, repo type) and write repositories-discovered.yaml'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to repositories.yaml (default: REPOSITORIES_CONFIG or config/repositories.yaml)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be written without writing'
    )
    args = parser.parse_args()

    config_path = args.config or _resolve_config_path()
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return 1

    repos, repos_base_dir = load_repositories(config_path=config_path)
    if not repos:
        logger.warning("No repositories in config")
        return 0

    base_dir = Path(repos_base_dir or './repos')
    if not base_dir.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        base_dir = project_root / base_dir

    discovery = RepoDiscovery()
    discovered = {}
    for repo_id in repos:
        repo_path = base_dir / repo_id
        if not repo_path.is_dir():
            logger.debug(f"Skipping {repo_id}: path not found {repo_path}")
            continue
        meta = discovery.discover(repo_path)
        if meta:
            discovered[repo_id] = meta
            logger.info(f"Discovered {repo_id}: helm={meta.get('has_helm')}, type={meta.get('repo_type')}, langs={meta.get('languages')}")

    if not discovered:
        logger.warning("No repos found on disk to discover")
        return 0

    out_data = {'repos': discovered}
    out_path = _resolve_discovered_path(config_path)

    if args.dry_run:
        print(yaml.dump(out_data, default_flow_style=False, sort_keys=False))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        yaml.dump(out_data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Wrote {len(discovered)} discovered entries to {out_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
