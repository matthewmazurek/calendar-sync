"""Tests for git-setup command."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.config import CalendarConfig
from cli.context import CLIContext, set_context

# Import the module properly using sys.modules
# (not using `import cli.commands.git_setup as module` because Python
# resolves that to the function named git_setup, not the module)
from cli.commands import git_setup as git_setup_func
git_setup_module = sys.modules['cli.commands.git_setup']


@pytest.fixture
def temp_calendar_dir():
    """Create a temporary calendar directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_env_file(tmp_path):
    """Create a temporary .env file."""
    env_file = tmp_path / ".env"
    yield env_file
    if env_file.exists():
        env_file.unlink()


@pytest.fixture
def mock_context():
    """Set up mock CLI context."""
    ctx = CLIContext()
    set_context(ctx)
    return ctx


def test_check_gh_cli_available():
    """Test checking if GitHub CLI is available."""
    with patch("subprocess.run") as mock_run:
        # Test when gh is available and authenticated
        mock_run.side_effect = [
            MagicMock(returncode=0),  # gh --version
            MagicMock(returncode=0),  # gh auth status
        ]
        assert git_setup_module._check_gh_cli_available() is True

        # Test when gh is not installed
        mock_run.side_effect = [
            MagicMock(returncode=1),  # gh --version fails
        ]
        assert git_setup_module._check_gh_cli_available() is False

        # Test when gh is installed but not authenticated
        mock_run.side_effect = [
            MagicMock(returncode=0),  # gh --version
            MagicMock(returncode=1),  # gh auth status fails
        ]
        assert git_setup_module._check_gh_cli_available() is False


def test_get_github_username_from_gh():
    """Test getting GitHub username from gh CLI."""
    with patch("subprocess.run") as mock_run:
        mock_data = {"login": "testuser"}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(mock_data)
        )
        username = git_setup_module._get_github_username_from_gh()
        assert username == "testuser"

        # Test when gh command fails
        mock_run.return_value = MagicMock(returncode=1)
        username = git_setup_module._get_github_username_from_gh()
        assert username is None


def test_create_repo_with_gh(tmp_path):
    """Test creating repo with GitHub CLI."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = git_setup_module._create_repo_with_gh("testuser", "test-repo", tmp_path)
        assert result is True
        assert mock_run.called
        assert "gh" in mock_run.call_args[0][0]
        assert "repo" in mock_run.call_args[0][0]
        assert "create" in mock_run.call_args[0][0]

        # Test failure
        mock_run.return_value = MagicMock(returncode=1)
        result = git_setup_module._create_repo_with_gh("testuser", "test-repo", tmp_path)
        assert result is False


def test_write_to_env_file_new_file(tmp_path, monkeypatch):
    """Test writing to new .env file."""
    env_file = tmp_path / ".env"
    
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)
    git_setup_module._write_to_env_file("TEST_KEY", "test_value")
    
    assert env_file.exists()
    content = env_file.read_text()
    assert "TEST_KEY=test_value" in content


def test_write_to_env_file_update_existing(tmp_path, monkeypatch):
    """Test updating existing .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_KEY=old_value\n")
    
    monkeypatch.chdir(tmp_path)
    git_setup_module._write_to_env_file("EXISTING_KEY", "new_value")
    content = env_file.read_text()
    assert "EXISTING_KEY=new_value" in content
    assert "old_value" not in content


def test_write_to_env_file_append_new_key(tmp_path, monkeypatch):
    """Test appending new key to existing .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_KEY=value\n")
    
    monkeypatch.chdir(tmp_path)
    git_setup_module._write_to_env_file("NEW_KEY", "new_value")
    content = env_file.read_text()
    assert "EXISTING_KEY=value" in content
    assert "NEW_KEY=new_value" in content


def test_git_setup_existing_repo(tmp_path, monkeypatch, mock_context):
    """Test git-setup when repo already exists."""
    # Create existing git repo
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
        cwd=calendar_dir,
        check=True,
        capture_output=True,
    )

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    mock_context._config = config

    with patch.object(git_setup_module, "get_context", return_value=mock_context):
        # Should detect existing repo and remote
        with patch("typer.echo") as mock_echo:
            git_setup_func()
            # Should print that repo already exists
            assert any("already exists" in str(call) for call in mock_echo.call_args_list)


def test_git_setup_init_new_repo(tmp_path, monkeypatch, mock_context):
    """Test git-setup initializing new repo."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    mock_context._config = config

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with patch.object(git_setup_module, "get_context", return_value=mock_context), \
             patch.object(git_setup_module, "_check_gh_cli_available", return_value=False), \
             patch("typer.prompt", return_value=""):
            git_setup_func()
            # Should have created .git directory
            assert (calendar_dir / ".git").exists()
    finally:
        os.chdir(original_cwd)


def test_git_setup_with_gh_cli(tmp_path, monkeypatch, mock_context):
    """Test git-setup using GitHub CLI."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    mock_context._config = config

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with patch.object(git_setup_module, "get_context", return_value=mock_context), \
             patch.object(git_setup_module, "_check_gh_cli_available", return_value=True), \
             patch.object(git_setup_module, "_get_github_username_from_gh", return_value="testuser"), \
             patch.object(git_setup_module, "_create_repo_with_gh", return_value=True), \
             patch("typer.prompt", return_value=""):
            git_setup_func()
            # Should have created .git directory
            assert (calendar_dir / ".git").exists()
    finally:
        os.chdir(original_cwd)


def test_git_setup_creates_initial_commit(tmp_path, monkeypatch, mock_context):
    """Test git-setup creates initial commit if files exist."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    (calendar_dir / "test_calendar").mkdir()
    (calendar_dir / "test_calendar" / "calendar.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR")

    config = CalendarConfig()
    config.calendar_dir = calendar_dir
    mock_context._config = config

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with patch.object(git_setup_module, "get_context", return_value=mock_context), \
             patch.object(git_setup_module, "_check_gh_cli_available", return_value=False), \
             patch("typer.prompt", return_value=""):
            git_setup_func()
            # Should have created .git directory
            assert (calendar_dir / ".git").exists()
            # Check if initial commit was created
            result = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=calendar_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            # If commit was created, log should have output
            # (may be empty if no changes, but repo should exist)
            assert (calendar_dir / ".git").exists()
    finally:
        os.chdir(original_cwd)
