"""
Checkpoint Manager for Ingestion Pipeline

Handles checkpoint save/load/resume functionality to enable recovery from failures.
Following CLAUDE.md: <500 lines, single responsibility (checkpoint management only).
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoint operations for ingestion pipeline recovery.

    Responsibilities:
    - Save checkpoint after processing files
    - Load checkpoint to resume from failure
    - Clear checkpoint after successful completion
    - Get list of processed files for skip logic
    """

    def __init__(self, checkpoint_file: Path = Path("./ingestion_checkpoint.json")):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint JSON file
        """
        self.checkpoint_file = checkpoint_file
        logger.info(f"📋 Checkpoint manager initialized: {checkpoint_file}")

    def save_checkpoint(
        self,
        repo_id: str,
        language: str,
        processed_file_paths: List[str],
        chunks_processed: int,
        errors: List[str]
    ) -> bool:
        """
        Save progress checkpoint to enable resume after failures.

        Args:
            repo_id: Repository identifier
            language: Language being processed
            processed_file_paths: List of file paths that have been processed
            chunks_processed: Total number of chunks processed
            errors: List of error messages (keeps last 5)

        Returns:
            True if checkpoint saved successfully, False otherwise
        """
        checkpoint_data = {
            'timestamp': str(datetime.now()),
            'repo_id': repo_id,
            'language': language,
            'processed_files': processed_file_paths,
            'chunks_processed': chunks_processed,
            'errors': errors[-5:],  # Keep last 5 errors only
        }

        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.info(
                f"💾 Checkpoint saved: {len(processed_file_paths)} {language} files "
                f"processed in {repo_id}"
            )
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to save checkpoint: {e}")
            return False

    def load_checkpoint(self) -> Optional[Dict]:
        """
        Load progress checkpoint if it exists.

        Returns:
            Dictionary containing checkpoint data, or None if no checkpoint exists
        """
        try:
            if self.checkpoint_file.exists():
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)

                logger.info(
                    f"📂 Checkpoint loaded: {checkpoint.get('repo_id')} / "
                    f"{checkpoint.get('language')} - "
                    f"{len(checkpoint.get('processed_files', []))} files"
                )
                return checkpoint

        except Exception as e:
            logger.warning(f"⚠️ Failed to load checkpoint: {e}")

        return None

    def clear_checkpoint(self) -> bool:
        """
        Clear checkpoint file after successful completion.

        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.info("✅ Checkpoint cleared")
                return True
            return True  # Already clear

        except Exception as e:
            logger.warning(f"⚠️ Failed to clear checkpoint: {e}")
            return False

    def get_processed_files(self, repo_id: str, language: str) -> Set[str]:
        """
        Get set of already-processed file paths for skip logic.

        Args:
            repo_id: Repository identifier
            language: Language to check

        Returns:
            Set of file paths that have been processed
        """
        checkpoint = self.load_checkpoint()

        if not checkpoint:
            return set()

        # Only return processed files if checkpoint matches current repo/language
        if (checkpoint.get('repo_id') == repo_id and
                checkpoint.get('language') == language):
            processed = checkpoint.get('processed_files', [])
            logger.info(
                f"📂 Resuming: {len(processed)} {language} files already processed in {repo_id}"
            )
            return set(processed)

        return set()

    def has_checkpoint(self) -> bool:
        """
        Check if a checkpoint file exists.

        Returns:
            True if checkpoint exists, False otherwise
        """
        return self.checkpoint_file.exists()

    def get_checkpoint_info(self) -> Optional[Dict[str, any]]:
        """
        Get checkpoint information without loading full data.

        Returns:
            Dictionary with checkpoint metadata or None
        """
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return None

        return {
            'timestamp': checkpoint.get('timestamp'),
            'repo_id': checkpoint.get('repo_id'),
            'language': checkpoint.get('language'),
            'files_processed': len(checkpoint.get('processed_files', [])),
            'chunks_processed': checkpoint.get('chunks_processed', 0),
            'has_errors': len(checkpoint.get('errors', [])) > 0
        }
