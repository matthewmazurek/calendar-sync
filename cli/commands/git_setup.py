"""Git setup command for initializing calendar repository."""

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from app.config import CalendarConfig
from app.storage.git_service import GitService

logger = logging.getLogger(__name__)


def git_setup_command(delete: bool = False) -> None:
    """
    Initialize git repository in calendar directory with seamless URL generation,
    or delete local and remote repository if --delete is specified.
    """
    config = CalendarConfig.from_env()
    calendar_dir = config.calendar_dir.resolve()

    # Handle delete mode
    if delete:
        delete_git_repository(calendar_dir)
        return

    # Check if git repo already exists
    if (calendar_dir / ".git").exists():
        # Check if remote is configured
        git_service = GitService(calendar_dir)
        remote_url = git_service.get_remote_url()
        if remote_url:
            print(f"Git repository already exists in {calendar_dir}")
            print(f"Remote URL: {remote_url}")
            return

        print(f"Git repository already exists in {calendar_dir}")
        print("No remote configured. Setting up remote...")
    else:
        # Initialize git repo
        print(f"Initializing git repository in {calendar_dir}...")
        calendar_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "init"],
                cwd=calendar_dir,
                check=True,
                capture_output=True,
            )
            print("Git repository initialized.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize git repository: {e}")
            sys.exit(1)

    # Seamless URL generation (tiered approach)
    remote_url = None

    # Tier 1: Try GitHub CLI first (most seamless)
    if check_gh_cli_available():
        username = get_github_username_from_gh()
        if username:
            default_repo_name = "calendar-sync-calendars"
            suggested_repo = f"{username}/{default_repo_name}"
            print(f"\nGitHub CLI detected.")
            response = input(f"Repository name [{default_repo_name}]: ").strip()

            if response:
                repo_name = response
            else:
                repo_name = default_repo_name

            full_repo_name = f"{username}/{repo_name}"
            print(f"Creating repository '{full_repo_name}'...")
            if create_repo_with_gh(username, repo_name, calendar_dir):
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                print(f"Repository created and remote configured: {remote_url}")

    # Tier 2: Manual fallback
    if not remote_url:
        print("\nCould not auto-detect GitHub settings.")
        manual_url = input(
            "Enter GitHub repository URL (or press Enter to skip): "
        ).strip()
        if manual_url:
            remote_url = manual_url

    # Set up remote if we have a URL
    if remote_url:
        try:
            # Remove existing remote if it exists
            subprocess.run(
                ["git", "remote", "remove", "origin"],
                cwd=calendar_dir,
                capture_output=True,
                check=False,
            )
            # Add new remote
            subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                cwd=calendar_dir,
                check=True,
                capture_output=True,
            )
            print(f"Remote 'origin' configured: {remote_url}")

            # Save to .env file
            write_to_env_file("CALENDAR_GIT_REMOTE_URL", remote_url)
            print("Remote URL saved to .env file")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to set remote: {e}")
            print("Warning: Could not configure remote. You can set it manually later.")

    # Create initial commit if calendar files exist
    if calendar_dir.exists():
        # Check if there are any files to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=calendar_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            try:
                subprocess.run(
                    ["git", "add", "."],
                    cwd=calendar_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", "Initial calendar repository"],
                    cwd=calendar_dir,
                    check=True,
                    capture_output=True,
                )
                print("Initial commit created.")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to create initial commit: {e}")

    print("\nGit setup complete!")
    if remote_url:
        print(f"Remote repository: {remote_url}")
        print(
            "You can now use 'calendar-sync publish' to push calendars to the remote."
        )
    else:
        print("No remote configured. You can set one up later with:")
        print("  git remote add origin <repository-url>")


def check_gh_cli_available() -> bool:
    """Check if GitHub CLI is installed and authenticated."""
    try:
        # Check if gh is installed
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False

        # Check if authenticated
        auth_result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        return auth_result.returncode == 0
    except Exception:
        return False


