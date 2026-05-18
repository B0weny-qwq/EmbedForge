"""STM32 SDK management commands."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from embedforge.util import Status, print_status


STM32F1_REPO = "https://github.com/STMicroelectronics/STM32CubeF1.git"
DEFAULT_STM32_SDK_ROOT = "~/SDK/STM32"
STM32F1_DIR_NAME = "STM32CubeF1"
STM32F1_REQUIRED_PATHS = [
    "Drivers/CMSIS",
    "Drivers/CMSIS/Device/ST/STM32F1xx",
    "Drivers/STM32F1xx_HAL_Driver",
    "Drivers/STM32F1xx_HAL_Driver/Inc",
    "Drivers/STM32F1xx_HAL_Driver/Src",
]


@dataclass(frozen=True)
class SdkPath:
    path: Path
    source: str


def add_sdk_arguments(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="sdk_command")

    check = subparsers.add_parser("check", help="check installed SDK")
    check.add_argument("family", choices=["stm32f1"])
    check.add_argument("--path", default=None, help="SDK path or SDK root")
    check.set_defaults(handler=handle_sdk)

    install = subparsers.add_parser("install", help="install SDK")
    install.add_argument("family", choices=["stm32f1"])
    install.add_argument("--path", default=None, help="SDK path or SDK root")
    install.add_argument("--dry-run", action="store_true", help="print clone command without running it")
    install.set_defaults(handler=handle_sdk)

    list_cmd = subparsers.add_parser("list", help="list supported SDKs")
    list_cmd.set_defaults(handler=handle_sdk)


def handle_sdk(args: argparse.Namespace) -> int:
    command = args.sdk_command
    if command == "list":
        return list_sdks()
    if command == "check":
        return check_stm32f1(resolve_stm32f1_path(args.path))
    if command == "install":
        return install_stm32f1(resolve_stm32f1_path(args.path), args.dry_run)
    print("error: missing sdk command", file=sys.stderr)
    return 2


def resolve_stm32f1_path(cli_path: str | None = None) -> SdkPath:
    if cli_path:
        return SdkPath(normalize_sdk_path(cli_path), "--path")
    env_path = os.environ.get("STM32CUBE_F1_PATH")
    if env_path:
        return SdkPath(Path(env_path).expanduser(), "STM32CUBE_F1_PATH")
    root = os.environ.get("EMBEDFORGE_SDK_ROOT")
    if root:
        return SdkPath(Path(root).expanduser() / STM32F1_DIR_NAME, "EMBEDFORGE_SDK_ROOT")
    return SdkPath(Path(DEFAULT_STM32_SDK_ROOT).expanduser() / STM32F1_DIR_NAME, "default")


def normalize_sdk_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.name == STM32F1_DIR_NAME:
        return path
    return path / STM32F1_DIR_NAME


def list_sdks() -> int:
    sdk = resolve_stm32f1_path()
    state = "OK" if sdk.path.is_dir() else "MISSING"
    print("Supported SDKs:")
    print(f"  stm32f1: {state} ({sdk.path})")
    return 0


def install_stm32f1(sdk: SdkPath, dry_run: bool) -> int:
    if sdk.path.exists():
        print(f"STM32CubeF1 already exists: {sdk.path}")
        return 0

    command = ["git", "clone", "--recursive", STM32F1_REPO, str(sdk.path)]
    print("SDK install plan:")
    print(f"  mkdir -p {shlex.quote(str(sdk.path.parent))}")
    print("  " + " ".join(shlex.quote(part) for part in command))
    if dry_run:
        return 0

    sdk.path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"error: failed to run git clone: {exc}", file=sys.stderr)
        return 2
    return completed.returncode


def check_stm32f1(sdk: SdkPath) -> int:
    print("STM32 SDK:")
    print(f"  STM32CubeF1 path: {sdk.path}")
    if not sdk.path.is_dir():
        print("STM32CubeF1 SDK not found.")
        print("Run:")
        print("  ./ef sdk install stm32f1")
        print()
        print("Or set:")
        print("  export STM32CUBE_F1_PATH=~/SDK/STM32/STM32CubeF1")
        return 1

    missing = []
    for relative in STM32F1_REQUIRED_PATHS:
        path = sdk.path / relative
        exists = path.exists()
        print_status(Status.OK if exists else Status.MISS, relative, str(path))
        if not exists:
            missing.append(relative)
    return 0 if not missing else 1
