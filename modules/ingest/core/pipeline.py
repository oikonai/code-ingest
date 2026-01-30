"""
Ingestion Pipeline Orchestrator

Main orchestrator for multi-language code ingestion into vector database.
Following CLAUDE.md: <500 lines, single responsibility (orchestration only).
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config import IngestionConfig, RepositoryConfig, DEFAULT_REPOSITORIES, REPOSITORIES, RepoConfig
from .checkpoint_manager import CheckpointManager
from .embedding_service import EmbeddingService
from .storage_manager import StorageManager
from .batch_processor import BatchProcessor
from .file_processor import FileProcessor

# Import parsers from parsers/ subdirectory
from ..parsers.rust_parser import RustASTParser, RustCodeChunk
from ..parsers.typescript_parser import TypeScriptASTParser
from ..parsers.solidity_parser import SolidityASTParser
from ..parsers.documentation_parser import DocumentationParser

# Import vector backend factory
from .vector_backend import create_vector_backend, VectorBackend

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Main orchestrator for multi-language ingestion pipeline.

    Coordinates:
    - Configuration management
    - Service initialization (embedding, storage)
    - File processing by language
    - Checkpoint management for resume
    - Search across languages

    Delegates actual work to specialized managers.
    """

    def __init__(self, config: Optional[IngestionConfig] = None, skip_vector_init: bool = False):
        """
        Initialize ingestion pipeline with all services.

        Args:
            config: Optional configuration (uses defaults if not provided)
            skip_vector_init: Skip vector client initialization (for warmup-only mode)
        """
        self.config = config or IngestionConfig()

        logger.info("🚀 Initializing ingestion pipeline...")

        # Initialize embedding service with Cloudflare AI Gateway
        self.checkpoint_manager = CheckpointManager(self.config.checkpoint_file)
        self.embedding_service = EmbeddingService(
            base_url=self.config.cloudflare_base_url,
            model=self.config.embedding_model,
            rate_limit=self.config.rate_limit,
            embedding_size=self.config.embedding_size,
            timeout=self.config.embedding_timeout
        )

        # Lazy-load vector client and dependent services
        self._vector_client = None
        self._storage_manager = None
        self._batch_processor = None
        self._file_processor = None
        self._skip_vector_init = skip_vector_init

        # Initialize language parsers (lightweight, no external deps)
        self.rust_parser = RustASTParser()
        self.typescript_parser = TypeScriptASTParser()
        self.solidity_parser = SolidityASTParser()
        self.documentation_parser = DocumentationParser()
        
        # Initialize new parsers for YAML, Terraform, CI/CD
        try:
            from ..parsers.yaml_parser import YAMLParser
            from ..parsers.terraform_parser import TerraformParser
            from ..parsers.cicd_parser import CICDParser
            
            self.yaml_parser = YAMLParser("", "")  # Will be configured per-repo
            self.terraform_parser = TerraformParser("", "")  # Will be configured per-repo
            self.cicd_parser = CICDParser("", "")  # Will be configured per-repo
        except ImportError:
            logger.warning("⚠️ New parsers not found, YAML/Terraform/CI-CD parsing disabled")
            self.yaml_parser = None
            self.terraform_parser = None
            self.cicd_parser = None

        logger.info("✅ Ingestion pipeline initialized")

    @property
    def vector_client(self) -> VectorBackend:
        """Lazy-load vector client on first access."""
        if self._vector_client is None:
            if self._skip_vector_init:
                raise RuntimeError("Vector client access not allowed in warmup-only mode")
            self._vector_client = create_vector_backend(
                embedding_size=self.config.embedding_size
            )
        return self._vector_client

    @property
    def storage_manager(self) -> StorageManager:
        """Lazy-load storage manager on first access."""
        if self._storage_manager is None:
            self._storage_manager = StorageManager(
                vector_client=self.vector_client,
                embedding_size=self.config.embedding_size
            )
        return self._storage_manager

    @property
    def batch_processor(self) -> BatchProcessor:
        """Lazy-load batch processor on first access."""
        if self._batch_processor is None:
            self._batch_processor = BatchProcessor(
                embedding_service=self.embedding_service,
                storage_manager=self.storage_manager,
                batch_size=self.config.batch_size,
                max_workers=self.config.rate_limit,
                max_retries=self.config.max_batch_retries
            )
        return self._batch_processor

    @property
    def file_processor(self) -> FileProcessor:
        """Lazy-load file processor on first access."""
        if self._file_processor is None:
            self._file_processor = FileProcessor(
                rust_parser=self.rust_parser,
                typescript_parser=self.typescript_parser,
                solidity_parser=self.solidity_parser,
                documentation_parser=self.documentation_parser,
                checkpoint_manager=self.checkpoint_manager,
                batch_processor=self.batch_processor,
                config=self.config,
                yaml_parser=self.yaml_parser,
                terraform_parser=self.terraform_parser,
                cicd_parser=self.cicd_parser
            )
        return self._file_processor

    def warmup_services(self, skip_vector_setup: bool = False) -> bool:
        """
        Pre-warm all services before ingestion.

        Args:
            skip_vector_setup: Skip Qdrant collection setup (for embedding-only warmup)

        Returns:
            True if warmup successful
        """
        logger.info("🔥 Warming up services...")

        # Setup Qdrant collections (unless skipped)
        if not skip_vector_setup:
            if not self.storage_manager.setup_collections(self.config.collections):
                logger.error("❌ Failed to setup Qdrant collections")
                return False

        # Warmup Modal embedding service
        if not self.embedding_service.warmup_containers(num_containers=self.config.rate_limit):
            logger.error("❌ Failed to warmup Modal service")
            return False

        logger.info("✅ All services ready")
        return True

    def ingest_repositories(
        self,
        repositories: Optional[List[RepoConfig]] = None,
        resume_from_checkpoint: bool = True,
        use_new_config: bool = True,
        min_priority: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest multiple repositories with language-specific processing.

        Args:
            repositories: List of RepoConfig objects (uses REPOSITORIES dict if not provided)
            resume_from_checkpoint: Whether to resume from saved checkpoint
            use_new_config: If True, use new REPOSITORIES dict; if False, use legacy DEFAULT_REPOSITORIES
            min_priority: Minimum priority filter (high|medium|low|ALL) - only ingest repos at or above this priority

        Returns:
            Comprehensive ingestion statistics
        """
        logger.info("🏢 Starting repository ingestion")

        # Warmup services first
        if not self.warmup_services():
            logger.error("❌ Service warmup failed, aborting ingestion")
            return {'error': 'Service warmup failed'}

        # Check for existing checkpoint
        if resume_from_checkpoint:
            checkpoint_info = self.checkpoint_manager.get_checkpoint_info()
            if checkpoint_info:
                logger.info(
                    f"📂 Resuming from checkpoint: {checkpoint_info['repo_id']} / "
                    f"{checkpoint_info['language']} - {checkpoint_info['files_processed']} files"
                )

        # Determine which repositories to use
        if repositories:
            repos = repositories
        elif use_new_config:
            # Use new REPOSITORIES dict
            repos = list(REPOSITORIES.values())
            
            # Apply priority filter if specified
            if min_priority:
                from .config import PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW
                priority_map = {
                    'high': [PRIORITY_HIGH],
                    'medium': [PRIORITY_HIGH, PRIORITY_MEDIUM],
                    'low': [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW],
                    'ALL': [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]
                }
                allowed_priorities = priority_map.get(min_priority.lower(), [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW])
                repos = [r for r in repos if r.priority in allowed_priorities]
                logger.info(f"📋 Using {len(repos)} repositories (priority >= {min_priority}) from REPOSITORIES config")
            else:
                logger.info(f"📋 Using {len(repos)} repositories from REPOSITORIES config")
        else:
            # Use legacy DEFAULT_REPOSITORIES
            repos = DEFAULT_REPOSITORIES
            logger.info(f"📋 Using {len(repos)} repositories from DEFAULT_REPOSITORIES (legacy)")

        total_stats = {
            'repositories_processed': 0,
            'files_by_language': {},
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        # Process each repository
        for repo_config in repos:
            # Handle both new RepoConfig and legacy RepositoryConfig
            if isinstance(repo_config, RepoConfig):
                # New config - check if path exists (convert github_url to local path)
                repo_name = repo_config.github_url.split('/')[-1]
                repo_path = Path(self.config.repos_base_dir) / repo_name
                if not repo_path.exists():
                    logger.warning(f"⚠️ Repository not found: {repo_path}")
                    continue
                
                logger.info(f"📂 Processing repository: {repo_name}")
                repo_stats = self._ingest_repository_new(repo_config, repo_path)
            else:
                # Legacy config
                if not Path(repo_config.path).exists():
                    logger.warning(f"⚠️ Repository not found: {repo_config.path}")
                    continue
                
                logger.info(f"📂 Processing repository: {repo_config.repo_id}")
                repo_stats = self._ingest_repository(repo_config)

            # Aggregate statistics
            total_stats['repositories_processed'] += 1

            for lang, count in repo_stats.get('files_by_language', {}).items():
                total_stats['files_by_language'][lang] = \
                    total_stats['files_by_language'].get(lang, 0) + count

            for collection, count in repo_stats.get('chunks_by_collection', {}).items():
                total_stats['chunks_by_collection'][collection] = \
                    total_stats['chunks_by_collection'].get(collection, 0) + count

            for domain, count in repo_stats.get('business_domains', {}).items():
                total_stats['business_domains'][domain] = \
                    total_stats['business_domains'].get(domain, 0) + count

            total_stats['errors'].extend(repo_stats.get('errors', []))

        # Clear checkpoint on successful completion
        self.checkpoint_manager.clear_checkpoint()

        logger.info(f"✅ Repository ingestion complete")
        self._log_statistics(total_stats)

        return total_stats

    def _ingest_repository_new(self, repo_config: RepoConfig, repo_path: Path) -> Dict[str, Any]:
        """
        Ingest a single repository using new RepoConfig with language-specific processing.

        Args:
            repo_config: Repository configuration
            repo_path: Path to the repository

        Returns:
            Repository statistics
        """
        stats = {
            'files_by_language': {},
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        # Categorize files by language
        language_files = self.file_processor.categorize_files_by_language(repo_path)

        # Process each language
        for language, files in language_files.items():
            if not files:
                continue

            repo_name = repo_config.github_url.split('/')[-1]
            logger.info(f"📝 Processing {len(files)} {language} files in {repo_name}")
            stats['files_by_language'][language] = len(files)

            # Dispatch to appropriate processor with RepoConfig
            if language == 'rust':
                lang_stats = self.file_processor.process_rust_files(files, repo_config)
            elif language in ['typescript', 'javascript', 'jsx', 'tsx']:
                lang_stats = self.file_processor.process_typescript_files(files, repo_config, language)
            elif language == 'solidity':
                # TODO: Update to use repo_config
                lang_stats = self.file_processor.process_solidity_files(files, repo_name)
            elif language == 'documentation':
                # TODO: Update to use repo_config
                lang_stats = self.file_processor.process_documentation_files(files, repo_name)
            elif language == 'yaml':
                # TODO: Update to use repo_config
                lang_stats = self.file_processor.process_yaml_files(files, repo_name)
            elif language == 'terraform':
                # TODO: Update to use repo_config
                lang_stats = self.file_processor.process_terraform_files(files, repo_name)
            elif language == 'cicd':
                # TODO: Update to use repo_config
                lang_stats = self.file_processor.process_cicd_files(files, repo_name)
            else:
                logger.warning(f"⚠️ Unsupported language: {language}")
                continue

            # Aggregate language stats
            for collection, count in lang_stats.get('chunks_by_collection', {}).items():
                stats['chunks_by_collection'][collection] = \
                    stats['chunks_by_collection'].get(collection, 0) + count

            for domain, count in lang_stats.get('business_domains', {}).items():
                stats['business_domains'][domain] = \
                    stats['business_domains'].get(domain, 0) + count

            stats['errors'].extend(lang_stats.get('errors', []))

        return stats
    
    def _ingest_repository(self, repo_config: RepositoryConfig) -> Dict[str, Any]:
        """
        Ingest a single repository with language-specific processing.

        Args:
            repo_config: Repository configuration

        Returns:
            Repository statistics
        """
        repo_path = Path(repo_config.path)
        repo_id = repo_config.repo_id

        stats = {
            'files_by_language': {},
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        # Categorize files by language
        language_files = self.file_processor.categorize_files_by_language(repo_path)

        # Process each language
        for language, files in language_files.items():
            if not files:
                continue

            logger.info(f"📝 Processing {len(files)} {language} files in {repo_id}")
            stats['files_by_language'][language] = len(files)

            # Dispatch to appropriate processor
            if language == 'rust':
                lang_stats = self.file_processor.process_rust_files(files, repo_id)
            elif language in ['typescript', 'javascript', 'jsx', 'tsx']:
                lang_stats = self.file_processor.process_typescript_files(files, repo_id, language)
            elif language == 'solidity':
                lang_stats = self.file_processor.process_solidity_files(files, repo_id)
            elif language == 'documentation':
                lang_stats = self.file_processor.process_documentation_files(files, repo_id)
            elif language == 'yaml':
                lang_stats = self.file_processor.process_yaml_files(files, repo_id)
            elif language == 'terraform':
                lang_stats = self.file_processor.process_terraform_files(files, repo_id)
            elif language == 'cicd':
                lang_stats = self.file_processor.process_cicd_files(files, repo_id)
            else:
                logger.warning(f"⚠️ Unsupported language: {language}")
                continue

            # Aggregate language stats
            for collection, count in lang_stats.get('chunks_by_collection', {}).items():
                stats['chunks_by_collection'][collection] = \
                    stats['chunks_by_collection'].get(collection, 0) + count

            for domain, count in lang_stats.get('business_domains', {}).items():
                stats['business_domains'][domain] = \
                    stats['business_domains'].get(domain, 0) + count

            stats['errors'].extend(lang_stats.get('errors', []))

        return stats

    def search_across_languages(
        self,
        query: str,
        languages: Optional[List[str]] = None,
        limit: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for code across multiple languages.

        Args:
            query: Search query text
            languages: List of languages to search (searches all if None)
            limit: Maximum results per language

        Returns:
            Dictionary mapping language to search results
        """
        # Generate query embedding
        query_embeddings = self.embedding_service.generate_embeddings([query])

        if not query_embeddings:
            logger.error("❌ Failed to generate query embedding")
            return {}

        query_vector = query_embeddings[0]

        # Search collections
        languages_to_search = languages or ['rust', 'typescript', 'solidity', 'documentation']
        results = {}

        for lang in languages_to_search:
            collection_name = self.config.collections.get(lang)
            if not collection_name:
                continue

            search_results = self.vector_client.search_vectors(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=0.3  # Lowered from 0.7 - semantic similarity typically peaks at 0.4-0.6
            )

            if search_results:
                results[lang] = search_results
                logger.info(f"🔍 Found {len(search_results)} results in {lang}")

        return results

    def _log_statistics(self, stats: Dict[str, Any]):
        """Log comprehensive ingestion statistics."""
        logger.info("\n" + "="*60)
        logger.info("📊 Ingestion Statistics:")
        logger.info("="*60)

        logger.info(f"  Repositories: {stats['repositories_processed']}")

        if stats['files_by_language']:
            logger.info("  Files by language:")
            for lang, count in stats['files_by_language'].items():
                logger.info(f"    {lang}: {count}")

        if stats['chunks_by_collection']:
            logger.info("  Chunks by collection:")
            for collection, count in stats['chunks_by_collection'].items():
                logger.info(f"    {collection}: {count}")

        if stats['business_domains']:
            logger.info("  Business domains:")
            for domain, count in stats['business_domains'].items():
                logger.info(f"    {domain}: {count}")

        if stats['errors']:
            logger.info(f"\n⚠️ Errors ({len(stats['errors'])}):")
            for error in stats['errors'][:5]:  # Show first 5
                logger.info(f"  - {error}")
            if len(stats['errors']) > 5:
                logger.info(f"  ... and {len(stats['errors']) - 5} more")

        logger.info("="*60 + "\n")


# For backward compatibility (can be removed later)
MultiLanguageIngestionPipeline = IngestionPipeline
