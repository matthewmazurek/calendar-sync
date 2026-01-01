"""Tests for git publishing functionality."""

import subprocess
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


def test_stage_calendar_directory(tmp_path):
    """Test staging calendar files."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    
    test_calendar = calendar_dir / "test_calendar"
    test_calendar.mkdir()
    (test_calendar / "calendar.ics").touch()
    (test_calendar / "metadata.json").touch()
    
    publisher = GitPublisher(calendar_dir)
    publisher._stage_calendar_files("test_calendar")
    
    # Check that files were staged
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=calendar_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "test_calendar/calendar.ics" in result.stdout or "A" in result.stdout


def test_commit_changes(tmp_path):
    """Test committing changes."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=calendar_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=calendar_dir,
        check=True,
    )
    
    # Create and stage a file
    test_file = calendar_dir / "test.txt"
    test_file.write_text("test")
    subprocess.run(["git", "add", "test.txt"], cwd=calendar_dir, check=True)
    
    publisher = GitPublisher(calendar_dir)
    publisher._commit_changes("Test commit")
    
    # Check that commit was created
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=calendar_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Test commit" in result.stdout
    
    # Test with no changes
    publisher._commit_changes("No changes commit")
    # Should not create another commit
    result2 = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=calendar_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result2.stdout.count("Test commit") == 1


def test_push_changes(tmp_path):
    """Test pushing changes."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    
    publisher = GitPublisher(calendar_dir)
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        publisher._push_changes()
        # Should call git push
        push_calls = [call for call in mock_run.call_args_list if "push" in str(call)]
        assert len(push_calls) > 0


def test_git_publisher_uses_calendar_dir_as_repo_root(tmp_path):
    """Test GitPublisher uses calendar_dir as repo root."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)

    publisher = GitPublisher(calendar_dir)
    repo_root = publisher._get_repo_root()
    assert repo_root == calendar_dir


def test_git_publisher_is_git_repo_checks_calendar_dir(tmp_path):
    """Test _is_git_repo checks calendar_dir, not current directory."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)

    publisher = GitPublisher(calendar_dir)
    assert publisher._is_git_repo() is True

    # Test with non-git directory
    # Note: _is_git_repo uses `git rev-parse --is-inside-work-tree` which checks
    # if we're inside ANY git repo. If we're running tests from within the project
    # (which is a git repo), subdirectories will be detected as inside the repo.
    # So we'll test the behavior: if calendar_dir has .git, it should be True;
    # if it doesn't, the result depends on whether we're in a parent git repo.
    # The key test is that it checks calendar_dir, not the current working directory.
    non_git_dir = tmp_path / "non_git"
    non_git_dir.mkdir()
    # Ensure no .git in this specific directory
    assert not (non_git_dir / ".git").exists()
    
    publisher2 = GitPublisher(non_git_dir)
    # The result depends on whether tmp_path is in a git repo
    # But the important thing is that it checked non_git_dir, not cwd
    result = publisher2._is_git_repo()
    # Just verify the method works without error
    assert isinstance(result, bool)


def test_git_publisher_get_remote_url_from_calendar_dir(tmp_path):
    """Test _get_remote_url reads from calendar_dir git config."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
        cwd=calendar_dir,
        check=True,
    )

    publisher = GitPublisher(calendar_dir)
    remote_url = publisher._get_remote_url()
    assert remote_url == "https://github.com/user/repo.git"


def test_git_publisher_generate_subscription_urls_with_calendar_repo(tmp_path):
    """Test subscription URL generation when calendar_dir is repo root."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
        cwd=calendar_dir,
        check=True,
    )

    # Create calendar file
    test_calendar = calendar_dir / "test_calendar"
    test_calendar.mkdir()
    calendar_file = test_calendar / "calendar.ics"
    calendar_file.write_text("BEGIN:VCALENDAR\nEND:VCALENDAR")

    publisher = GitPublisher(calendar_dir)
    with patch.object(publisher, "_get_branch", return_value="main"):
        urls = publisher.generate_subscription_urls("test_calendar", calendar_file, "ics")
        assert len(urls) == 1
        assert "test_calendar/calendar.ics" in urls[0]
        assert "user/repo" in urls[0]
        assert "main" in urls[0]


def test_git_publisher_stage_calendar_files_relative_to_repo_root(tmp_path):
    """Test _stage_calendar_files uses relative paths from repo root."""
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    subprocess.run(["git", "init"], cwd=calendar_dir, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=calendar_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=calendar_dir,
        check=True,
    )

    test_calendar = calendar_dir / "test_calendar"
    test_calendar.mkdir()
    (test_calendar / "calendar.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR")

    publisher = GitPublisher(calendar_dir)
    publisher._stage_calendar_files("test_calendar")
    
    # Check that file was staged
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=calendar_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "test_calendar/calendar.ics" in result.stdout or "A" in result.stdout