def get_github_username_from_gh() -> Optional[str]:
    """Get GitHub username from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "api", "user"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse JSON to get login
        import json

        user_data = json.loads(result.stdout)
        return user_data.get("login")
    except Exception:
        return None


def create_repo_with_gh(username: str, repo_name: str, calendar_dir: Path) -> bool:
    """Create GitHub repository using gh CLI."""
    try:
        full_repo_name = f"{username}/{repo_name}"
        result = subprocess.run(
            [
                "gh",
                "repo",
                "create",
                full_repo_name,
                "--private",
                "--source",
                str(calendar_dir),
                "--remote",
                "origin",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def delete_git_repository(calendar_dir: Path) -> None:
    """Delete local and remote git repository with confirmation."""
    # Check if git repo exists
    git_dir = calendar_dir / ".git"
    if not git_dir.exists():
        print(f"No git repository found in {calendar_dir}")
        return

    # Get remote URL if it exists
    git_service = GitService(calendar_dir)
    remote_url = git_service.get_remote_url()

    # Show what will be deleted
    print("This will delete:")
    print(f"  - Local git repository: {git_dir}")
    if remote_url:
        print(f"  - Remote repository: {remote_url}")
        # Try to extract repo name for deletion
        repo_name = extract_repo_name_from_url(remote_url)
        if repo_name:
            print(f"    (Repository: {repo_name})")
    else:
        print("  - No remote repository configured")

    # Confirmation prompt
    print()
    response = input(
        "Are you sure you want to delete the git repository? [yes/no]: "
    ).strip()
    if response.lower() not in ["yes", "y"]:
        print("Deletion cancelled.")
        return

    # Delete remote repository if it exists
    if remote_url:
        repo_name = extract_repo_name_from_url(remote_url)
        if repo_name and check_gh_cli_available():
            print(f"\nDeleting remote repository '{repo_name}'...")
            success, error_msg = delete_remote_repo(repo_name)
            if success:
                print(f"Remote repository '{repo_name}' deleted successfully.")
            else:
                print(f"Warning: Could not delete remote repository '{repo_name}'.")
                if error_msg:
                    # Check for missing scope error
                    if (
                        "delete_repo" in error_msg.lower()
                        or "admin rights" in error_msg.lower()
                    ):
                        print(
                            "\nGitHub CLI needs the 'delete_repo' scope to delete repositories."
                        )
                        print("To fix this, run:")
                        print("  gh auth refresh -h github.com -s delete_repo")
                        print("\nThen try the deletion again.")
                    else:
                        print(f"Error: {error_msg}")
                print("\nYou can also delete it manually on GitHub if needed.")
        else:
            print(f"\nRemote repository exists at {remote_url}")
            print("Please delete it manually on GitHub if needed.")

    # Delete local .git directory
    print(f"\nDeleting local git repository...")
    try:
        shutil.rmtree(git_dir)
        print(f"Local git repository deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to delete local git repository: {e}")
        print(f"Error: Could not delete local git repository: {e}")
        sys.exit(1)

    # Remove remote URL from .env file if it exists
    if remote_url:
        remove_from_env_file("CALENDAR_GIT_REMOTE_URL")
        print("Remote URL removed from .env file")

    print("\nGit repository deletion complete!")


def extract_repo_name_from_url(remote_url: str) -> Optional[str]:
    """Extract repository name (owner/repo) from GitHub URL."""
    # Remove .git suffix if present
    url = remote_url.rstrip(".git")

    # Handle SSH format: git@github.com:owner/repo
    ssh_match = re.match(r"git@github\.com:(.+?)/(.+?)$", url)
    if ssh_match:
        return f"{ssh_match.group(1)}/{ssh_match.group(2)}"

    # Handle HTTPS format: https://github.com/owner/repo
    https_match = re.match(r"https?://github\.com/(.+?)/(.+?)$", url)
    if https_match:
        return f"{https_match.group(1)}/{https_match.group(2)}"

    return None


def delete_remote_repo(full_repo_name: str) -> tuple[bool, str]:
    """
    Delete a GitHub repository using gh CLI.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "delete", full_repo_name, "--yes"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, ""
        else:
            error_msg = (
                result.stderr.strip() or result.stdout.strip() or "Unknown error"
            )
            return False, error_msg
    except Exception as e:
        return False, str(e)


def remove_from_env_file(key: str) -> None:
    """Remove a key from .env file."""
    env_file = Path(".env")
    if not env_file.exists():
        return

    env_content = env_file.read_text()
    lines = env_content.splitlines()
    updated_lines = [line for line in lines if not line.startswith(f"{key}=")]

    if len(updated_lines) < len(lines):
        env_file.write_text("\n".join(updated_lines) + "\n")


def write_to_env_file(key: str, value: str) -> None:
    """Append or update .env file with key=value."""
    env_file = Path(".env")
    env_content = ""

    # Read existing .env if it exists
    if env_file.exists():
        env_content = env_file.read_text()

    # Check if key already exists
    lines = env_content.splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break

    if not updated:
        lines.append(f"{key}={value}")

    # Write back to file
    env_file.write_text("\n".join(lines) + "\n")
