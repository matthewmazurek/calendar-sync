"""CLI commands package."""

from cli.commands.config import config
from cli.commands.delete import delete
from cli.commands.diff import diff
from cli.commands.git_setup import git_setup
from cli.commands.info import info
from cli.commands.ls import ls
from cli.commands.sync import sync
from cli.commands.publish import publish
from cli.commands.restore import restore
from cli.commands.template import template
__all__ = [
    "config",
    "delete",
    "diff",
    "git_setup",
    "info",
    "ls",
    "sync",
    "publish",
    "restore",
    "template",
]
