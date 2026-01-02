"""CLI commands package."""

from cli.commands.config import config_command
from cli.commands.delete import delete_command
from cli.commands.git_setup import git_setup_command
from cli.commands.info import info_command
from cli.commands.ls import ls_command
from cli.commands.sync import sync_command
from cli.commands.publish import publish_command
from cli.commands.restore import restore_command
from cli.commands.template import template_command

__all__ = [
    "config_command",
    "delete_command",
    "git_setup_command",
    "info_command",
    "ls_command",
    "sync_command",
    "publish_command",
    "restore_command",
    "template_command",
]
