#!/usr/bin/env python3
"""
Derive service_dependencies from cloned repos and write config/repositories-relationships.yaml.

Scans YAML/Helm files in each repo, runs DependencyAnalyzer, and writes per-repo
service_dependencies. Run after ingestion to refresh the relationship file.
The loader merges it when building REPOSITORIES (user-set service_dependencies in
base YAML take precedence).

Usage:
    python derive_dependencies.py
    python derive_dependencies.py --config /path/to/repositories.yaml
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import yaml
from modules.ingest.core.repository_loader import (
    load_repositories,
    _resolve_config_path,
    _resolve_relationships_path,
)
from modules.ingest.parsers.yaml_parser import YAMLParser
from modules.ingest.analysis.dependency_analyzer import DependencyAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_SKIP_DIRS = {'target', '.git', 'node_modules', '__pycache__', 'dist', 'build'}


def _collect_yaml_metadata(repo_path: Path, repo_id: str) -> List[Any]:
    """Parse YAML/Helm files in repo and return list of CodeItemMetadata for DependencyAnalyzer."""
    parser = YAMLParser(repo_id=repo_id, repo_component='helm')
    items = []
    for ext in ('*.yaml', '*.yml'):
        for path in repo_path.rglob(ext):
            if not path.is_file():
                continue
            if any(d in path.parts for d in DEFAULT_SKIP_DIRS):
                continue
            try:
                items.extend(parser.parse_file(path))
            except Exception as e:
                logger.debug(f"Skip {path}: {e}")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Derive service_dependencies from repos and write repositories-relationships.yaml'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to repositories.yaml'
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

    all_repo_data: Dict[str, List[Any]] = {}
    for repo_id in repos:
        repo_path = base_dir / repo_id
        if not repo_path.is_dir():
            logger.debug(f"Skipping {repo_id}: path not found {repo_path}")
            continue
        items = _collect_yaml_metadata(repo_path, repo_id)
        if items:
            all_repo_data[repo_id] = items
            logger.info(f"Collected {len(items)} YAML metadata items for {repo_id}")

    if not all_repo_data:
        logger.warning("No YAML metadata collected from any repo")
        return 0

    analyzer = DependencyAnalyzer(all_repo_data)
    analyzer.analyze_all_dependencies()
    derived = analyzer.get_derived_service_dependencies()

    out_data = {
        'repos': {
            repo_id: {'service_dependencies': deps}
            for repo_id, deps in derived.items()
            if deps
        }
    }
    if not out_data['repos']:
        logger.warning("No derived service_dependencies")
        return 0

    out_path = _resolve_relationships_path(config_path)

    if args.dry_run:
        print(yaml.dump(out_data, default_flow_style=False, sort_keys=False))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        yaml.dump(out_data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Wrote relationships for {len(out_data['repos'])} repos to {out_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
