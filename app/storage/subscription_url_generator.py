"""Subscription URL generator for calendar files."""

import logging
import re
from pathlib import Path

from app.storage.git_client import GitClient, SubprocessGitClient

logger = logging.getLogger(__name__)


class SubscriptionUrlGenerator:
    """Generates subscription URLs for calendar files."""

    def __init__(
        self,
        repo_root: Path,
        remote_url: str | None = None,
        git_client: GitClient | None = None,
    ):
        """
        Initialize SubscriptionUrlGenerator.

        Args:
            repo_root: Root directory of git repository
            remote_url: Optional remote URL override
            git_client: GitClient implementation (defaults to SubprocessGitClient)
        """
        self.repo_root = repo_root
        self.remote_url = remote_url
        self.git_client = git_client or SubprocessGitClient()

    def _get_remote_url(self) -> str | None:
        """Get remote URL from git config."""
        if self.remote_url:
            return self.remote_url

        result = self.git_client.run_command(
            ["git", "remote", "get-url", "origin"], self.repo_root
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

    def _parse_remote_url(self, remote_url: str) -> tuple[str | None, str | None]:
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

    def _get_repo_root(self) -> Path | None:
        """Get git repository root directory."""
        result = self.git_client.run_command(
            ["git", "rev-parse", "--show-toplevel"], self.repo_root
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None

    def generate_subscription_urls(
        self, calendar_name: str, filepath: Path, format: str
    ) -> list[str]:
        """
        Generate GitHub raw URLs for calendar subscription.

        Args:
            calendar_name: Name of the calendar
            filepath: Path to the calendar file
            format: Calendar format (ics or json)

        Returns:
            List of subscription URLs (single URL for calendar.{ext})
        """
        remote_url = self._get_remote_url()
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
            calendar_file = self.repo_root / calendar_name / f"calendar.{format}"
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
