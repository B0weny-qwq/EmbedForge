"""Vendor SDK management commands."""

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
MSPM0_REPO = "https://github.com/TexasInstruments/mspm0-sdk.git"
DEFAULT_STM32_SDK_ROOT = "~/SDK/STM32"
DEFAULT_TI_SDK_ROOT = "~/SDK/TI"
STM32F1_DIR_NAME = "STM32CubeF1"
MSPM0_DIR_NAME = "mspm0-sdk"
STM32F1_REQUIRED_PATHS = [
    "Drivers/CMSIS",
    "Drivers/CMSIS/Device/ST/STM32F1xx",
    "Drivers/STM32F1xx_HAL_Driver",
    "Drivers/STM32F1xx_HAL_Driver/Inc",
    "Drivers/STM32F1xx_HAL_Driver/Src",
]
MSPM0_REQUIRED_PATHS = [
    "docs",
    "examples",
    "kernel",
    "source",
    "tools",
    "imports.mak.linux",
]


@dataclass(frozen=True)
class SdkPath:
    path: Path
    source: str


def add_sdk_arguments(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="sdk_command")

    check = subparsers.add_parser("check", help="check installed SDK")
    check.add_argument("family", choices=["stm32f1", "mspm0"])
    check.add_argument("--path", default=None, help="SDK path or SDK root")
    check.set_defaults(handler=handle_sdk)

    install = subparsers.add_parser("install", help="install SDK")
    install.add_argument("family", choices=["stm32f1", "mspm0"])
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
        if args.family == "stm32f1":
            return check_stm32f1(resolve_stm32f1_path(args.path))
        if args.family == "mspm0":
            return check_mspm0(resolve_mspm0_path(args.path))
    if command == "install":
        if args.family == "stm32f1":
            return install_sdk("STM32CubeF1", STM32F1_REPO, resolve_stm32f1_path(args.path), args.dry_run)
        if args.family == "mspm0":
            return install_sdk("MSPM0 SDK", MSPM0_REPO, resolve_mspm0_path(args.path), args.dry_run)
    print("error: missing sdk command", file=sys.stderr)
    return 2


def resolve_stm32f1_path(cli_path: str | None = None) -> SdkPath:
    if cli_path:
        return SdkPath(normalize_sdk_path(cli_path, STM32F1_DIR_NAME), "--path")
    env_path = os.environ.get("STM32CUBE_F1_PATH")
    if env_path:
        return SdkPath(Path(env_path).expanduser(), "STM32CUBE_F1_PATH")
    root = os.environ.get("EMBEDFORGE_SDK_ROOT")
    if root:
        return SdkPath(Path(root).expanduser() / STM32F1_DIR_NAME, "EMBEDFORGE_SDK_ROOT")
    return SdkPath(Path(DEFAULT_STM32_SDK_ROOT).expanduser() / STM32F1_DIR_NAME, "default")


def resolve_mspm0_path(cli_path: str | None = None) -> SdkPath:
    if cli_path:
        return SdkPath(normalize_sdk_path(cli_path, MSPM0_DIR_NAME), "--path")
    env_path = os.environ.get("MSPM0_SDK_PATH")
    if env_path:
        return SdkPath(Path(env_path).expanduser(), "MSPM0_SDK_PATH")
    root = os.environ.get("EMBEDFORGE_SDK_ROOT")
    if root:
        return SdkPath(Path(root).expanduser() / MSPM0_DIR_NAME, "EMBEDFORGE_SDK_ROOT")
    return SdkPath(Path(DEFAULT_TI_SDK_ROOT).expanduser() / MSPM0_DIR_NAME, "default")


def normalize_sdk_path(path_text: str, sdk_dir_name: str) -> Path:
    path = Path(path_text).expanduser()
    if path.name == sdk_dir_name:
        return path
    return path / sdk_dir_name


def list_sdks() -> int:
    stm32 = resolve_stm32f1_path()
    mspm0 = resolve_mspm0_path()
    stm32_state = "OK" if stm32.path.is_dir() else "MISSING"
    mspm0_state = "OK" if mspm0.path.is_dir() else "MISSING"
    print("Supported SDKs:")
    print(f"  stm32f1: {stm32_state} ({stm32.path})")
    print(f"  mspm0: {mspm0_state} ({mspm0.path})")
    return 0


def install_stm32f1(sdk: SdkPath, dry_run: bool) -> int:
    return install_sdk("STM32CubeF1", STM32F1_REPO, sdk, dry_run)


def install_mspm0(sdk: SdkPath, dry_run: bool) -> int:
    return install_sdk("MSPM0 SDK", MSPM0_REPO, sdk, dry_run)


def install_sdk(label: str, repo: str, sdk: SdkPath, dry_run: bool) -> int:
    if sdk.path.exists():
        print(f"{label} already exists: {sdk.path}")
        return 0

    command = ["git", "clone", "--recursive", repo, str(sdk.path)]
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


def check_mspm0(sdk: SdkPath) -> int:
    print("MSPM0 SDK:")
    print(f"  mspm0-sdk path: {sdk.path}")
    if not sdk.path.is_dir():
        print("MSPM0 SDK not found.")
        print("Run:")
        print("  ./ef sdk install mspm0")
        print()
        print("Or set:")
        print("  export MSPM0_SDK_PATH=~/SDK/TI/mspm0-sdk")
        return 1

    missing = []
    for relative in MSPM0_REQUIRED_PATHS:
        path = sdk.path / relative
        exists = path.exists()
        print_status(Status.OK if exists else Status.MISS, relative, str(path))
        if not exists:
            missing.append(relative)
    return 0 if not missing else 1
