#!/usr/bin/env python3
"""Command-line entry point for EmbedForge."""

from __future__ import annotations

import argparse
import os
import select
import sys
import termios
import time
from pathlib import Path

from embedforge import doctor
from embedforge import sdk
from embedforge.build import cmake as cmake_build
from embedforge.core.config import ConfigError, get_nested, load_project_config
from embedforge.flash import openocd as openocd_flash


REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ef", description="EmbedForge embedded automation toolkit")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="check local toolchain environment")
    doctor.add_argument("--stm32", action="store_true", help="check STM32 CLI toolchain and SDK")
    doctor.set_defaults(handler=doctor_module_handler)

    sdk_parser = subparsers.add_parser("sdk", help="manage vendor SDKs")
    sdk.add_sdk_arguments(sdk_parser)

    build = subparsers.add_parser("build", help="build firmware")
    cmake_build.add_build_arguments(build)
    build.set_defaults(handler=cmake_build.run)

    flash = subparsers.add_parser("flash", help="flash firmware")
    openocd_flash.add_flash_arguments(flash)
    flash.set_defaults(handler=openocd_flash_handler)

    reset = subparsers.add_parser("reset", help="reset target")
    reset.add_argument("--example", default=None)
    reset.add_argument("--adapter", default=None)
    reset.add_argument("--dry-run", action="store_true")
    reset.set_defaults(handler=handle_reset)

    monitor = subparsers.add_parser("monitor", help="open serial monitor")
    monitor.add_argument("--example", default=None)
    monitor.add_argument("--no-monitor", action="store_true")
    monitor.add_argument("--timeout", type=float, default=30.0)
    monitor.set_defaults(handler=handle_monitor)

    run = subparsers.add_parser("run", help="build, flash, reset, and monitor")
    run.add_argument("--example", default=None)
    run.add_argument("--adapter", default=None)
    run.add_argument("--no-monitor", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--timeout", type=float, default=30.0)
    run.set_defaults(handler=handle_run)

    return parser


def doctor_module_handler(args: argparse.Namespace) -> int:
    return doctor.run_doctor(args)


def openocd_flash_handler(args: argparse.Namespace) -> int:
    if args.example:
        try:
            apply_example_flash_defaults(args)
        except ConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    return openocd_flash.run(args)


def handle_placeholder(args: argparse.Namespace) -> int:
    command = args.command or "help"
    print(f"EmbedForge: '{command}' command is registered but not implemented yet.")
    return 0


def example_dir(example: str | None) -> Path:
    if example:
        return REPO_ROOT / "examples" / example
    return Path.cwd()


def apply_example_flash_defaults(args: argparse.Namespace) -> None:
    project_dir = example_dir(args.example)
    config = load_project_config(project_dir)
    artifact = get_nested(config, "flash.artifact", get_nested(config, "build.artifact", "build/app.elf"))
    args.file = args.file or str(project_dir / artifact)
    args.adapter = args.adapter or get_nested(config, "flash.adapter", "cmsis-dap")
    args.target = args.target or get_nested(config, "flash.target", "stm32f103")
    args.scripts_dir = args.scripts_dir or resolve_project_path(project_dir, get_nested(config, "flash.scripts_dir", None))
    args.interface_cfg = args.interface_cfg or get_nested(config, "flash.interface_cfg", None)
    args.target_cfg = args.target_cfg or get_nested(config, "flash.target_cfg", None)
    args.config = args.config or str(REPO_ROOT / "configs" / "openocd_targets.json")


def resolve_project_path(project_dir: Path, value: object | None) -> str | None:
    if value is None:
        return None
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return str(path)
    return str((project_dir / path).resolve())


def handle_reset(args: argparse.Namespace) -> int:
    project_dir = example_dir(args.example)
    try:
        config = load_project_config(project_dir)
    except ConfigError:
        config = {}
    flash_args = argparse.Namespace(
        adapter=args.adapter or get_nested(config, "flash.adapter", "cmsis-dap"),
        probe=None,
        target=get_nested(config, "flash.target", "stm32f103"),
        file=str(project_dir / get_nested(config, "flash.artifact", "build/app.elf")),
        address=None,
        openocd=None,
        scripts_dir=None,
        interface_cfg=None,
        target_cfg=None,
        config=str(REPO_ROOT / "configs" / "openocd_targets.json"),
        transport=None,
        speed=None,
        timeout=60.0,
        extra_cmd=[],
        dry_run=args.dry_run,
        verbose=False,
        verify=False,
        reset=True,
        exit=True,
        reset_only=True,
    )
    return openocd_flash.run_reset(flash_args)


def handle_monitor(args: argparse.Namespace) -> int:
    if args.no_monitor:
        print("UART: SKIPPED")
        return 0
    project_dir = example_dir(args.example)
    try:
        config = load_project_config(project_dir)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    port = get_nested(config, "serial.port", "/dev/ttyUSB0")
    baud = get_nested(config, "serial.baud", 115200)
    expect = get_nested(config, "serial.expect", [])
    timeout = getattr(args, "timeout", 30.0)
    return serial_expect(str(port), int(baud), list(expect), float(timeout))


def handle_run(args: argparse.Namespace) -> int:
    if not args.example:
        print("error: ./ef run currently requires --example for STM32 workflows", file=sys.stderr)
        return 2

    if not args.no_monitor:
        print("SDK CHECK:")
        sdk_status = sdk.check_stm32f1(sdk.resolve_stm32f1_path())
        if sdk_status != 0:
            print("RESULT: FAIL")
            return sdk_status

        doctor_status = doctor.run_stm32_doctor()
        if doctor_status != 0:
            print("RESULT: FAIL")
            return doctor_status

    build_status = cmake_build.run(
        argparse.Namespace(command="build", target=None, example=args.example, dry_run=args.dry_run)
    )
    print(f"BUILD: {'OK' if build_status == 0 else 'FAIL'}")
    if build_status != 0:
        print("RESULT: FAIL")
        return build_status

    flash_args = argparse.Namespace(
        command="flash",
        example=args.example,
        adapter=args.adapter,
        probe=None,
        target=None,
        file=None,
        address=None,
        openocd=None,
        scripts_dir=None,
        interface_cfg=None,
        target_cfg=None,
        config=None,
        transport=None,
        speed=None,
        timeout=60.0,
        extra_cmd=[],
        dry_run=args.dry_run,
        verbose=False,
        verify=True,
        reset=True,
        exit=True,
    )
    flash_status = openocd_flash_handler(flash_args)
    print(f"FLASH: {'OK' if flash_status == 0 else 'FAIL'}")
    if flash_status != 0:
        print("RESULT: FAIL")
        return flash_status

    reset_status = handle_reset(argparse.Namespace(example=args.example, adapter=args.adapter, dry_run=args.dry_run))
    print(f"RESET: {'OK' if reset_status == 0 else 'FAIL'}")
    if reset_status != 0:
        print("RESULT: FAIL")
        return reset_status

    uart_status = 0 if args.no_monitor else handle_monitor(
        argparse.Namespace(example=args.example, no_monitor=False, timeout=args.timeout)
    )
    print(f"UART: {'SKIPPED' if args.no_monitor or uart_status == 0 else 'FAIL'}")
    print(f"RESULT: {'PASS' if uart_status == 0 else 'FAIL'}")
    return uart_status


def serial_expect(port: str, baud: int, expected: list[str], timeout: float) -> int:
    if not Path(port).exists():
        print(f"error: serial port not found: {port}", file=sys.stderr)
        return 1
    if not expected:
        print(f"Serial monitor opened without expect patterns: {port} @ {baud}")
        return 0

    baud_const = baud_to_termios(baud)
    if baud_const is None:
        print(f"error: unsupported baud rate: {baud}", file=sys.stderr)
        return 2

    matched: set[str] = set()
    buffer = ""
    deadline = time.monotonic() + timeout

    old_attrs = None
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as exc:
        print(f"error: failed to open serial port {port}: {exc}", file=sys.stderr)
        return 1

    try:
        old_attrs = termios.tcgetattr(fd)
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = baud_const
        attrs[5] = baud_const
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], 0.2)
            if not readable:
                continue
            chunk = os.read(fd, 1024).decode("utf-8", errors="replace")
            if chunk:
                print(chunk, end="")
                buffer += chunk
                for item in expected:
                    if item in buffer:
                        matched.add(item)
                if len(matched) == len(expected):
                    print("UART: OK")
                    return 0
        missing = [item for item in expected if item not in matched]
        print(f"error: serial expect timeout; missing: {', '.join(missing)}", file=sys.stderr)
        return 1
    finally:
        if old_attrs is not None:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
            except OSError:
                pass
        os.close(fd)


def baud_to_termios(baud: int) -> int | None:
    return {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
    }.get(baud)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
