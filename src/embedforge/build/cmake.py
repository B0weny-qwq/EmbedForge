"""CMake/Ninja build support."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from embedforge.core.config import ConfigError, get_nested, load_project_config
from embedforge.sdk import resolve_stm32f1_path


REPO_ROOT = Path(__file__).resolve().parents[3]


class BuildError(Exception):
    """User-facing build setup error."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", choices=["c51", "c251", "keil-arm", "cmake-arm"], default=None)
    parser.add_argument("--example", default=None, help="example project name under examples/")
    parser.add_argument("--dry-run", action="store_true", help="print build commands without executing")


def run(args: argparse.Namespace) -> int:
    try:
        project_dir = resolve_project_dir(args)
        config = load_project_config(project_dir)
        system = get_nested(config, "build.system")
        if args.target not in {None, "cmake-arm"} or system != "cmake":
            command = args.target or system or "build"
            print(f"EmbedForge: '{command}' build is registered but not implemented yet.")
            return 0
        return build_cmake_project(project_dir, config, args.dry_run)
    except (BuildError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 2)


def resolve_project_dir(args: argparse.Namespace) -> Path:
    if args.example:
        path = REPO_ROOT / "examples" / args.example
        if not path.is_dir():
            raise BuildError(f"example not found: {args.example}")
        return path
    return Path.cwd()


def build_cmake_project(project_dir: Path, config: dict[str, object], dry_run: bool = False) -> int:
    build_dir = project_dir / str(get_nested(config, "build.build_dir", "build"))
    generator = str(get_nested(config, "build.generator", "ninja"))
    toolchain_file = project_dir / "cmake" / "arm-none-eabi.cmake"
    sdk_path = resolve_sdk_path(config)

    configure = [
        "cmake",
        "-S",
        ".",
        "-B",
        str(build_dir.relative_to(project_dir)),
        "-G",
        "Ninja" if generator == "ninja" else generator,
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file.relative_to(project_dir)}",
        f"-DSTM32CUBE_F1_PATH={sdk_path}",
    ]
    build = ["cmake", "--build", str(build_dir.relative_to(project_dir))]

    print("CMake configure:")
    print("  " + format_command(configure))
    print("CMake build:")
    print("  " + format_command(build))
    if dry_run:
        return 0

    env = os.environ.copy()
    env["STM32CUBE_F1_PATH"] = str(sdk_path)
    for command in (configure, build):
        completed = subprocess.run(command, cwd=project_dir, env=env, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def resolve_sdk_path(config: dict[str, object]) -> Path:
    env_name = str(get_nested(config, "sdk.env", "STM32CUBE_F1_PATH"))
    if os.environ.get(env_name):
        return Path(os.environ[env_name]).expanduser()
    return resolve_stm32f1_path(None).path


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)
