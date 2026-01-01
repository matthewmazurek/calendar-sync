"""Git version service for calendar file version management."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class GitVersionService:
    """Service for git-based version operations."""

    def __init__(self, repo_root: Path):
        """
        Initialize git version service.

        Args:
            repo_root: Root directory of git repository
        """
        self.repo_root = repo_root

    def get_file_versions(
        self, file_path: Path
    ) -> List[Tuple[str, datetime, str]]:
        """
        Get git log for a specific file.

        Args:
            file_path: Path to file (relative to repo root or absolute)

        Returns:
            List of (commit_hash, commit_date, commit_message) tuples
        """
        if not self._is_git_repo():
            return []

        # Get relative path from repo root
        try:
            rel_path = file_path.relative_to(self.repo_root)
        except ValueError:
            # If file_path is already relative, use it as-is
            rel_path = file_path

        try:
            # Get git log with format: hash|date|message
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--format=%H|%ai|%s",
                    "--",
                    str(rel_path),
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Git log failed: {result.stderr}")
                return []

            versions = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    parts = line.split("|", 2)
                    if len(parts) >= 3:
                        commit_hash = parts[0]
                        date_str = parts[1]
                        message = parts[2]

                        # Parse date: "2025-01-01 12:00:00 -0500"
                        commit_date = datetime.strptime(
                            date_str.split(" ")[0] + " " + date_str.split(" ")[1],
                            "%Y-%m-%d %H:%M:%S",
                        )
                        versions.append((commit_hash, commit_date, message))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse git log line: {line}, error: {e}")
                    continue

            return versions
        except Exception as e:
            logger.warning(f"Error getting git versions: {e}")
            return []

    def restore_file_version(self, file_path: Path, commit: str) -> bool:
        """
        Checkout specific version of file from git.

        Args:
            file_path: Path to file (relative to repo root or absolute)
            commit: Git commit hash or tag

        Returns:
            True if successful, False otherwise
        """
        if not self._is_git_repo():
            logger.warning("Not in a git repository")
            return False

        # Get relative path from repo root
        try:
            rel_path = file_path.relative_to(self.repo_root)
        except ValueError:
            # If file_path is already relative, use it as-is
            rel_path = file_path

        try:
            result = subprocess.run(
                ["git", "checkout", commit, "--", str(rel_path)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"Git checkout failed: {result.stderr}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error restoring file version: {e}")
            return False

    def restore_directory_version(self, dir_path: Path, commit: str) -> bool:
        """
        Checkout all files in a directory from a specific git commit.

        Args:
            dir_path: Path to directory (relative to repo root or absolute)
            commit: Git commit hash or tag

        Returns:
            True if successful, False otherwise
        """
        if not self._is_git_repo():
            logger.warning("Not in a git repository")
            return False

        # Get relative path from repo root
        try:
            rel_path = dir_path.relative_to(self.repo_root)
        except ValueError:
            # If dir_path is already relative, use it as-is
            rel_path = dir_path

        try:
            result = subprocess.run(
                ["git", "checkout", commit, "--", str(rel_path)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"Git checkout failed: {result.stderr}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error restoring directory version: {e}")
            return False

    def get_file_at_commit(
        self, file_path: Path, commit: str
    ) -> Optional[bytes]:
        """
        Get file content at specific commit without checking out.

        Args:
            file_path: Path to file (relative to repo root or absolute)
            commit: Git commit hash or tag

        Returns:
            File content as bytes, or None if error
        """
        if not self._is_git_repo():
            return None

        # Get relative path from repo root
        try:
            rel_path = file_path.relative_to(self.repo_root)
        except ValueError:
            # If file_path is already relative, use it as-is
            rel_path = file_path

        try:
            result = subprocess.run(
                ["git", "show", f"{commit}:{rel_path}"],
                cwd=self.repo_root,
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Git show failed: {result.stderr.decode()}")
                return None

            return result.stdout
        except Exception as e:
            logger.warning(f"Error getting file at commit: {e}")
            return None

    def file_matches_head(self, file_path: Path) -> bool:
        """
        Check if file in working directory matches HEAD.
        
        Args:
            file_path: Path to file (relative to repo root or absolute)
            
        Returns:
            True if file matches HEAD, False otherwise
        """
        if not self._is_git_repo():
            return False
        
        # Get relative path from repo root
        try:
            rel_path = file_path.relative_to(self.repo_root)
        except ValueError:
            # If file_path is already relative, use it as-is
            rel_path = file_path
        
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", "--quiet", "--", str(rel_path)],
                cwd=self.repo_root,
                capture_output=True,
                check=False,
            )
            # Exit code 0 means file matches HEAD
            return result.returncode == 0
        except Exception:
            return False

    def _is_git_repo(self) -> bool:
        """Check if repo_root is in a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False
