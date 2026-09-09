"""Small, readable tools for an agent's Linux workspace.

File paths are checked to catch mistakes. The shell is deliberately unrestricted:
the actual isolation boundary is the AgentCore session, not this Python class.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

from strands import tool

MAX_FILE_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 20_000
MAX_COMMAND_SECONDS = 120


class Workspace:
    """Files and commands rooted in one session's working directory."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str) -> Path:
        if not isinstance(path, str) or not path:
            raise ValueError("path must be a non-empty string")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("path must stay inside the workspace")
        if ".conversation" in target.relative_to(self.root).parts:
            raise ValueError(".conversation is reserved for session history")
        return target

    def read_text(self, path: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ValueError("path must name a regular file")
        with target.open("rb") as source:
            data = source.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("file exceeds the 1 MiB text-file limit")
        return data.decode("utf-8")

    def list_entries(self, path: str = ".") -> list[dict]:
        directory = self.resolve(path)
        entries = []
        for entry in directory.iterdir():
            # Hidden files remain accessible through the shell, but aren't artifacts.
            if entry.name.startswith(".") or entry.is_symlink():
                continue
            if not (entry.is_file() or entry.is_dir()):
                continue
            entries.append({
                "path": str(entry.relative_to(self.root)),
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
            if len(entries) > 500:
                raise ValueError("too many entries; list a smaller directory with the shell")
        return sorted(entries, key=lambda entry: entry["path"])

    @tool
    def read_file(self, path: str) -> str:
        """Read a UTF-8 file, up to 1 MiB, relative to the workspace.

        Args:
            path: Relative file path.
        """
        return self.read_text(path)

    @tool
    def write_file(self, path: str, content: str) -> str:
        """Create or replace a UTF-8 file, creating parent directories as needed.

        Args:
            path: Relative file path.
            content: Complete file contents, up to 1 MiB.
        """
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("content exceeds the 1 MiB text-file limit")
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target.relative_to(self.root)}"

    @tool
    def list_files(self, path: str = ".") -> str:
        """List the visible files and directories at a workspace path.

        Args:
            path: Relative directory path; defaults to the workspace root.
        """
        return json.dumps(self.list_entries(path))

    @tool
    def run_shell(self, command: str, timeout_seconds: int = 60) -> str:
        """Run a bash command in the workspace and return exit code and output.

        Each call starts a fresh shell. Use `cd directory && command` for a
        subdirectory. Output is capped at 20 KB. Background jobs are stopped
        when the command ends; commands must finish within 120 seconds.

        Args:
            command: Bash command, such as `python analysis.py` or `git status`.
            timeout_seconds: Time limit between 1 and 120 seconds.
        """
        if not 1 <= timeout_seconds <= MAX_COMMAND_SECONDS:
            raise ValueError("timeout_seconds must be between 1 and 120")
        # A file captures large output without keeping it all in Python memory.
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                ["/bin/bash", "-c", command],
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            timed_out = False
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Stop the whole command group, including children on timeout.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            output.seek(0)
            data = output.read(MAX_OUTPUT_BYTES + 1)
        return json.dumps({
            "exit_code": process.returncode,
            "output": data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            "truncated": len(data) > MAX_OUTPUT_BYTES,
            "timed_out": timed_out,
        })
