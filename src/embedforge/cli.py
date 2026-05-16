#!/usr/bin/env python3
"""Command-line entry point for EmbedForge."""

from __future__ import annotations

import argparse
import sys

from embedforge import doctor
from embedforge.flash import openocd as openocd_flash


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ef", description="EmbedForge embedded automation toolkit")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="check local toolchain environment")
    doctor.set_defaults(handler=doctor_module_handler)

    build = subparsers.add_parser("build", help="build firmware")
    build.add_argument("--target", choices=["c51", "c251", "keil-arm", "cmake-arm"], default=None)
    build.set_defaults(handler=handle_placeholder)

    flash = subparsers.add_parser("flash", help="flash firmware")
    openocd_flash.add_flash_arguments(flash)
    flash.set_defaults(handler=openocd_flash_handler)

    for name, help_text in {
        "reset": "reset target",
        "monitor": "open serial monitor",
        "run": "build, flash, reset, and monitor",
    }.items():
        command = subparsers.add_parser(name, help=help_text)
        command.set_defaults(handler=handle_placeholder)

    return parser


def doctor_module_handler(args: argparse.Namespace) -> int:
    return doctor.run_doctor(args)


def openocd_flash_handler(args: argparse.Namespace) -> int:
    return openocd_flash.run(args)


def handle_placeholder(args: argparse.Namespace) -> int:
    command = args.command or "help"
    print(f"EmbedForge: '{command}' command is registered but not implemented yet.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
