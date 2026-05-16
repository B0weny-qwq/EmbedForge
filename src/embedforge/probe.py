"""Local environment probing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class CommandResult:
    """Result from a command probe that never raises to callers."""

    cmd: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None


def find_executable(root: str | Path, names: list[str] | tuple[str, ...]) -> Path | None:
    """Find the first executable-like file under root matching any provided name.

    Matching is case-insensitive so Wine-mounted Windows paths work even when a
    tool appears as either L251.EXE or l251.exe.
    """

    root_path = Path(root)
    if not root_path.exists():
        return None

    wanted = {name.lower() for name in names}
    for path in root_path.rglob("*"):
        if path.is_file() and path.name.lower() in wanted:
            return path
    return None


def run_command(cmd: list[str], timeout: int = 5) -> CommandResult:
    """Run a command and return a status object instead of raising."""

    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            cmd=cmd,
            returncode=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            timed_out=True,
            error=f"timed out after {timeout}s",
        )
    except OSError as exc:
        return CommandResult(cmd=cmd, returncode=None, stdout="", stderr="", error=str(exc))

    return CommandResult(
        cmd=cmd,
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
