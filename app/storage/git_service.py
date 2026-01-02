"""Unified git service for calendar operations."""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from app.constants import CALENDAR_EXTENSIONS, METADATA_FILENAME
from app.exceptions import GitCommandError, GitError, GitRepositoryNotFoundError
from app.storage.git_client import GitClient, SubprocessGitClient

logger = logging.getLogger(__name__)


class GitService:
    """Unified service for git operations (versioning and publishing)."""

    def __init__(
        self,
        repo_root: Path,
        remote_url: Optional[str] = None,
        git_client: Optional[GitClient] = None,
    ):
        """
        Initialize GitService.

        Args:
            repo_root: Root directory of git repository
            remote_url: Optional remote URL override for subscription URLs
            git_client: GitClient implementation (defaults to SubprocessGitClient)
        """
        self.repo_root = repo_root
        self.remote_url = remote_url
        self.git_client = git_client or SubprocessGitClient()

    def _get_relative_path(self, path: Path) -> Path:
        """
        Get relative path from repo root.

        Args:
            path: Path to file or directory (relative to repo root or absolute)

        Returns:
            Relative path from repo root
        """
        try:
            return path.relative_to(self.repo_root)
        except ValueError:
            # If path is already relative, use it as-is
            return path

    def _is_git_repo(self) -> bool:
        """Check if repo_root is in a git repository."""
        result = self.git_client.run_command(
            ["git", "rev-parse", "--is-inside-work-tree"], self.repo_root
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _get_repo_root(self) -> Optional[Path]:
        """Get git repository root directory."""
        result = self.git_client.run_command(
            ["git", "rev-parse", "--show-toplevel"], self.repo_root
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None

    def _get_remote_url(self, remote_name: str = "origin") -> Optional[str]:
        """Get remote URL from git config."""
        result = self.git_client.run_command(
            ["git", "remote", "get-url", remote_name], self.repo_root
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def _get_branch(self) -> str:
        """Get current branch name."""
        result = self.git_client.run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repo_root
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch:
                return branch
        # Default to master or main
        return "master"

    # Version operations (from GitVersionService)

    def get_file_versions(self, file_path: Path) -> List[Tuple[str, datetime, str]]:
        """
        Get git log for a specific file.

        Args:
            file_path: Path to file (relative to repo root or absolute)

        Returns:
            List of (commit_hash, commit_date, commit_message) tuples
        """
        if not self._is_git_repo():
            return []

        rel_path = self._get_relative_path(file_path)

        result = self.git_client.run_command(
            ["git", "log", "--format=%H|%ai|%s", "--", str(rel_path)],
            self.repo_root,
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

    def get_file_at_commit(self, file_path: Path, commit: str) -> Optional[bytes]:
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

        rel_path = self._get_relative_path(file_path)

        result = self.git_client.run_command(
            ["git", "show", f"{commit}:{rel_path}"], self.repo_root
        )

        if result.returncode != 0:
            logger.warning(f"Git show failed: {result.stderr}")
            return None

        return result.stdout.encode("utf-8")

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

        rel_path = self._get_relative_path(file_path)

        result = self.git_client.run_command(
            ["git", "checkout", commit, "--", str(rel_path)], self.repo_root
        )

        if result.returncode != 0:
            logger.error(f"Git checkout failed: {result.stderr}")
            return False

        return True

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

        rel_path = self._get_relative_path(dir_path)

        result = self.git_client.run_command(
            ["git", "checkout", commit, "--", str(rel_path)], self.repo_root
        )

        if result.returncode != 0:
            logger.error(f"Git checkout failed: {result.stderr}")
            return False

        return True

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

        rel_path = self._get_relative_path(file_path)

        result = self.git_client.run_command(
            ["git", "diff", "HEAD", "--quiet", "--", str(rel_path)], self.repo_root
        )
        # Exit code 0 means file matches HEAD
        return result.returncode == 0

    def get_current_commit_hash(self, file_path: Path) -> Optional[str]:
        """
        Get the commit hash that the current working file matches.

        If the file has uncommitted changes, returns None.
        If the file matches a commit, returns that commit hash.
        When file matches HEAD, returns the latest commit that modified the file
        (not necessarily HEAD, since HEAD may not have modified this file).

        Args:
            file_path: Path to file (relative to repo root or absolute)

        Returns:
            Commit hash if file matches a commit, None if uncommitted changes or not in git
        """
        if not self._is_git_repo() or not file_path.exists():
            return None

        # Fast path: check if file matches HEAD
        if self.file_matches_head(file_path):
            # Get versions list - first version is the latest commit that modified this file
            versions = self.get_file_versions(file_path)
            if versions:
                # Return the latest commit that modified this file, not HEAD
                # (HEAD may not have modified this file)
                return versions[0][0]
            return None

        # File doesn't match HEAD - check if it matches any commit
        # by comparing content
        try:
            current_content = file_path.read_bytes()
            versions = self.get_file_versions(file_path)

            # Check each version to see if content matches
            for commit_hash, _, _ in versions:
                commit_content = self.get_file_at_commit(file_path, commit_hash)
                if commit_content and commit_content == current_content:
                    return commit_hash
        except (OSError, ValueError):
            pass

        # File has uncommitted changes (doesn't match any commit)
        return None

    def get_remote_url(self, remote_name: str = "origin") -> Optional[str]:
        """
        Get the URL of a git remote.

        Args:
            remote_name: Name of the remote (default: "origin")

        Returns:
            Remote URL if found, None otherwise
        """
        if not self._is_git_repo():
            return None

        result = self.git_client.run_command(
            ["git", "remote", "get-url", remote_name], self.repo_root
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    # Publishing operations (from GitPublisher)

    def commit_calendar_locally(self, calendar_name: str) -> None:
        """
        Commit calendar changes locally (stage and commit, but don't push).

        Args:
            calendar_name: Name of the calendar
        """
        if not self._is_git_repo():
            logger.debug("Not in a git repository, skipping local commit")
            return

        try:
            # Stage specific calendar files (force-add to bypass .gitignore)
            self._stage_calendar_files(calendar_name)

            # Commit changes
            commit_message = f"Update calendar: {calendar_name}"
            self._commit_changes(commit_message)
        except (GitError, GitCommandError) as e:
            logger.warning(f"Local git commit failed: {e}")
            logger.debug("Calendar saved but local commit failed")

    def publish_calendar(
        self, calendar_name: str, filepath: Path, format: str = "ics"
    ) -> None:
        """
        Publish a calendar to git (stage, commit, push).

        Args:
            calendar_name: Name of the calendar
            filepath: Path to the calendar file that was saved
            format: Calendar format (ics or json)
        """

        if not self._is_git_repo():
            logger.warning("Not in a git repository, skipping git operations")
            return

        try:
            # Commit locally first (if not already committed)
            self.commit_calendar_locally(calendar_name)

            # Push to remote
            self._push_changes()

            # Generate and display subscription URLs
            from app.storage.subscription_url_generator import SubscriptionUrlGenerator

            url_generator = SubscriptionUrlGenerator(self.repo_root, self.remote_url)
            urls = url_generator.generate_subscription_urls(
                calendar_name, filepath, format
            )
            if urls:
                print("Calendar subscription URLs:")
                for url in urls:
                    print(f"  {url}")
            else:
                print("Subscription URLs not available (could not determine remote)")

        except (GitError, GitCommandError) as e:
            logger.warning(f"Git operation failed: {e}")
            print("Calendar saved but git operations failed", file=sys.stderr)

    def commit_deletion(self, calendar_name: str) -> None:
        """
        Commit calendar deletion to git.

        Args:
            calendar_name: Name of the calendar to delete
        """
        if not self._is_git_repo():
            logger.debug("Not in a git repository, skipping deletion commit")
            return

        try:
            calendar_dir = self.repo_root / calendar_name

            # Get repo root for git commands
            repo_root = self._get_repo_root()
            if not repo_root:
                logger.warning("Could not determine git repo root")
                return

            # Stage deletion of calendar files (use git rm to track deletion)
            for ext in CALENDAR_EXTENSIONS:
                calendar_file = calendar_dir / f"calendar.{ext}"
                # Use git rm to stage deletion (works even if file doesn't exist in working dir)
                # --ignore-unmatch prevents error if file doesn't exist in git
                self.git_client.run_command(
                    ["git", "rm", "--ignore-unmatch", str(calendar_file)],
                    repo_root,
                )

            # Stage deletion of metadata file
            metadata_file = calendar_dir / METADATA_FILENAME
            self.git_client.run_command(
                ["git", "rm", "--ignore-unmatch", str(metadata_file)],
                repo_root,
            )

            # Also remove the directory itself if it's tracked (recursive)
            self.git_client.run_command(
                ["git", "rm", "-r", "--ignore-unmatch", str(calendar_dir)],
                repo_root,
            )

            # Commit the deletion
            commit_message = f"Delete calendar: {calendar_name}"
            self._commit_changes(commit_message)
        except (GitError, GitCommandError) as e:
            logger.warning(f"Failed to commit deletion: {e}")

    def purge_from_history(self, calendar_name: str) -> bool:
        """
        Remove calendar from git history entirely (hard delete).

        This rewrites git history and is destructive. All commits that touched
        this calendar will be rewritten.

        Args:
            calendar_name: Name of the calendar to purge

        Returns:
            True if successful, False otherwise
        """
        if not self._is_git_repo():
            logger.warning("Not in a git repository")
            return False

        repo_root = self._get_repo_root()
        if not repo_root:
            logger.warning("Could not determine git repo root")
            return False

        # Resolve calendar_dir to absolute path (it might be relative)
        calendar_dir_abs = self.repo_root.resolve()

        calendar_dir_full = calendar_dir_abs / calendar_name
        # Get relative path from repo root
        try:
            rel_calendar_path = calendar_dir_full.relative_to(repo_root.resolve())
        except ValueError:
            logger.error(
                f"Calendar path {calendar_dir_full} (absolute) is not within repo root {repo_root}"
            )
            logger.error(
                f"Calendar dir base: {self.repo_root}, resolved: {calendar_dir_abs}"
            )
            return False

        try:
            # Try git filter-repo first (recommended tool)
            result = self.git_client.run_command(
                ["git", "filter-repo", "--version"], repo_root
            )

            if result.returncode == 0:
                # Use git filter-repo (recommended)
                logger.info(
                    f"Using git filter-repo to purge {calendar_name} from history"
                )
                result = self.git_client.run_command(
                    [
                        "git",
                        "filter-repo",
                        "--path",
                        str(rel_calendar_path),
                        "--invert-paths",
                        "--force",
                    ],
                    repo_root,
                )
                if result.returncode != 0:
                    raise GitCommandError(f"git filter-repo failed: {result.stderr}")
                return True
            else:
                # Fall back to git filter-branch (deprecated but available)
                logger.warning(
                    "git filter-repo not found, falling back to git filter-branch"
                )
                logger.warning(
                    "Consider installing git filter-repo: pip install git-filter-repo"
                )

                # Use git filter-branch
                result = self.git_client.run_command(
                    [
                        "git",
                        "filter-branch",
                        "--force",
                        "--index-filter",
                        f'git rm -rf --cached --ignore-unmatch "{rel_calendar_path}"',
                        "--prune-empty",
                        "--tag-name-filter",
                        "cat",
                        "--",
                        "--all",
                    ],
                    repo_root,
                )
                if result.returncode != 0:
                    raise GitCommandError(f"git filter-branch failed: {result.stderr}")

                # Clean up filter-branch backup refs
                self.git_client.run_command(
                    ["git", "for-each-ref", "--format=%(refname)", "refs/original/"],
                    repo_root,
                )

                return True
        except GitCommandError as e:
            logger.error(f"Failed to purge calendar from history: {e}")
            return False
        except (GitError, OSError) as e:
            logger.error(f"Unexpected error purging from history: {e}")
            return False

    def _stage_calendar_files(self, calendar_name: str) -> None:
        """
        Stage specific calendar files for commit.

        Args:
            calendar_name: Name of the calendar to stage
        """
        calendar_dir = (self.repo_root / calendar_name).resolve()
        repo_root = self._get_repo_root()
        if not repo_root:
            raise GitRepositoryNotFoundError("Could not determine git repo root")
        repo_root = repo_root.resolve()

        # Stage calendar file (could be .ics or .json)
        for ext in CALENDAR_EXTENSIONS:
            calendar_file = calendar_dir / f"calendar.{ext}"
            if calendar_file.exists():
                # Get relative path from repo root
                rel_path = calendar_file.relative_to(repo_root)
                result = self.git_client.run_command(
                    ["git", "add", str(rel_path)], repo_root
                )
                if result.returncode != 0:
                    raise GitCommandError(
                        f"Failed to stage calendar file: {result.stderr}"
                    )

        # Stage metadata file
        metadata_file = calendar_dir / METADATA_FILENAME
        if metadata_file.exists():
            rel_path = metadata_file.relative_to(repo_root)
            result = self.git_client.run_command(
                ["git", "add", str(rel_path)], repo_root
            )
            if result.returncode != 0:
                raise GitCommandError(f"Failed to stage metadata file: {result.stderr}")

    def _commit_changes(self, message: str) -> None:
        """Commit staged changes."""
        repo_root = self._get_repo_root()
        if not repo_root:
            raise GitRepositoryNotFoundError("Could not determine git repo root")

        # Check if there are staged changes to commit
        result = self.git_client.run_command(
            ["git", "diff", "--cached", "--quiet"], repo_root
        )
        # Exit code 0 means no staged changes
        if result.returncode == 0:
            logger.info("No calendar changes to commit")
            return

        result = self.git_client.run_command(
            ["git", "commit", "-m", message], repo_root
        )
        if result.returncode != 0:
            raise GitCommandError(f"Failed to commit changes: {result.stderr}")

    def _has_upstream_branch(self, branch: str) -> bool:
        """
        Check if a branch has an upstream tracking branch configured.

        Args:
            branch: Branch name to check

        Returns:
            True if branch has upstream, False otherwise
        """
        repo_root = self._get_repo_root()
        if not repo_root:
            return False

        # Check if upstream is configured using git rev-parse
        result = self.git_client.run_command(
            ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{u}}"], repo_root
        )
        return result.returncode == 0

    def _push_changes(self) -> None:
        """Push committed changes to remote."""
        repo_root = self._get_repo_root()
        if not repo_root:
            raise GitRepositoryNotFoundError("Could not determine git repo root")

        # Get current branch
        branch = self._get_branch()

        # Check if branch has upstream tracking
        if not self._has_upstream_branch(branch):
            # Check if remote exists
            remote_url = self.get_remote_url("origin")
            if not remote_url:
                raise GitCommandError(
                    "No remote 'origin' configured. Cannot set upstream branch."
                )

            # Push with --set-upstream to configure tracking
            result = self.git_client.run_command(
                ["git", "push", "--set-upstream", "origin", branch], repo_root
            )
        else:
            # Branch has upstream, use regular push
            result = self.git_client.run_command(["git", "push"], repo_root)

        if result.returncode != 0:
            raise GitCommandError(f"Failed to push changes: {result.stderr}")

        logger.info(f"Pushed changes to remote.")
