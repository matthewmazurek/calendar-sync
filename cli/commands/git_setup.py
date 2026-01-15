"""Git setup command for initializing calendar repository."""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import typer
from typing_extensions import Annotated

from app.storage.git_service import GitService
from cli.context import CLIContext, get_context

logger = logging.getLogger(__name__)


def git_setup(
    delete: Annotated[
        bool,
        typer.Option(
            "--delete",
            help="Delete local and remote git repository (with confirmation)",
        ),
    ] = False,
) -> None:
    """Initialize git repository in calendar directory with seamless URL generation,
    or delete local and remote repository if --delete is specified.
    """
    ctx = get_context()
    config = ctx.config
    calendar_dir = config.calendar_dir.resolve()

    # Handle delete mode
    if delete:
        _delete_git_repository(calendar_dir)
        return

    # Check if git repo already exists
    if (calendar_dir / ".git").exists():
        # Check if remote is configured
        git_service = GitService(calendar_dir)
        remote_url = git_service.get_remote_url()
        if remote_url:
            typer.echo(f"Git repository already exists in {calendar_dir}")
            typer.echo(f"Remote URL: {remote_url}")
            return

        typer.echo(f"Git repository already exists in {calendar_dir}")
        typer.echo("No remote configured. Setting up remote...")
    else:
        # Initialize git repo
        typer.echo(f"Initializing git repository in {calendar_dir}...")
        calendar_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "init"],
                cwd=calendar_dir,
                check=True,
                capture_output=True,
            )
            typer.echo("Git repository initialized.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize git repository: {e}")
            raise typer.Exit(1)

    # Seamless URL generation (tiered approach)
    remote_url = None

    # Tier 1: Try GitHub CLI first (most seamless)
    if _check_gh_cli_available():
        username = _get_github_username_from_gh()
        if username:
            default_repo_name = "calendar-sync-calendars"
            typer.echo(f"\nGitHub CLI detected.")
            response = typer.prompt(f"Repository name", default=default_repo_name)

            repo_name = response if response else default_repo_name

            full_repo_name = f"{username}/{repo_name}"
            typer.echo(f"Creating repository '{full_repo_name}'...")
            if _create_repo_with_gh(username, repo_name, calendar_dir):
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                typer.echo(f"Repository created and remote configured: {remote_url}")

    # Tier 2: Manual fallback
    if not remote_url:
        typer.echo("\nCould not auto-detect GitHub settings.")
        manual_url = typer.prompt(
            "Enter GitHub repository URL (or press Enter to skip)",
            default="",
        )
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
            typer.echo(f"Remote 'origin' configured: {remote_url}")

            # Save to .env file
            _write_to_env_file("CALENDAR_GIT_REMOTE_URL", remote_url)
            typer.echo("Remote URL saved to .env file")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to set remote: {e}")
            typer.echo(
                "Warning: Could not configure remote. You can set it manually later."
            )

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
                typer.echo("Initial commit created.")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to create initial commit: {e}")

    typer.echo("\nGit setup complete!")
    if remote_url:
        typer.echo(f"Remote repository: {remote_url}")
        typer.echo(
            "You can now use 'calendar-sync publish' to push calendars to the remote."
        )
    else:
        typer.echo("No remote configured. You can set one up later with:")
        typer.echo("  git remote add origin <repository-url>")


def _check_gh_cli_available() -> bool:
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


def _get_github_username_from_gh() -> str | None:
    """Get GitHub username from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "api", "user"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse JSON to get login
        user_data = json.loads(result.stdout)
        return user_data.get("login")
    except Exception:
        return None


def _create_repo_with_gh(username: str, repo_name: str, calendar_dir: Path) -> bool:
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


def _delete_git_repository(calendar_dir: Path) -> None:
    """Delete local and remote git repository with confirmation."""
    # Check if git repo exists
    git_dir = calendar_dir / ".git"
    if not git_dir.exists():
        typer.echo(f"No git repository found in {calendar_dir}")
        return

    # Get remote URL if it exists
    git_service = GitService(calendar_dir)
    remote_url = git_service.get_remote_url()

    # Show what will be deleted
    typer.echo("This will delete:")
    typer.echo(f"  - Local git repository: {git_dir}")
    if remote_url:
        typer.echo(f"  - Remote repository: {remote_url}")
        # Try to extract repo name for deletion
        repo_name = _extract_repo_name_from_url(remote_url)
        if repo_name:
            typer.echo(f"    (Repository: {repo_name})")
    else:
        typer.echo("  - No remote repository configured")

    # Confirmation prompt
    typer.echo()
    if not typer.confirm("Are you sure you want to delete the git repository?"):
        typer.echo("Deletion cancelled.")
        return

    # Delete remote repository if it exists
    if remote_url:
        repo_name = _extract_repo_name_from_url(remote_url)
        if repo_name and _check_gh_cli_available():
            typer.echo(f"\nDeleting remote repository '{repo_name}'...")
            success, error_msg = _delete_remote_repo(repo_name)
            if success:
                typer.echo(f"Remote repository '{repo_name}' deleted successfully.")
            else:
                typer.echo(
                    f"Warning: Could not delete remote repository '{repo_name}'."
                )
                if error_msg:
                    # Check for missing scope error
                    if (
                        "delete_repo" in error_msg.lower()
                        or "admin rights" in error_msg.lower()
                    ):
                        typer.echo(
                            "\nGitHub CLI needs the 'delete_repo' scope to delete repositories."
                        )
                        typer.echo("To fix this, run:")
                        typer.echo("  gh auth refresh -h github.com -s delete_repo")
                        typer.echo("\nThen try the deletion again.")
                    else:
                        typer.echo(f"Error: {error_msg}")
                typer.echo("\nYou can also delete it manually on GitHub if needed.")
        else:
            typer.echo(f"\nRemote repository exists at {remote_url}")
            typer.echo("Please delete it manually on GitHub if needed.")

    # Delete local .git directory
    typer.echo(f"\nDeleting local git repository...")
    try:
        shutil.rmtree(git_dir)
        typer.echo(f"Local git repository deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to delete local git repository: {e}")
        typer.echo(f"Error: Could not delete local git repository: {e}")
        raise typer.Exit(1)

    # Remove remote URL from .env file if it exists
    if remote_url:
        _remove_from_env_file("CALENDAR_GIT_REMOTE_URL")
        typer.echo("Remote URL removed from .env file")

    typer.echo("\nGit repository deletion complete!")


def _extract_repo_name_from_url(remote_url: str) -> str | None:
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


def _delete_remote_repo(full_repo_name: str) -> tuple[bool, str]:
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


def _remove_from_env_file(key: str) -> None:
    """Remove a key from .env file."""
    env_file = Path(".env")
    if not env_file.exists():
        return

    env_content = env_file.read_text()
    lines = env_content.splitlines()
    updated_lines = [line for line in lines if not line.startswith(f"{key}=")]

    if len(updated_lines) < len(lines):
        env_file.write_text("\n".join(updated_lines) + "\n")


def _write_to_env_file(key: str, value: str) -> None:
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
