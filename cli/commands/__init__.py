"""CLI commands package."""

from cli.commands.config import config
from cli.commands.delete import delete
from cli.commands.diff import diff
from cli.commands.git_setup import git_setup
from cli.commands.info import info
from cli.commands.ls import ls
from cli.commands.push import push
from cli.commands.restore import restore
from cli.commands.search import search
from cli.commands.show import show
from cli.commands.sync import sync
from cli.commands.template import template

__all__ = [
    "config",
    "delete",
    "diff",
    "git_setup",
    "info",
    "ls",
    "push",
    "restore",
    "search",
    "show",
    "sync",
    "template",
]
