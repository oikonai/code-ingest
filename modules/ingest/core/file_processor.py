"""
File Processor for Language-Specific Processing

Handles file categorization and language-specific code processing.
Following CLAUDE.md: <500 lines, single responsibility (file processing orchestration).
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from .config import RepoConfig
from .collection_assignment import CollectionAssigner
from ..services.content_filter import content_filter

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Processes files by language with checkpoint resume support.

    Responsibilities:
    - Categorize files by programming language
    - Process Rust files with AST parsing
    - Process TypeScript/JavaScript files with AST parsing
    - Process Solidity smart contract files
    - Process documentation (Markdown) files
    - Classify business domains and repository components
    """

    def __init__(
        self,
        rust_parser,
        typescript_parser,
        solidity_parser,
        documentation_parser,
        checkpoint_manager,
        batch_processor,
        config,
        yaml_parser=None,
        terraform_parser=None,
        cicd_parser=None
    ):
        """
        Initialize file processor.

        Args:
            rust_parser: RustASTParser instance
            typescript_parser: TypeScriptASTParser instance
            solidity_parser: SolidityASTParser instance
            documentation_parser: DocumentationParser instance
            checkpoint_manager: CheckpointManager instance
            batch_processor: BatchProcessor instance
            config: IngestionConfig instance
            yaml_parser: Optional YAMLParser instance
            terraform_parser: Optional TerraformParser instance
            cicd_parser: Optional CICDParser instance
        """
        self.rust_parser = rust_parser
        self.typescript_parser = typescript_parser
        self.solidity_parser = solidity_parser
        self.documentation_parser = documentation_parser
        self.yaml_parser = yaml_parser
        self.terraform_parser = terraform_parser
        self.cicd_parser = cicd_parser
        self.checkpoint_manager = checkpoint_manager
        self.batch_processor = batch_processor
        self.config = config
        
        # Initialize collection assigner for multi-collection support
        self.collection_assigner = CollectionAssigner(config)

        logger.info("📁 File processor initialized")

    def categorize_files_by_language(self, repo_path: Path) -> Dict[str, List[Path]]:
        """
        Categorize all code files in a repository by language.

        Args:
            repo_path: Path to repository root

        Returns:
            Dict mapping language name to list of file paths
        """
        language_files = {
            'rust': [],
            'typescript': [],
            'javascript': [],
            'jsx': [],
            'tsx': [],
            'solidity': [],
            'documentation': [],
            'yaml': [],
            'terraform': [],
            'cicd': []
        }

        for path in repo_path.rglob('*'):
            if not path.is_file():
                continue

            # Skip directories
            if any(skip_dir in path.parts for skip_dir in self.config.skip_dirs):
                continue

            # Skip excluded files (lock files, build artifacts, etc.)
            file_path_str = str(path)
            if not content_filter.should_include_file(file_path_str):
                logger.debug(f"⏭️  Skipping excluded file: {path.name}")
                continue

            # Skip files that are too large
            try:
                if path.stat().st_size > self.config.max_file_size:
                    logger.debug(f"⏭️  Skipping large file: {path.name} ({path.stat().st_size} bytes)")
                    continue
            except:
                continue

            # Categorize by extension and path
            ext = path.suffix.lower()
            if ext == '.rs':
                language_files['rust'].append(path)
            elif ext == '.ts':
                language_files['typescript'].append(path)
            elif ext == '.tsx':
                language_files['tsx'].append(path)
            elif ext == '.js':
                language_files['javascript'].append(path)
            elif ext == '.jsx':
                language_files['jsx'].append(path)
            elif ext == '.sol':
                language_files['solidity'].append(path)
            elif ext in ['.md', '.markdown']:
                language_files['documentation'].append(path)
            elif ext in ['.yaml', '.yml']:
                # Distinguish CI/CD from generic YAML
                if '.github/workflows' in str(path) or '.gitlab-ci' in path.name or '.circleci' in str(path):
                    language_files['cicd'].append(path)
                else:
                    language_files['yaml'].append(path)
            elif ext in ['.tf', '.tfvars']:
                language_files['terraform'].append(path)
            elif path.name == 'Jenkinsfile':
                language_files['cicd'].append(path)

        # Log summary
        logger.info(f"📊 Found files by language in {repo_path.name}:")
        for lang, files in language_files.items():
            if files:
                logger.info(f"  📄 {lang}: {len(files)} files")

        return language_files

    def process_rust_files(self, files: List[Path], repo_config: RepoConfig) -> Dict[str, Any]:
        """
        Process Rust files with checkpoint resume support and multi-collection storage.

        Args:
            files: List of Rust file paths
            repo_config: Repository configuration with metadata

        Returns:
            Statistics dictionary with chunks, domains, errors
        """
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        repo_id = repo_config.github_url.split('/')[-1]  # Extract repo name from URL
        all_chunks = []

        # Load checkpoint to skip already-processed files
        processed_files = self.checkpoint_manager.get_processed_files(repo_id, 'rust')
        processed_file_paths = list(processed_files)

        for file_path in files:
            # Skip if already processed
            if str(file_path) in processed_files:
                logger.debug(f"⏭️ Skipping already-processed file: {file_path}")
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse with AST
                parse_result = self.rust_parser.parse_file(str(file_path), content, repo_id)

                if parse_result.success:
                    # Enhance chunks with enhanced metadata
                    for chunk in parse_result.chunks:
                        if self.rust_parser.validate_chunk(chunk):
                            # Enhance with parser-specific metadata (API endpoints, dependencies)
                            chunk = self.rust_parser.enhance_chunk_metadata(chunk)
                            
                            # Add repository metadata
                            domain = self._classify_business_domain(chunk.content, chunk.file_path)
                            chunk.metadata['business_domain'] = domain
                            chunk.metadata['repo_id'] = repo_id
                            chunk.metadata['repo_component'] = self._extract_repo_component(
                                file_path, repo_id
                            )
                            chunk.metadata['service_type'] = repo_config.repo_type.value
                            chunk.metadata['depends_on_services'] = repo_config.service_dependencies
                            
                            # Add Helm info if available
                            if repo_config.has_helm:
                                chunk.metadata['helm_chart_name'] = repo_config.helm_path
                            
                            all_chunks.append(chunk)
                else:
                    stats['errors'].append(
                        f"Parse failed for {file_path}: {parse_result.error_message}"
                    )

                # Track successfully processed file
                processed_file_paths.append(str(file_path))

                # Save checkpoint every N files
                if len(processed_file_paths) % self.config.checkpoint_frequency == 0:
                    self.checkpoint_manager.save_checkpoint(
                        repo_id, 'rust', processed_file_paths, len(all_chunks), stats['errors']
                    )

            except Exception as e:
                stats['errors'].append(f"Error processing {file_path}: {e}")

        # Process and store embeddings in streaming batches with multi-collection support
        if all_chunks:
            logger.info(f"📊 Processing {len(all_chunks)} Rust chunks for embedding")
            
            # Determine target collections for first chunk (all chunks from same repo have same collections)
            sample_chunk = all_chunks[0]
            target_collections = self.collection_assigner.get_target_collections(
                chunk=sample_chunk,
                repo_config=repo_config,
                language='rust'
            )
            
            logger.info(f"🎯 Storing to collections: {', '.join(target_collections)}")
            
            total_stored = self.batch_processor.stream_chunks_to_storage(
                all_chunks, target_collections, 'rust'
            )

            # Track stats for all collections
            for collection in target_collections:
                stats['chunks_by_collection'][collection] = total_stored

            # Count by business domain
            for chunk in all_chunks:
                domain = chunk.metadata.get('business_domain', 'unknown')
                stats['business_domains'][domain] = stats['business_domains'].get(domain, 0) + 1

        return stats

    def process_typescript_files(
        self, files: List[Path], repo_config: RepoConfig, language: str
    ) -> Dict[str, Any]:
        """
        Process TypeScript/JavaScript files with checkpoint resume support and multi-collection storage.

        Args:
            files: List of TypeScript/JS file paths
            repo_config: Repository configuration with metadata
            language: Specific language (typescript, jsx, tsx, javascript)

        Returns:
            Statistics dictionary
        """
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        repo_id = repo_config.github_url.split('/')[-1]
        all_chunks = []

        # Load checkpoint
        processed_files = self.checkpoint_manager.get_processed_files(repo_id, language)
        processed_file_paths = list(processed_files)

        for file_path in files:
            if str(file_path) in processed_files:
                logger.debug(f"⏭️ Skipping already-processed file: {file_path}")
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                parse_result = self.typescript_parser.parse_file(str(file_path), content, repo_id)

                if parse_result.success:
                    for ts_chunk in parse_result.chunks:
                        if self.typescript_parser.validate_chunk(ts_chunk):
                            # Enhance with parser-specific metadata
                            ts_chunk = self.typescript_parser.enhance_chunk_metadata(ts_chunk)
                            
                            # Convert to RustCodeChunk format for compatibility
                            from ..parsers.rust_parser import RustCodeChunk

                            domain = self._classify_business_domain(ts_chunk.content, ts_chunk.file_path)

                            rust_chunk = RustCodeChunk(
                                file_path=ts_chunk.file_path,
                                content=ts_chunk.content,
                                start_line=ts_chunk.start_line,
                                end_line=ts_chunk.end_line,
                                item_name=ts_chunk.item_name,
                                item_type=ts_chunk.item_type,
                                use_statements=ts_chunk.imports,
                                doc_comments=[],
                                metadata={
                                    'language': language,
                                    'repo_id': repo_id,
                                    'repo_component': self._extract_repo_component(file_path, repo_id),
                                    'business_domain': domain,
                                    'complexity_score': ts_chunk.metadata.get('complexity_score', 1.0),
                                    'line_count': ts_chunk.metadata.get('line_count', 0),
                                    'service_type': repo_config.repo_type.value,
                                    'depends_on_services': repo_config.service_dependencies,
                                    # Copy enhanced metadata from TypeScript parser
                                    'api_endpoints': ts_chunk.metadata.get('api_endpoints', []),
                                    'api_consumes': ts_chunk.metadata.get('api_consumes', []),
                                    'imports': ts_chunk.metadata.get('imports', []),
                                    'component_dependencies': ts_chunk.metadata.get('component_dependencies', [])
                                }
                            )
                            
                            # Add Helm info if available
                            if repo_config.has_helm:
                                rust_chunk.metadata['helm_chart_name'] = repo_config.helm_path
                                
                            all_chunks.append(rust_chunk)
                else:
                    stats['errors'].append(f"Parse failed for {file_path}: {parse_result.error_message}")

                processed_file_paths.append(str(file_path))

                if len(processed_file_paths) % self.config.checkpoint_frequency == 0:
                    self.checkpoint_manager.save_checkpoint(
                        repo_id, language, processed_file_paths, len(all_chunks), stats['errors']
                    )

            except Exception as e:
                stats['errors'].append(f"Error processing {file_path}: {e}")

        if all_chunks:
            logger.info(f"📊 Processing {len(all_chunks)} {language} chunks for embedding")
            
            # Determine target collections
            sample_chunk = all_chunks[0]
            target_collections = self.collection_assigner.get_target_collections(
                chunk=sample_chunk,
                repo_config=repo_config,
                language=language
            )
            
            logger.info(f"🎯 Storing to collections: {', '.join(target_collections)}")
            
            total_stored = self.batch_processor.stream_chunks_to_storage(
                all_chunks, target_collections, language
            )

            # Track stats for all collections
            for collection in target_collections:
                stats['chunks_by_collection'][collection] = total_stored

            for chunk in all_chunks:
                domain = chunk.metadata.get('business_domain', 'unknown')
                stats['business_domains'][domain] = stats['business_domains'].get(domain, 0) + 1

        return stats

    def process_solidity_files(self, files: List[Path], repo_id: str) -> Dict[str, Any]:
        """
        Process Solidity smart contract files in batches.

        Args:
            files: List of Solidity file paths
            repo_id: Repository identifier

        Returns:
            Statistics dictionary
        """
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        collection_name = self.config.collections['solidity']
        total_stored = 0

        # Load checkpoint and filter files
        processed_files = self.checkpoint_manager.get_processed_files(repo_id, 'solidity')
        files = [f for f in files if str(f) not in processed_files]
        processed_file_paths = list(processed_files)

        # Process in batches (using standard batch size)
        file_batch_size = self.config.batch_size

        for i in range(0, len(files), file_batch_size):
            file_batch = files[i:i + file_batch_size]
            logger.info(
                f"📁 Processing Solidity file batch {i//file_batch_size + 1}/"
                f"{(len(files) + file_batch_size - 1)//file_batch_size} ({len(file_batch)} files)"
            )

            batch_chunks = []
            for file_path in file_batch:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    parse_result = self.solidity_parser.parse_file(str(file_path), content, repo_id)

                    if parse_result.success:
                        for sol_chunk in parse_result.chunks:
                            if self.solidity_parser.validate_chunk(sol_chunk):
                                # Convert to RustCodeChunk for compatibility
                                from ..parsers.rust_parser import RustCodeChunk

                                rust_chunk = RustCodeChunk(
                                    file_path=sol_chunk.file_path,
                                    content=sol_chunk.content,
                                    start_line=sol_chunk.start_line,
                                    end_line=sol_chunk.end_line,
                                    item_name=sol_chunk.item_name,
                                    item_type=sol_chunk.item_type,
                                    use_statements=sol_chunk.imports,
                                    doc_comments=[],
                                    metadata={
                                        'language': 'solidity',
                                        'repo_id': repo_id,
                                        'repo_component': self._extract_repo_component(file_path, repo_id),
                                        'business_domain': 'contracts',
                                        'complexity_score': sol_chunk.metadata.get('complexity_score', 1.0),
                                        'line_count': sol_chunk.metadata.get('line_count', 0),
                                        'contract_type': sol_chunk.metadata.get('contract_type', 'application')
                                    }
                                )
                                batch_chunks.append(rust_chunk)
                    else:
                        stats['errors'].append(f"Parse failed for {file_path}: {parse_result.error_message}")

                    processed_file_paths.append(str(file_path))

                except Exception as e:
                    stats['errors'].append(f"Error processing {file_path}: {e}")

            # Stream this batch to Qdrant
            if batch_chunks:
                logger.info(f"📊 Processing {len(batch_chunks)} Solidity chunks")
                # Fix: pass collection_name as a list
                batch_stored = self.batch_processor.stream_chunks_to_storage(
                    batch_chunks, [collection_name], 'solidity'
                )
                total_stored += batch_stored

                for chunk in batch_chunks:
                    domain = chunk.metadata.get('business_domain', 'unknown')
                    stats['business_domains'][domain] = stats['business_domains'].get(domain, 0) + 1

                # Save checkpoint
                self.checkpoint_manager.save_checkpoint(
                    repo_id, 'solidity', processed_file_paths, total_stored, stats['errors']
                )

        if total_stored > 0:
            stats['chunks_by_collection'][collection_name] = total_stored

        return stats

    def process_documentation_files(self, files: List[Path], repo_id: str) -> Dict[str, Any]:
        """Process documentation (Markdown) files."""
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        all_doc_chunks = []

        processed_files = self.checkpoint_manager.get_processed_files(repo_id, 'documentation')
        processed_file_paths = list(processed_files)

        for file_path in files:
            if str(file_path) in processed_files:
                logger.debug(f"⏭️ Skipping already-processed file: {file_path}")
                continue

            try:
                logger.info(f"📚 Processing documentation: {file_path.name}")
                doc_chunks = self.documentation_parser.parse_file(str(file_path))

                if doc_chunks:
                    logger.info(f"📄 Parsed {file_path.name}: {len(doc_chunks)} documentation chunks")
                    # Add repo_id to each doc chunk for collection assignment
                    for chunk in doc_chunks:
                        chunk['repo_id'] = repo_id
                    all_doc_chunks.extend(doc_chunks)
                else:
                    logger.warning(f"⚠️ No chunks extracted from {file_path}")

                processed_file_paths.append(str(file_path))

                if len(processed_file_paths) % self.config.checkpoint_frequency == 0:
                    self.checkpoint_manager.save_checkpoint(
                        repo_id, 'documentation', processed_file_paths, len(all_doc_chunks), stats['errors']
                    )

            except Exception as e:
                error_msg = f"Error processing documentation {file_path}: {e}"
                stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")

        if all_doc_chunks:
            logger.info(f"📊 Processing {len(all_doc_chunks)} documentation chunks for embedding")
            
            # Determine target collections - documentation always goes to documentation collection
            # Could also add BY_CONCERN logic here if needed
            doc_collection = self.config.collections.get('documentation', 'documentation')
            target_collections = [doc_collection]
            
            logger.info(f"🎯 Storing to collections: {', '.join(target_collections)}")
            
            total_stored = self.batch_processor.stream_docs_to_storage(all_doc_chunks, target_collections)

            # Track stats for all collections
            for collection in target_collections:
                stats['chunks_by_collection'][collection] = total_stored

            for chunk in all_doc_chunks:
                domain = chunk.get('business_domain', 'unknown')
                stats['business_domains'][domain] = stats['business_domains'].get(domain, 0) + 1

        return stats

    def process_yaml_files(self, files: List[Path], repo_id: str) -> Dict[str, Any]:
        """Process YAML and Helm files."""
        if not self.yaml_parser:
            logger.warning("⚠️ YAML parser not initialized, skipping YAML files")
            return {'chunks_by_collection': {}, 'business_domains': {}, 'errors': []}
        
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        collection_name = self.config.collections.get('yaml', 'code_yaml')
        all_metadata_items = []

        for file_path in files:
            try:
                logger.info(f"📄 Processing YAML: {file_path.name}")
                metadata_items = self.yaml_parser.parse_file(file_path)
                
                if metadata_items:
                    all_metadata_items.extend(metadata_items)
                    logger.info(f"✅ Parsed {file_path.name}: {len(metadata_items)} items")
            
            except Exception as e:
                error_msg = f"Error processing YAML {file_path}: {e}"
                stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")

        # Convert metadata to chunks and store
        if all_metadata_items:
            logger.info(f"📊 Processing {len(all_metadata_items)} YAML items for embedding")
            from ..parsers.rust_parser import RustCodeChunk
            
            chunks = []
            for item in all_metadata_items:
                chunk = RustCodeChunk(
                    file_path=item.file_path,
                    content=item.full_content,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    item_name=item.item_name,
                    item_type=item.item_type,
                    use_statements=[],
                    doc_comments=[],
                    metadata=item.to_dict()
                )
                chunks.append(chunk)
            
            total_stored = self.batch_processor.stream_chunks_to_storage(
                chunks, [collection_name], 'yaml'
            )
            stats['chunks_by_collection'][collection_name] = total_stored

        return stats

    def process_terraform_files(self, files: List[Path], repo_id: str) -> Dict[str, Any]:
        """Process Terraform/IaC files."""
        if not self.terraform_parser:
            logger.warning("⚠️ Terraform parser not initialized, skipping Terraform files")
            return {'chunks_by_collection': {}, 'business_domains': {}, 'errors': []}
        
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        collection_name = self.config.collections.get('terraform', 'code_terraform')
        all_metadata_items = []

        for file_path in files:
            try:
                logger.info(f"🏗️  Processing Terraform: {file_path.name}")
                metadata_items = self.terraform_parser.parse_file(file_path)
                
                if metadata_items:
                    all_metadata_items.extend(metadata_items)
                    logger.info(f"✅ Parsed {file_path.name}: {len(metadata_items)} resources")
            
            except Exception as e:
                error_msg = f"Error processing Terraform {file_path}: {e}"
                stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")

        # Convert metadata to chunks and store
        if all_metadata_items:
            logger.info(f"📊 Processing {len(all_metadata_items)} Terraform items for embedding")
            from ..parsers.rust_parser import RustCodeChunk
            
            chunks = []
            for item in all_metadata_items:
                chunk = RustCodeChunk(
                    file_path=item.file_path,
                    content=item.full_content,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    item_name=item.item_name,
                    item_type=item.item_type,
                    use_statements=[],
                    doc_comments=[],
                    metadata=item.to_dict()
                )
                chunks.append(chunk)
            
            total_stored = self.batch_processor.stream_chunks_to_storage(
                chunks, [collection_name], 'terraform'
            )
            stats['chunks_by_collection'][collection_name] = total_stored

        return stats

    def process_cicd_files(self, files: List[Path], repo_id: str) -> Dict[str, Any]:
        """Process CI/CD workflow files."""
        if not self.cicd_parser:
            logger.warning("⚠️ CI/CD parser not initialized, skipping CI/CD files")
            return {'chunks_by_collection': {}, 'business_domains': {}, 'errors': []}
        
        stats = {
            'chunks_by_collection': {},
            'business_domains': {},
            'errors': []
        }

        collection_name = self.config.collections.get('cicd', 'cicd')
        all_metadata_items = []

        for file_path in files:
            try:
                logger.info(f"⚙️  Processing CI/CD: {file_path.name}")
                metadata_items = self.cicd_parser.parse_file(file_path)
                
                if metadata_items:
                    all_metadata_items.extend(metadata_items)
                    logger.info(f"✅ Parsed {file_path.name}: {len(metadata_items)} workflows")
            
            except Exception as e:
                error_msg = f"Error processing CI/CD {file_path}: {e}"
                stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")

        # Convert metadata to chunks and store
        if all_metadata_items:
            logger.info(f"📊 Processing {len(all_metadata_items)} CI/CD items for embedding")
            from ..parsers.rust_parser import RustCodeChunk
            
            chunks = []
            for item in all_metadata_items:
                chunk = RustCodeChunk(
                    file_path=item.file_path,
                    content=item.full_content,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    item_name=item.item_name,
                    item_type=item.item_type,
                    use_statements=[],
                    doc_comments=[],
                    metadata=item.to_dict()
                )
                chunks.append(chunk)
            
            total_stored = self.batch_processor.stream_chunks_to_storage(
                chunks, [collection_name], 'cicd'
            )
            stats['chunks_by_collection'][collection_name] = total_stored

        return stats

    def _classify_business_domain(self, content: str, file_path: str) -> str:
        """Classify business domain based on content and file path."""
        content_lower = content.lower()

        for domain, patterns in self.config.domain_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                return domain

        # Fallback to path-based detection
        path_lower = file_path.lower()
        if 'auth' in path_lower:
            return 'auth'
        elif 'contract' in path_lower:
            return 'contracts'
        elif 'ui' in path_lower or 'component' in path_lower:
            return 'ui'

        return 'general'

    def _extract_repo_component(self, file_path: Path, repo_id: str) -> str:
        """Extract which repository component this file belongs to."""
        path_str = str(file_path)

        # Monorepo app detection (for Turborepo/pnpm workspaces)
        if 'apps/platform' in path_str or '/platform/src' in path_str:
            return 'platform'
        elif 'apps/credit-app' in path_str or '/credit-app/src' in path_str:
            return 'credit-app'
        elif 'apps/idr' in path_str or '/idr/src' in path_str:
            return 'idr'
        elif 'packages/ui' in path_str or '/packages/ui' in path_str:
            return 'shared-ui'
        elif 'packages/' in path_str:
            return 'shared-packages'

        # Standard component detection (for non-monorepo projects)
        if 'api' in path_str:
            return 'api'
        elif 'contracts' in path_str:
            return 'contracts'
        elif 'cli' in path_str:
            return 'cli'
        elif 'docs' in path_str or 'documentation' in path_str:
            return 'documentation'
        elif 'frontend' in path_str:
            return 'frontend'
        elif 'backend' in path_str:
            return 'backend'

        return 'core'
