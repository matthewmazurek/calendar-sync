"""Git publishing operations for calendar sync."""

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class GitPublisher:
    """Handles git operations for publishing calendars."""

    def __init__(self, calendar_dir: Path, remote_url: Optional[str] = None):
        """
        Initialize GitPublisher.

        Args:
            calendar_dir: Directory containing calendars
            remote_url: Optional remote URL override for subscription URLs
        """
        self.calendar_dir = calendar_dir
        self.remote_url = remote_url

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
        except Exception as e:
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
            urls = self.generate_subscription_urls(calendar_name, filepath, format)
            if urls:
                print("Calendar subscription URLs:")
                for url in urls:
                    print(f"  {url}")
            else:
                print("Subscription URLs not available (could not determine remote)")

        except Exception as e:
            logger.warning(f"Git operation failed: {e}")
            print("Calendar saved but git operations failed", file=sys.stderr)

    def generate_subscription_urls(
        self, calendar_name: str, filepath: Path, format: str
    ) -> List[str]:
        """
        Generate GitHub raw URLs for calendar subscription.

        Args:
            calendar_name: Name of the calendar
            filepath: Path to the calendar file
            format: Calendar format (ics or json)

        Returns:
            List of subscription URLs (single URL for calendar.{ext})
        """
        remote_url = self.remote_url or self._get_remote_url()
        if not remote_url:
            return []

        # Parse remote URL to extract owner/repo
        owner, repo = self._parse_remote_url(remote_url)
        if not owner or not repo:
            return []

        # Get branch name
        branch = self._get_branch()

        # URL for calendar file - calendar_dir is the repo root, so path is relative to it
        # Get relative path from repo root
        repo_root = self._get_repo_root()
        if repo_root:
            calendar_file = self.calendar_dir / calendar_name / f"calendar.{format}"
            try:
                rel_path = calendar_file.relative_to(repo_root)
            except ValueError:
                # If path is not relative, use default structure
                rel_path = Path(calendar_name) / f"calendar.{format}"
        else:
            rel_path = Path(calendar_name) / f"calendar.{format}"

        calendar_url = (
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
            f"{rel_path.as_posix()}"
        )

        return [calendar_url]

    def _is_git_repo(self) -> bool:
        """Check if calendar_dir is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.calendar_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False

    def _get_remote_url(self) -> Optional[str]:
        """Get remote URL from git config."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.calendar_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.calendar_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                if branch:
                    return branch
        except Exception:
            pass
        # Default to master or main
        return "master"

    def _parse_remote_url(self, remote_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse remote URL to extract owner and repo.

        Supports:
        - git@github.com:owner/repo.git
        - https://github.com/owner/repo.git
        - https://github.com/owner/repo
        """
        # Remove .git suffix if present
        url = remote_url.rstrip(".git")

        # Handle SSH format: git@github.com:owner/repo
        ssh_match = re.match(r"git@github\.com:(.+?)/(.+?)$", url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)

        # Handle HTTPS format: https://github.com/owner/repo
        https_match = re.match(r"https?://github\.com/(.+?)/(.+?)$", url)
        if https_match:
            return https_match.group(1), https_match.group(2)

        return None, None

    def _stage_calendar_files(self, calendar_name: str) -> None:
        """
        Stage specific calendar files for commit.

        Args:
            calendar_name: Name of the calendar to stage
        """
        try:
            calendar_dir = self.calendar_dir / calendar_name
            repo_root = self._get_repo_root()
            if not repo_root:
                raise Exception("Could not determine git repo root")

            # Stage calendar file (could be .ics or .json)
            for ext in ["ics", "json"]:
                calendar_file = calendar_dir / f"calendar.{ext}"
                if calendar_file.exists():
                    # Get relative path from repo root
                    rel_path = calendar_file.relative_to(repo_root)
                    subprocess.run(
                        ["git", "add", str(rel_path)],
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                    )

            # Stage metadata file
            metadata_file = calendar_dir / "metadata.json"
            if metadata_file.exists():
                rel_path = metadata_file.relative_to(repo_root)
                subprocess.run(
                    ["git", "add", str(rel_path)],
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stage calendar files: {e}")

    def _commit_changes(self, message: str) -> None:
        """Commit staged changes."""
        try:
            repo_root = self._get_repo_root()
            if not repo_root:
                raise Exception("Could not determine git repo root")

            # Check if there are staged changes to commit
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=repo_root,
                capture_output=True,
                check=False,
            )
            # Exit code 0 means no staged changes
            if result.returncode == 0:
                logger.info("No calendar changes to commit")
                return

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to commit changes: {e}")

    def _push_changes(self) -> None:
        """Push committed changes to remote."""
        try:
            repo_root = self._get_repo_root()
            if not repo_root:
                raise Exception("Could not determine git repo root")

            subprocess.run(
                ["git", "push"],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to push changes: {e}")

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
            calendar_dir = self.calendar_dir / calendar_name

            # Get repo root for git commands
            repo_root = self._get_repo_root()
            if not repo_root:
                logger.warning("Could not determine git repo root")
                return

            # Stage deletion of calendar files (use git rm to track deletion)
            for ext in ["ics", "json"]:
                calendar_file = calendar_dir / f"calendar.{ext}"
                # Use git rm to stage deletion (works even if file doesn't exist in working dir)
                # --ignore-unmatch prevents error if file doesn't exist in git
                subprocess.run(
                    ["git", "rm", "--ignore-unmatch", str(calendar_file)],
                    cwd=repo_root,
                    check=False,
                    capture_output=True,
                )

            # Stage deletion of metadata file
            metadata_file = calendar_dir / "metadata.json"
            subprocess.run(
                ["git", "rm", "--ignore-unmatch", str(metadata_file)],
                cwd=repo_root,
                check=False,
                capture_output=True,
            )

            # Also remove the directory itself if it's tracked (recursive)
            subprocess.run(
                ["git", "rm", "-r", "--ignore-unmatch", str(calendar_dir)],
                cwd=repo_root,
                check=False,
                capture_output=True,
            )

            # Commit the deletion
            commit_message = f"Delete calendar: {calendar_name}"
            self._commit_changes(commit_message)
        except Exception as e:
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
        if not self.calendar_dir.is_absolute():
            # If relative, resolve it relative to repo root
            calendar_dir_abs = (repo_root / self.calendar_dir).resolve()
        else:
            calendar_dir_abs = self.calendar_dir.resolve()

        calendar_dir_full = calendar_dir_abs / calendar_name
        # Get relative path from repo root
        try:
            rel_calendar_path = calendar_dir_full.relative_to(repo_root.resolve())
        except ValueError:
            logger.error(
                f"Calendar path {calendar_dir_full} (absolute) is not within repo root {repo_root}"
            )
            logger.error(
                f"Calendar dir base: {self.calendar_dir}, resolved: {calendar_dir_abs}"
            )
            return False

        try:
            # Try git filter-repo first (recommended tool)
            result = subprocess.run(
                ["git", "filter-repo", "--version"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                # Use git filter-repo (recommended)
                logger.info(
                    f"Using git filter-repo to purge {calendar_name} from history"
                )
                subprocess.run(
                    [
                        "git",
                        "filter-repo",
                        "--path",
                        str(rel_calendar_path),
                        "--invert-paths",
                        "--force",
                    ],
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                )
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
                subprocess.run(
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
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                )

                # Clean up filter-branch backup refs
                subprocess.run(
                    ["git", "for-each-ref", "--format=%(refname)", "refs/original/"],
                    cwd=repo_root,
                    check=False,
                    capture_output=True,
                )

                return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to purge calendar from history: {e}")
            if e.stderr:
                logger.error(
                    f"Error output: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
                )
            return False
        except Exception as e:
            logger.error(f"Unexpected error purging from history: {e}")
            return False

    def _get_repo_root(self) -> Optional[Path]:
        """Get git repository root directory."""
        try:
            # Use calendar_dir as the base - it should be the repo root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.calendar_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return None
