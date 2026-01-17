"""Unified git service for calendar operations."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from app.exceptions import GitCommandError, GitError, GitRepositoryNotFoundError
from app.storage.git_client import GitClient, SubprocessGitClient

logger = logging.getLogger(__name__)


class GitService:
    """Unified service for git operations (versioning and publishing)."""

    def __init__(
        self,
        repo_root: Path,
        remote_url: str | None = None,
        git_client: GitClient | None = None,
        canonical_filename: str = "data.json",
        ics_export_filename: str = "calendar.ics",
        default_remote: str = "origin",
        default_branch: str = "main",
    ):
        """
        Initialize GitService.

        Args:
            repo_root: Root directory of git repository
            remote_url: Optional remote URL override for subscription URLs
            git_client: GitClient implementation (defaults to SubprocessGitClient)
            canonical_filename: Filename for canonical JSON storage
            ics_export_filename: Filename for ICS export
            default_remote: Default git remote name
            default_branch: Default git branch name (fallback)
        """
        self.repo_root = repo_root
        self.remote_url = remote_url
        self.git_client = git_client or SubprocessGitClient()
        self.canonical_filename = canonical_filename
        self.ics_export_filename = ics_export_filename
        self.default_remote = default_remote
        self.default_branch = default_branch

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

    def _get_repo_root(self) -> Path | None:
        """Get git repository root directory."""
        result = self.git_client.run_command(
            ["git", "rev-parse", "--show-toplevel"], self.repo_root
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None

    def _get_remote_url(self, remote_name: str | None = None) -> str | None:
        """Get remote URL from git config."""
        remote = remote_name or self.default_remote
        result = self.git_client.run_command(
            ["git", "remote", "get-url", remote], self.repo_root
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
        return self.default_branch

    # Version operations (from GitVersionService)

    def get_file_versions(self, file_path: Path) -> list[tuple[str, datetime, str]]:
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
                    # Include timezone offset for correct UTC conversion
                    commit_date = datetime.strptime(
                        date_str,
                        "%Y-%m-%d %H:%M:%S %z",
                    )
                    versions.append((commit_hash, commit_date, message))
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse git log line: {line}, error: {e}")
                continue

        return versions

    def get_file_at_commit(self, file_path: Path, commit: str) -> bytes | None:
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

        # Use binary mode to preserve exact bytes for accurate comparison
        result = self.git_client.run_command_binary(
            ["git", "show", f"{commit}:{rel_path}"], self.repo_root
        )

        if result.returncode != 0:
            logger.warning(f"Git show failed: {result.stderr}")
            return None

        return result.stdout

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

    def get_current_commit_hash(self, file_path: Path) -> str | None:
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

    def get_remote_url(self, remote_name: str | None = None) -> str | None:
        """
        Get the URL of a git remote.

        Args:
            remote_name: Name of the remote (defaults to configured default_remote)

        Returns:
            Remote URL if found, None otherwise
        """
        if not self._is_git_repo():
            return None

        remote = remote_name or self.default_remote
        result = self.git_client.run_command(
            ["git", "remote", "get-url", remote], self.repo_root
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    # Publishing operations (from GitPublisher)

    def commit_calendar_locally(
        self, calendar_name: str, message: str | None = None
    ) -> None:
        """
        Commit calendar changes locally (stage and commit, but don't push).

        Args:
            calendar_name: Name of the calendar
            message: Optional custom commit message
        """
        if not self._is_git_repo():
            logger.debug("Not in a git repository, skipping local commit")
            return

        try:
            # Stage specific calendar files (force-add to bypass .gitignore)
            self._stage_calendar_files(calendar_name)

            # Commit changes
            commit_message = message or f"Update calendar: {calendar_name}"
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
            filepath: Path to the calendar file (ICS export)
            format: Deprecated, ignored (kept for backwards compatibility)
        """

        if not self._is_git_repo():
            logger.warning("Not in a git repository, skipping git operations")
            return

        try:
            # Commit locally first (if not already committed)
            self.commit_calendar_locally(calendar_name)

            # Push to remote
            self._push_changes()

            # Generate and display subscription URLs (always ICS)
            from app.storage.subscription_url_generator import SubscriptionUrlGenerator

            url_generator = SubscriptionUrlGenerator(self.repo_root, self.remote_url)
            urls = url_generator.generate_subscription_urls(
                calendar_name, filepath, "ics"
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
            calendar_file = calendar_dir / self.ics_export_filename
            # Use git rm to stage deletion (works even if file doesn't exist in working dir)
            # --ignore-unmatch prevents error if file doesn't exist in git
            self.git_client.run_command(
                ["git", "rm", "--ignore-unmatch", str(calendar_file)],
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

    def commit_rename(self, old_name: str, new_name: str) -> None:
        """
        Commit calendar rename to git.

        Stages the deletion of old files and addition of new files,
        then commits. Git will recognize this as a rename if content is similar.

        Args:
            old_name: Old calendar name
            new_name: New calendar name
        """
        if not self._is_git_repo():
            logger.debug("Not in a git repository, skipping rename commit")
            return

        try:
            repo_root = self._get_repo_root()
            if not repo_root:
                logger.warning("Could not determine git repo root")
                return

            old_dir = self.repo_root / old_name
            new_dir = self.repo_root / new_name

            # Stage deletion of old calendar directory
            self.git_client.run_command(
                ["git", "rm", "-r", "--ignore-unmatch", str(old_dir)],
                repo_root,
            )

            # Stage addition of new calendar directory
            if new_dir.exists():
                rel_new_dir = new_dir.relative_to(repo_root)
                self.git_client.run_command(
                    ["git", "add", str(rel_new_dir)],
                    repo_root,
                )

            # Commit the rename
            commit_message = f"Rename calendar: {old_name} → {new_name}"
            self._commit_changes(commit_message)
        except (GitError, GitCommandError) as e:
            logger.warning(f"Failed to commit rename: {e}")

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
        Stage all calendar files for commit.

        Stages the entire calendar directory, which handles:
        - New files (data.json, config.json)
        - Modified files (calendar.ics)
        - Deleted files (old filenames)

        Args:
            calendar_name: Name of the calendar to stage
        """
        calendar_dir = (self.repo_root / calendar_name).resolve()
        repo_root = self._get_repo_root()
        if not repo_root:
            raise GitRepositoryNotFoundError("Could not determine git repo root")
        repo_root = repo_root.resolve()

        # Stage entire calendar directory (handles adds, modifications, and deletions)
        rel_dir = calendar_dir.relative_to(repo_root)
        result = self.git_client.run_command(
            ["git", "add", "-A", str(rel_dir)], repo_root
        )
        if result.returncode != 0:
            raise GitCommandError(
                f"Failed to stage calendar directory: {result.stderr}"
            )

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
            remote_url = self.get_remote_url()
            if not remote_url:
                raise GitCommandError(
                    f"No remote '{self.default_remote}' configured. "
                    "Cannot set upstream branch."
                )

            # Push with --set-upstream to configure tracking
            result = self.git_client.run_command(
                ["git", "push", "--set-upstream", self.default_remote, branch],
                repo_root,
            )
        else:
            # Branch has upstream, use regular push
            result = self.git_client.run_command(["git", "push"], repo_root)

        if result.returncode != 0:
            raise GitCommandError(f"Failed to push changes: {result.stderr}")

        logger.info("Pushed changes to remote.")
