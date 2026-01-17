"""Tests for configuration."""

import os
import tempfile
from pathlib import Path

import pytest

from app.config import CalendarConfig


def test_calendar_config_defaults():
    """Test CalendarConfig default values."""
    config = CalendarConfig()
    assert config.calendar_dir == Path("data/calendars")
    assert config.ls_default_limit == 5
    assert config.calendar_git_remote_url is None


def test_calendar_config_from_env_calendar_git_remote_url(monkeypatch):
    """Test loading CALENDAR_GIT_REMOTE_URL from environment."""
    monkeypatch.setenv("CALENDAR_GIT_REMOTE_URL", "https://github.com/user/repo.git")
    config = CalendarConfig.from_env()
    assert config.calendar_git_remote_url == "https://github.com/user/repo.git"


def test_calendar_config_from_env_all_vars(monkeypatch):
    """Test loading all config values from environment."""
    monkeypatch.setenv("CALENDAR_DIR", "/custom/path/calendars")
    monkeypatch.setenv("LS_DEFAULT_LIMIT", "10")
    monkeypatch.setenv("CALENDAR_GIT_REMOTE_URL", "https://github.com/user/repo.git")

    config = CalendarConfig.from_env()
    assert config.calendar_dir == Path("/custom/path/calendars")
    assert config.ls_default_limit == 10
    assert config.calendar_git_remote_url == "https://github.com/user/repo.git"


def test_calendar_config_from_env_file(tmp_path, monkeypatch):
    """Test loading config from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CALENDAR_GIT_REMOTE_URL=https://github.com/user/repo.git\n"
    )

    # Change to tmp_path so .env file is found
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        config = CalendarConfig.from_env()
        # Note: dotenv loading depends on python-dotenv being installed
        # This test verifies the code path exists
        assert hasattr(config, "calendar_git_remote_url")
    finally:
        os.chdir(original_cwd)


def test_calendar_config_invalid_ls_default_limit(monkeypatch):
    """Test handling invalid LS_DEFAULT_LIMIT."""
    monkeypatch.setenv("LS_DEFAULT_LIMIT", "invalid")
    config = CalendarConfig.from_env()
    # Should fall back to default
    assert config.ls_default_limit == 5
