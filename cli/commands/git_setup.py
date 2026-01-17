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

    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'━' * 40}")
    print(typer.style("  Git Setup", bold=True))
    print(f"{'━' * 40}")
    print(f"\nDirectory: {calendar_dir}")

    # ─────────────────────────────────────────────────────────────────────────
    # Check existing repository
    # ─────────────────────────────────────────────────────────────────────────
    if (calendar_dir / ".git").exists():
        git_service = GitService(calendar_dir)
        remote_url = git_service.get_remote_url()
        if remote_url:
            print("\nRepository already configured:")
            print(f"  Remote: {remote_url}")
            return

        print("\nRepository exists but no remote configured.")
        print("Setting up remote...")
    else:
        # Initialize git repo
        print("\nInitializing...")
        print("  Creating git repository...", end=" ", flush=True)
        calendar_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "init"],
                cwd=calendar_dir,
                check=True,
                capture_output=True,
            )
            print(typer.style("done", fg=typer.colors.GREEN))
        except subprocess.CalledProcessError as e:
            print(typer.style("failed", fg=typer.colors.RED))
            logger.error(f"Failed to initialize git repository: {e}")
            raise typer.Exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Remote URL configuration
    # ─────────────────────────────────────────────────────────────────────────
    remote_url = None

    # Tier 1: Try GitHub CLI first (most seamless)
    if _check_gh_cli_available():
        username = _get_github_username_from_gh()
        if username:
            print(f"\nGitHub CLI detected (user: {username})")
            default_repo_name = "calendar-sync-calendars"
            response = typer.prompt("Repository name", default=default_repo_name)

            repo_name = response if response else default_repo_name
            full_repo_name = f"{username}/{repo_name}"

            print(f"\n  Creating GitHub repository...", end=" ", flush=True)
            if _create_repo_with_gh(username, repo_name, calendar_dir):
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                print(typer.style("done", fg=typer.colors.GREEN))

    # Tier 2: Manual fallback
    if not remote_url:
        print("\nCould not auto-detect GitHub settings.")
        manual_url = typer.prompt(
            "Enter GitHub repository URL (or press Enter to skip)",
            default="",
        )
        if manual_url:
            remote_url = manual_url

    # Set up remote if we have a URL
    if remote_url:
        print("  Configuring remote...", end=" ", flush=True)
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
            print(typer.style("done", fg=typer.colors.GREEN))

            # Save to .env file
            _write_to_env_file("CALENDAR_GIT_REMOTE_URL", remote_url)
        except subprocess.CalledProcessError as e:
            print(typer.style("failed", fg=typer.colors.RED))
            logger.warning(f"Failed to set remote: {e}")
            print("  Warning: Could not configure remote. Set it manually later.")

    # ─────────────────────────────────────────────────────────────────────────
    # Initial commit
    # ─────────────────────────────────────────────────────────────────────────
    if calendar_dir.exists():
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=calendar_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            print("  Creating initial commit...", end=" ", flush=True)
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
                print(typer.style("done", fg=typer.colors.GREEN))
            except subprocess.CalledProcessError as e:
                print(typer.style("skipped", fg=typer.colors.YELLOW))
                logger.warning(f"Failed to create initial commit: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{typer.style('Setup complete', bold=True)}")
    if remote_url:
        print(f"  Remote: {remote_url}")
        print("\nYou can now use 'calsync push' to push calendars.")
    else:
        print("  No remote configured.")
        print("\nTo add a remote later:")
        print("  git remote add origin <repository-url>")


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
    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'━' * 40}")
    print(typer.style("  Git Repository Deletion", bold=True))
    print(f"{'━' * 40}")

    # Check if git repo exists
    git_dir = calendar_dir / ".git"
    if not git_dir.exists():
        print(f"\nNo git repository found in {calendar_dir}")
        return

    # Get remote URL if it exists
    git_service = GitService(calendar_dir)
    remote_url = git_service.get_remote_url()

    # Show what will be deleted
    print("\nThis will delete:")
    print(f"  Local:  {git_dir}")
    if remote_url:
        repo_name = _extract_repo_name_from_url(remote_url)
        print(f"  Remote: {remote_url}")
        if repo_name:
            print(f"          ({repo_name})")
    else:
        print("  Remote: (none configured)")

    # Confirmation prompt
    print()
    if not typer.confirm("Are you sure you want to delete the git repository?"):
        print("Deletion cancelled.")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # Delete remote repository
    # ─────────────────────────────────────────────────────────────────────────
    print("\nDeleting...")

    if remote_url:
        repo_name = _extract_repo_name_from_url(remote_url)
        if repo_name and _check_gh_cli_available():
            print(f"  Deleting remote repository...", end=" ", flush=True)
            success, error_msg = _delete_remote_repo(repo_name)
            if success:
                print(typer.style("done", fg=typer.colors.GREEN))
            else:
                print(typer.style("failed", fg=typer.colors.RED))
                if error_msg:
                    if (
                        "delete_repo" in error_msg.lower()
                        or "admin rights" in error_msg.lower()
                    ):
                        print("\n  GitHub CLI needs 'delete_repo' scope. Run:")
                        print("    gh auth refresh -h github.com -s delete_repo")
                    else:
                        print(f"  Error: {error_msg}")
                print("  Delete manually on GitHub if needed.")
        else:
            print(f"  Remote: {remote_url}")
            print("  (Delete manually on GitHub if needed)")

    # ─────────────────────────────────────────────────────────────────────────
    # Delete local repository
    # ─────────────────────────────────────────────────────────────────────────
    print("  Deleting local repository...", end=" ", flush=True)
    try:
        shutil.rmtree(git_dir)
        print(typer.style("done", fg=typer.colors.GREEN))
    except Exception as e:
        print(typer.style("failed", fg=typer.colors.RED))
        logger.error(f"Failed to delete local git repository: {e}")
        print(f"  Error: {e}")
        raise typer.Exit(1)

    # Remove remote URL from .env file if it exists
    if remote_url:
        _remove_from_env_file("CALENDAR_GIT_REMOTE_URL")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{typer.style('Deletion complete', bold=True)}")


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
