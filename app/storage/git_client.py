"""Git client abstraction for subprocess operations."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol


@dataclass
class CommandResult:
    """Result of a git command execution."""

    returncode: int
    stdout: str
    stderr: str


class GitClient(Protocol):
    """Protocol for git command execution."""

    def run_command(self, cmd: List[str], cwd: Path) -> CommandResult:
        """
        Execute a git command.

        Args:
            cmd: Git command as list of strings (e.g., ["git", "status"])
            cwd: Working directory for command execution

        Returns:
            CommandResult with returncode, stdout, and stderr
        """
        ...


class SubprocessGitClient:
    """Git client implementation using subprocess."""

    def run_command(self, cmd: List[str], cwd: Path) -> CommandResult:
        """
        Execute a git command using subprocess.

        Args:
            cmd: Git command as list of strings
            cwd: Working directory for command execution

        Returns:
            CommandResult with returncode, stdout, and stderr
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except Exception as e:
            # Convert exception to CommandResult for consistent error handling
            return CommandResult(
                returncode=1,
                stdout="",
                stderr=str(e),
            )
