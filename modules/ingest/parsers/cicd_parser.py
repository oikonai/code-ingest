"""
CI/CD Workflow Parser

Parses CI/CD workflow files from various platforms (GitHub Actions, GitLab CI, etc.)
and extracts workflow metadata, jobs, triggers, and deployment information.

Following CLAUDE.md: <500 lines, single responsibility (CI/CD parsing only).
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional
import logging

from ..core.metadata_schema import CodeItemMetadata, IndexGranularity, ServiceType, ArchitecturalLayer

logger = logging.getLogger(__name__)


class CICDParser:
    """
    Parser for CI/CD workflow files.
    
    Supports:
    - GitHub Actions (.github/workflows/*.yml)
    - GitLab CI (.gitlab-ci.yml)
    - Other CI/CD platforms (extensible)
    """
    
    def __init__(self, repo_id: str, repo_component: str = "cicd"):
        """
        Initialize CI/CD parser.
        
        Args:
            repo_id: Repository identifier
            repo_component: Component within repo (default: 'cicd')
        """
        self.repo_id = repo_id
        self.repo_component = repo_component
    
    def parse_file(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Route to appropriate parser based on CI/CD platform.
        
        Args:
            file_path: Path to workflow file
            
        Returns:
            List of metadata items (typically one per workflow file)
        """
        try:
            if ".github/workflows" in str(file_path):
                return self.parse_github_actions(file_path)
            elif file_path.name == ".gitlab-ci.yml":
                return self.parse_gitlab_ci(file_path)
            elif file_path.name == "Jenkinsfile":
                return self.parse_jenkinsfile(file_path)
            elif ".circleci" in str(file_path):
                return self.parse_circleci(file_path)
            else:
                logger.warning(f"Unknown CI/CD file type: {file_path}")
                return []
        except Exception as e:
            logger.error(f"Error parsing CI/CD file {file_path}: {e}")
            return []
    
    def parse_github_actions(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse GitHub Actions workflow files.
        
        Extracts:
        - Workflow name and triggers
        - Jobs and steps
        - Actions used
        - Deployment targets
        - Test/lint detection
        
        Args:
            file_path: Path to GitHub Actions workflow file
            
        Returns:
            List with single metadata item for the workflow
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            workflow_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error in {file_path}: {e}")
            return []
        
        if not isinstance(workflow_data, dict):
            logger.warning(f"Invalid workflow data in {file_path}")
            return []
        
        workflow_name = workflow_data.get('name', file_path.stem)
        
        # Extract triggers
        triggers = []
        if 'on' in workflow_data:
            on_data = workflow_data['on']
            if isinstance(on_data, dict):
                triggers = list(on_data.keys())
            elif isinstance(on_data, list):
                triggers = on_data
            elif isinstance(on_data, str):
                triggers = [on_data]
        
        # Extract jobs
        jobs = []
        if isinstance(workflow_data.get('jobs'), dict):
            jobs = list(workflow_data['jobs'].keys())
        
        # Extract actions used
        actions_used = []
        for job_name, job_data in workflow_data.get('jobs', {}).items():
            if isinstance(job_data, dict):
                for step in job_data.get('steps', []):
                    if isinstance(step, dict) and 'uses' in step:
                        actions_used.append(step['uses'])
        
        # Detect what this workflow does
        deploys_to = []
        runs_tests = False
        runs_linting = False
        
        content_lower = content.lower()
        
        # Deployment detection
        if any(keyword in content_lower for keyword in ['deploy', 'kubectl', 'helm']):
            if 'production' in content_lower or 'prod' in content_lower:
                deploys_to.append('production')
            if 'staging' in content_lower:
                deploys_to.append('staging')
            if 'dev' in content_lower or 'development' in content_lower:
                deploys_to.append('development')
        
        # Test detection
        if any(keyword in content_lower for keyword in ['test', 'jest', 'pytest', 'mocha', 'cargo test']):
            runs_tests = True
        
        # Lint detection
        if any(keyword in content_lower for keyword in ['lint', 'eslint', 'flake8', 'clippy', 'pylint']):
            runs_linting = True
        
        # Extract environment variables (for dependencies)
        env_vars = {}
        if isinstance(workflow_data.get('env'), dict):
            env_vars = workflow_data['env']
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name=f"workflow/{workflow_name}",
            item_type="ci_workflow",
            language="yaml",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="devops",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE,
            workflow_name=workflow_name,
            workflow_triggers=triggers,
            workflow_jobs=jobs,
            deployed_services=deploys_to,
            env_vars={k: str(v) for k, v in env_vars.items()}
        )
        
        return [metadata]
    
    def parse_gitlab_ci(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse GitLab CI configuration.
        
        Args:
            file_path: Path to .gitlab-ci.yml
            
        Returns:
            List with single metadata item for the CI config
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            gitlab_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error in {file_path}: {e}")
            return []
        
        if not isinstance(gitlab_data, dict):
            return []
        
        # Extract stages
        stages = gitlab_data.get('stages', [])
        
        # Extract job names (top-level keys that aren't GitLab keywords)
        gitlab_keywords = {'stages', 'variables', 'before_script', 'after_script', 'image', 'services', 'cache', 'include'}
        jobs = [key for key in gitlab_data.keys() if key not in gitlab_keywords and not key.startswith('.')]
        
        # Extract triggers (from rules, only, etc.)
        triggers = []
        for job_data in gitlab_data.values():
            if isinstance(job_data, dict):
                if 'only' in job_data:
                    only = job_data['only']
                    if isinstance(only, list):
                        triggers.extend(only)
                if 'rules' in job_data:
                    triggers.append('rules-based')
        
        triggers = list(set(triggers))  # Remove duplicates
        
        # Detect deployment
        deploys_to = []
        content_lower = content.lower()
        if 'deploy' in content_lower:
            if 'production' in content_lower:
                deploys_to.append('production')
            if 'staging' in content_lower:
                deploys_to.append('staging')
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name="gitlab-ci/pipeline",
            item_type="ci_workflow",
            language="yaml",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="devops",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE,
            workflow_name="GitLab CI Pipeline",
            workflow_triggers=triggers,
            workflow_jobs=jobs,
            deployed_services=deploys_to
        )
        
        return [metadata]
    
    def parse_jenkinsfile(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse Jenkinsfile (Groovy-based, so basic text parsing).
        
        Args:
            file_path: Path to Jenkinsfile
            
        Returns:
            List with single metadata item
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic stage extraction (Jenkinsfile uses Groovy syntax)
        import re
        stage_pattern = r"stage\s*\(\s*['\"]([^'\"]+)['\"]"
        stages = re.findall(stage_pattern, content)
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name="jenkins/pipeline",
            item_type="ci_workflow",
            language="groovy",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="devops",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE,
            workflow_name="Jenkins Pipeline",
            workflow_jobs=stages
        )
        
        return [metadata]
    
    def parse_circleci(self, file_path: Path) -> List[CodeItemMetadata]:
        """
        Parse CircleCI configuration.
        
        Args:
            file_path: Path to .circleci/config.yml
            
        Returns:
            List with single metadata item
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            circle_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error in {file_path}: {e}")
            return []
        
        if not isinstance(circle_data, dict):
            return []
        
        # Extract jobs
        jobs = []
        if isinstance(circle_data.get('jobs'), dict):
            jobs = list(circle_data['jobs'].keys())
        
        # Extract workflows
        workflows = []
        if isinstance(circle_data.get('workflows'), dict):
            workflows = list(circle_data['workflows'].keys())
        
        metadata = CodeItemMetadata(
            file_path=str(file_path),
            item_name="circleci/config",
            item_type="ci_workflow",
            language="yaml",
            repo_id=self.repo_id,
            repo_component=self.repo_component,
            start_line=1,
            end_line=len(content.split('\n')),
            content_preview=content[:500],
            full_content=content,
            line_count=len(content.split('\n')),
            business_domain="devops",
            service_type=ServiceType.INFRASTRUCTURE,
            architectural_layer=ArchitecturalLayer.INFRASTRUCTURE,
            granularity=IndexGranularity.FILE,
            workflow_name="CircleCI Pipeline",
            workflow_jobs=jobs + workflows
        )
        
        return [metadata]

