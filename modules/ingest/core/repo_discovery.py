"""
Repository discovery from filesystem.

Scans a cloned repo path to infer has_helm, helm_path, languages, and repo_type.
Used to enrich minimal repository config without user editing.
Following CLAUDE.md: single responsibility (discovery only); no disk write.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from .config import RepoType, Language

logger = logging.getLogger(__name__)

# Directories to skip when scanning (align with IngestionConfig.skip_dirs)
DEFAULT_SKIP_DIRS = {
    'target', '.git', 'node_modules', '__pycache__',
    '.pytest_cache', 'dist', 'build', 'public'
}

# Extension -> language key for discovery (subset of FILE_PATTERNS logic)
_EXT_TO_LANG: Dict[str, str] = {
    '.rs': 'rust',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.js': 'javascript',
    '.jsx': 'jsx',
    '.sol': 'solidity',
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.tf': 'terraform',
    '.tfvars': 'terraform',
}

# Discovery language key -> Language enum
_DISCOVERED_LANG_TO_ENUM = {
    'rust': Language.RUST,
    'typescript': Language.TYPESCRIPT,
    'tsx': Language.TSX,
    'javascript': Language.JAVASCRIPT,
    'jsx': Language.JSX,
    'solidity': Language.SOLIDITY,
    'markdown': Language.MARKDOWN,
    'yaml': Language.YAML,
    'terraform': Language.TERRAFORM,
}


def _categorize_files_by_language(repo_path: Path, skip_dirs: Optional[set] = None) -> Dict[str, List[Path]]:
    """
    Scan repo by extension and return language key -> list of paths.
    Does not depend on FileProcessor; avoids circular imports.
    """
    skip = skip_dirs or DEFAULT_SKIP_DIRS
    result: Dict[str, List[Path]] = {}
    for path in repo_path.rglob('*'):
        if not path.is_file():
            continue
        if any(d in path.parts for d in skip):
            continue
        ext = path.suffix.lower()
        lang = _EXT_TO_LANG.get(ext)
        if lang:
            if lang not in result:
                result[lang] = []
            result[lang].append(path)
        elif path.name == 'Jenkinsfile':
            lang = 'yaml'
            if lang not in result:
                result[lang] = []
            result[lang].append(path)
    return result


def _discover_languages(repo_path: Path) -> List[Language]:
    """Discover languages present in repo; return list of Language enums (deduplicated)."""
    by_lang = _categorize_files_by_language(repo_path)
    # Prefer typescript over tsx/jsx for config; include all if we want full fidelity
    seen: set = set()
    out: List[Language] = []
    for key in ('rust', 'typescript', 'tsx', 'javascript', 'jsx', 'solidity', 'markdown', 'yaml', 'terraform'):
        if key not in by_lang or not by_lang[key]:
            continue
        enum_val = _DISCOVERED_LANG_TO_ENUM.get(key)
        if enum_val and enum_val not in seen:
            seen.add(enum_val)
            out.append(enum_val)
    return out


def _discover_helm(repo_path: Path) -> tuple[bool, Optional[str]]:
    """Return (has_helm, helm_path). helm_path is the dir containing Chart.yaml relative to repo root."""
    charts = list(repo_path.rglob('Chart.yaml'))
    if not charts:
        return False, None
    # Prefer top-level helm/ or first found
    for p in sorted(charts, key=lambda x: len(x.parts)):
        try:
            rel = p.parent.relative_to(repo_path)
            path_str = rel.as_posix() if rel.parts else '.'
            return True, path_str
        except ValueError:
            continue
    return True, '.'


def _discover_repo_type(repo_path: Path) -> RepoType:
    """Heuristic repo type from root manifests. Best-effort."""
    package_json = repo_path / 'package.json'
    cargo_toml = repo_path / 'Cargo.toml'
    go_mod = repo_path / 'go.mod'
    chart_yaml = repo_path / 'Chart.yaml'
    helm_dir = repo_path / 'helm' / 'Chart.yaml'

    if package_json.exists():
        try:
            with open(package_json) as f:
                data = json.load(f)
            deps = {}
            deps.update(data.get('dependencies') or {})
            deps.update(data.get('devDependencies') or {})
            names = [k.lower() for k in deps]
            if any(x in names for x in ('react', 'vue', 'next', '@next/', 'next/')):
                return RepoType.FRONTEND
        except (json.JSONDecodeError, OSError):
            pass

    if cargo_toml.exists() or go_mod.exists():
        return RepoType.BACKEND

    if chart_yaml.exists() or helm_dir.exists():
        if not package_json.exists() and not cargo_toml.exists():
            return RepoType.INFRASTRUCTURE

    return RepoType.BACKEND


class RepoDiscovery:
    """
    Discovers repository metadata by scanning the filesystem.
    Does not write to disk; returns a dict suitable for merging into config.
    """

    def __init__(self, skip_dirs: Optional[set] = None):
        self.skip_dirs = skip_dirs or DEFAULT_SKIP_DIRS

    def discover(self, repo_path: Path) -> Dict[str, Any]:
        """
        Scan repo_path and return discovered fields only.
        Keys: has_helm (bool), helm_path (str|None), languages (list of str),
        repo_type (str). Values are serializable for YAML.
        """
        if not repo_path.is_dir():
            logger.warning(f"Repo path is not a directory: {repo_path}")
            return {}

        has_helm, helm_path = _discover_helm(repo_path)
        languages = _discover_languages(repo_path)
        repo_type = _discover_repo_type(repo_path)

        return {
            'has_helm': has_helm,
            'helm_path': helm_path,
            'languages': [e.value for e in languages],
            'repo_type': repo_type.value,
        }