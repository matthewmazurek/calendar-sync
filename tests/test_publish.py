"""Tests for git publishing functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.publish import GitPublisher


def test_git_publisher_init():
    """Test GitPublisher initialization."""
    calendar_dir = Path("data/calendars")
    publisher = GitPublisher(calendar_dir)
    assert publisher.calendar_dir == calendar_dir
    assert publisher.remote_url is None

    publisher_with_url = GitPublisher(calendar_dir, remote_url="https://github.com/user/repo.git")
    assert publisher_with_url.remote_url == "https://github.com/user/repo.git"


def test_is_git_repo():
    """Test _is_git_repo detection."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        # Test when in git repo
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
        assert publisher._is_git_repo() is True

        # Test when not in git repo
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert publisher._is_git_repo() is False


def test_get_remote_url():
    """Test getting remote URL from git config."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        # Test successful remote URL retrieval
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/user/repo.git\n"
        )
        url = publisher._get_remote_url()
        assert url == "https://github.com/user/repo.git"

        # Test when remote not configured
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        url = publisher._get_remote_url()
        assert url is None


def test_get_branch():
    """Test getting current branch name."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        # Test successful branch retrieval
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n")
        branch = publisher._get_branch()
        assert branch == "main"

        # Test fallback to master
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        branch = publisher._get_branch()
        assert branch == "master"


def test_parse_remote_url_ssh():
    """Test parsing SSH format remote URL."""
    publisher = GitPublisher(Path("data/calendars"))
    owner, repo = publisher._parse_remote_url("git@github.com:owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_remote_url_https():
    """Test parsing HTTPS format remote URL."""
    publisher = GitPublisher(Path("data/calendars"))
    owner, repo = publisher._parse_remote_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"

    # Test without .git suffix
    owner, repo = publisher._parse_remote_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_remote_url_invalid():
    """Test parsing invalid remote URL."""
    publisher = GitPublisher(Path("data/calendars"))
    owner, repo = publisher._parse_remote_url("invalid-url")
    assert owner is None
    assert repo is None


def test_generate_subscription_urls():
    """Test subscription URL generation."""
    publisher = GitPublisher(Path("data/calendars"), remote_url="https://github.com/user/repo.git")

    with patch.object(publisher, "_get_branch", return_value="main"):
        filepath = Path("data/calendars/mazurek/calendar.ics")
        urls = publisher.generate_subscription_urls("mazurek", filepath, "ics")

        assert len(urls) == 1
        assert "calendar.ics" in urls[0]
        assert "user/repo" in urls[0]
        assert "main" in urls[0]


def test_generate_subscription_urls_no_remote():
    """Test subscription URL generation when remote is not available."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch.object(publisher, "_get_remote_url", return_value=None):
        filepath = Path("data/calendars/mazurek/calendar.ics")
        urls = publisher.generate_subscription_urls("mazurek", filepath, "ics")
        assert urls == []


def test_publish_calendar_not_in_git_repo():
    """Test publish_calendar when not in git repository."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch.object(publisher, "_is_git_repo", return_value=False):
        # Should not raise, just log warning
        publisher.publish_calendar("mazurek", Path("test.ics"), "ics")


def test_publish_calendar_success():
    """Test successful calendar publishing."""
    publisher = GitPublisher(Path("data/calendars"), remote_url="https://github.com/user/repo.git")

    with patch.object(publisher, "_is_git_repo", return_value=True), \
         patch.object(publisher, "commit_calendar_locally") as mock_commit_local, \
         patch.object(publisher, "_push_changes") as mock_push, \
         patch.object(publisher, "generate_subscription_urls", return_value=["url1", "url2"]):

        filepath = Path("data/calendars/mazurek/calendar.ics")
        publisher.publish_calendar("mazurek", filepath, "ics")

        mock_commit_local.assert_called_once_with("mazurek")
        mock_push.assert_called_once()


def test_publish_calendar_git_failure():
    """Test publish_calendar when git operations fail."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch.object(publisher, "_is_git_repo", return_value=True), \
         patch.object(publisher, "commit_calendar_locally", side_effect=Exception("Git error")):

        # Should not raise, just log warning
        publisher.publish_calendar("mazurek", Path("test.ics"), "ics")


def test_stage_calendar_directory():
    """Test staging calendar files."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Create a temporary calendar directory with files
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_dir = Path(tmpdir) / "test_calendar"
            calendar_dir.mkdir()
            (calendar_dir / "calendar.ics").touch()
            (calendar_dir / "metadata.json").touch()
            
            publisher.calendar_dir = Path(tmpdir)
            publisher._stage_calendar_files("test_calendar")
            
            # Should be called for both calendar.ics and metadata.json
            assert mock_run.call_count >= 2
            assert "git" in mock_run.call_args[0][0]
            assert "add" in mock_run.call_args[0][0]


def test_commit_changes():
    """Test committing changes."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        # Test with changes to commit
        # git diff --cached --quiet returns non-zero exit code when there are staged changes
        mock_run.side_effect = [
            MagicMock(returncode=1),  # diff --cached --quiet (has staged changes)
            MagicMock(returncode=0),  # commit
        ]
        publisher._commit_changes("Test commit")
        assert mock_run.call_count == 2

        # Test with no changes
        mock_run.reset_mock()
        # git diff --cached --quiet returns 0 when no staged changes
        mock_run.side_effect = [
            MagicMock(returncode=0),  # diff --cached --quiet (no staged changes)
        ]
        publisher._commit_changes("Test commit")
        # Should only call diff, not commit
        assert mock_run.call_count == 1


def test_push_changes():
    """Test pushing changes."""
    publisher = GitPublisher(Path("data/calendars"))

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        publisher._push_changes()
        mock_run.assert_called_once()
        assert "git" in mock_run.call_args[0][0]
        assert "push" in mock_run.call_args[0][0]
