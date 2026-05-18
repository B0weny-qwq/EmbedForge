"""OpenOCD flashing backend for EmbedForge."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SCRIPTS_DIR_CANDIDATES = [
    "~/.local/openocd-git/share/openocd/scripts",
    "/opt/openocd-git/share/openocd/scripts",
    "/usr/local/share/openocd/scripts",
    "/usr/share/openocd/scripts",
]
DEFAULT_OPENOCD = "~/.local/openocd-git/bin/openocd"
FALLBACK_OPENOCD = "/opt/openocd-git/bin/openocd"
OPENOCD_PERMISSION_ERROR_KEYWORDS = (
    "unable to open CMSIS-DAP device",
    "access denied",
    "permission denied",
    "hidapi open failed",
    "LIBUSB_ERROR_ACCESS",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "default_speed": 1000,
    "default_scripts_dir_candidates": DEFAULT_SCRIPTS_DIR_CANDIDATES,
    "adapters": {
        "cmsis-dap": {"interface": "interface/cmsis-dap.cfg", "default_transport": "swd"},
        "daplink": {"interface": "interface/cmsis-dap.cfg", "default_transport": "swd"},
        "stlink": {"interface": "interface/stlink.cfg", "default_transport": "swd"},
        "jlink": {"interface": "interface/jlink.cfg", "default_transport": "swd"},
        "ftdi": {"interface": None, "default_transport": "jtag", "requires_interface_cfg": True},
    },
    "targets": {
        "stm32f103": "target/stm32f1x.cfg",
        "stm32f1": "target/stm32f1x.cfg",
        "stm32f1x": "target/stm32f1x.cfg",
        "stm32f407": "target/stm32f4x.cfg",
        "stm32f4": "target/stm32f4x.cfg",
        "stm32f4x": "target/stm32f4x.cfg",
        "stm32g431": "target/stm32g4x.cfg",
        "stm32g4": "target/stm32g4x.cfg",
        "stm32g4x": "target/stm32g4x.cfg",
        "stm32h743": "target/stm32h7x.cfg",
        "stm32h7": "target/stm32h7x.cfg",
        "stm32h7x": "target/stm32h7x.cfg",
        "mspm0": ["target/ti_mspm0.cfg", "target/mspm0.cfg"],
        "mspm0g3507": ["target/ti_mspm0.cfg", "target/mspm0.cfg"],
    },
}


class OpenOCDError(Exception):
    """User-facing OpenOCD setup or execution error."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class FlashPlan:
    """Resolved OpenOCD flash command and diagnostics."""

    command: list[str]
    scripts_dir: Path
    interface_cfg: str
    target_cfg: str
    firmware: Path
    transport: str
    speed: int
    timeout: float | None


def add_flash_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--example", default=None, help="example project name under examples/")
    parser.add_argument("--adapter", default=None, help="adapter name, such as cmsis-dap, daplink, stlink")
    parser.add_argument("--probe", default=None, help="alias for --adapter")
    parser.add_argument("--target", default=None, help="target name, such as stm32f103")
    parser.add_argument("--file", default=None, help="firmware file: .hex, .elf, or .bin")
    parser.add_argument("--address", default=None, help="load address required for .bin, for example 0x08000000")
    parser.add_argument("--openocd", default=None, help="OpenOCD executable path")
    parser.add_argument("--scripts-dir", default=None, help="OpenOCD scripts directory")
    parser.add_argument("--interface-cfg", default=None, help="OpenOCD interface cfg")
    parser.add_argument("--target-cfg", default=None, help="OpenOCD target cfg")
    parser.add_argument("--config", default=None, help="JSON config extending adapter and target mappings")
    parser.add_argument("--transport", default=None, help="OpenOCD transport, default comes from adapter")
    parser.add_argument("--speed", type=int, default=None, help="adapter speed in kHz")
    parser.add_argument("--timeout", type=float, default=60.0, help="OpenOCD timeout in seconds; 0 disables")
    parser.add_argument("--extra-cmd", action="append", default=[], help="extra OpenOCD -c command")
    parser.add_argument("--dry-run", action="store_true", help="print command without executing OpenOCD")
    parser.add_argument("--verbose", action="store_true", help="print resolved OpenOCD diagnostics")

    verify_group = parser.add_mutually_exclusive_group()
    verify_group.add_argument("--verify", dest="verify", action="store_true", default=True)
    verify_group.add_argument("--no-verify", dest="verify", action="store_false")

    reset_group = parser.add_mutually_exclusive_group()
    reset_group.add_argument("--reset", dest="reset", action="store_true", default=True)
    reset_group.add_argument("--no-reset", dest="reset", action="store_false")

    exit_group = parser.add_mutually_exclusive_group()
    exit_group.add_argument("--exit", dest="exit", action="store_true", default=True)
    exit_group.add_argument("--no-exit", dest="exit", action="store_false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flash firmware with OpenOCD")
    add_flash_arguments(parser)
    return parser


def load_config(config_path: str | None) -> dict[str, Any]:
    config = {
        "default_speed": DEFAULT_CONFIG["default_speed"],
        "default_scripts_dir_candidates": list(DEFAULT_CONFIG["default_scripts_dir_candidates"]),
        "adapters": dict(DEFAULT_CONFIG["adapters"]),
        "targets": dict(DEFAULT_CONFIG["targets"]),
    }
    if not config_path:
        return config

    path = Path(config_path)
    if not path.exists():
        raise OpenOCDError(f"OpenOCD config file not found: {path}")
    try:
        user_config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OpenOCDError(f"Invalid OpenOCD JSON config {path}: {exc}") from exc

    for key in ("adapters", "targets"):
        if key in user_config:
            if not isinstance(user_config[key], dict):
                raise OpenOCDError(f"OpenOCD config field '{key}' must be an object")
            config[key].update(user_config[key])
    if "default_speed" in user_config:
        config["default_speed"] = int(user_config["default_speed"])
    if "default_scripts_dir_candidates" in user_config:
        candidates = user_config["default_scripts_dir_candidates"]
        if not isinstance(candidates, list):
            raise OpenOCDError("OpenOCD config field 'default_scripts_dir_candidates' must be a list")
        config["default_scripts_dir_candidates"] = candidates
    return config


def resolve_scripts_dir(args: argparse.Namespace, config: dict[str, Any]) -> Path:
    candidates: list[tuple[str, str]] = []
    if args.scripts_dir:
        candidates.append(("--scripts-dir", args.scripts_dir))
    env_scripts = os.environ.get("OPENOCD_SCRIPTS")
    if env_scripts:
        candidates.append(("OPENOCD_SCRIPTS", env_scripts))
    candidates.extend(("default", item) for item in config["default_scripts_dir_candidates"])

    for source, item in candidates:
        path = Path(item).expanduser()
        if path.is_dir():
            return path
        if source == "--scripts-dir":
            raise OpenOCDError(
                f"OpenOCD scripts directory does not exist: {path}\n"
                "Check the path or omit --scripts-dir to use OPENOCD_SCRIPTS/default locations."
            )
        if source == "OPENOCD_SCRIPTS":
            raise OpenOCDError(
                f"OPENOCD_SCRIPTS points to a missing directory: {path}\n"
                "Fix OPENOCD_SCRIPTS, unset it, or pass --scripts-dir explicitly."
            )

    searched = "\n".join(f"  - {item}" for _, item in candidates)
    raise OpenOCDError(
        "OpenOCD scripts directory not found.\n"
        "Install OpenOCD, run scripts/setup_openocd_git.sh, set OPENOCD_SCRIPTS, or pass --scripts-dir.\n"
        f"Searched:\n{searched}"
    )


def resolve_cfg(scripts_dir: Path, cfg: str, kind: str) -> str:
    cfg_path = Path(cfg).expanduser()
    if cfg_path.is_absolute():
        if cfg_path.is_file():
            return str(cfg_path)
        raise OpenOCDError(f"OpenOCD {kind} cfg does not exist: {cfg_path}")

    if (scripts_dir / cfg_path).is_file():
        return cfg

    if kind == "interface" and cfg == "interface/cmsis-dap.cfg":
        raise OpenOCDError(
            f"OpenOCD interface cfg not found: {scripts_dir / cfg_path}\n"
            "Could not find cmsis-dap.cfg. Check your OpenOCD scripts directory or pass --scripts-dir."
        )
    raise OpenOCDError(
        f"OpenOCD {kind} cfg not found: {scripts_dir / cfg_path}\n"
        "The current OpenOCD install may not support this chip/debug adapter, or you may need "
        f"to pass --{kind}-cfg manually."
    )


def resolve_adapter(args: argparse.Namespace, config: dict[str, Any]) -> tuple[str, str]:
    adapter_name = args.adapter or args.probe
    if not adapter_name and not args.interface_cfg:
        raise OpenOCDError("Missing adapter. Pass --adapter cmsis-dap, --adapter stlink, or --interface-cfg.")

    adapters = config["adapters"]
    if args.interface_cfg:
        default_transport = "swd"
        if adapter_name and adapter_name in adapters:
            default_transport = adapters[adapter_name].get("default_transport", default_transport)
        return args.interface_cfg, args.transport or default_transport

    adapter = adapters.get(adapter_name)
    if not adapter:
        raise OpenOCDError(f"Unknown adapter '{adapter_name}'. Pass --interface-cfg to use a custom adapter.")
    if adapter.get("requires_interface_cfg") and not adapter.get("interface"):
        raise OpenOCDError(
            "FTDI adapters need a specific board/interface cfg. Pass --interface-cfg, for example "
            "one of the interface/ftdi/*.cfg files from your OpenOCD scripts directory."
        )
    return adapter["interface"], args.transport or adapter.get("default_transport", "swd")


def resolve_target_cfg(args: argparse.Namespace, config: dict[str, Any], scripts_dir: Path) -> str:
    if args.target_cfg:
        return args.target_cfg
    if not args.target:
        raise OpenOCDError("Missing target. Pass --target stm32f103 or --target-cfg target/<chip>.cfg.")

    target_value = config["targets"].get(args.target)
    if not target_value:
        raise OpenOCDError(f"Unknown target '{args.target}'. Pass --target-cfg to use a custom target.")

    if isinstance(target_value, list):
        for candidate in target_value:
            if (scripts_dir / candidate).is_file():
                return candidate
        if args.target in {"mspm0", "mspm0g3507"}:
            raise OpenOCDError(
                "Current OpenOCD scripts do not include an MSPM0 target cfg.\n"
                "This OpenOCD version may be too old or upstream support may be incomplete. "
                "Use TI SDK / UniFlash / a vendor OpenOCD fork, or pass --target-cfg manually."
            )
        raise OpenOCDError(f"No usable target cfg found for target '{args.target}'")

    return str(target_value)


def validate_firmware(path_text: str | None, require_exists: bool = True) -> Path:
    if not path_text:
        raise OpenOCDError("Missing firmware file. Pass --file build/app.elf or use --example.")
    path = Path(path_text).expanduser()
    if require_exists and not path.is_file():
        raise OpenOCDError(f"Firmware file not found: {path}")
    return path


def validate_bin_address(firmware: Path, address: str | None) -> str | None:
    if firmware.suffix.lower() != ".bin":
        return None
    if not address:
        raise OpenOCDError(
            "Raw .bin does not contain load address.\n"
            "Use:\n"
            "  --address 0x08000000"
        )
    if not address.lower().startswith("0x"):
        raise OpenOCDError("Invalid --address. Use a hexadecimal address with 0x prefix, for example 0x08000000.")
    try:
        int(address, 16)
    except ValueError as exc:
        raise OpenOCDError("Invalid --address. Use a hexadecimal address, for example 0x08000000.") from exc
    return address


def tcl_braced_path(path: Path) -> str:
    text = str(path)
    if "}" in text:
        raise OpenOCDError(
            "Firmware path contains '}', which cannot be safely wrapped for OpenOCD Tcl. "
            "Move or rename the firmware file."
        )
    return "{" + text + "}"


def build_program_command(args: argparse.Namespace, firmware: Path, address: str | None) -> str:
    parts = ["program", tcl_braced_path(firmware)]
    if address:
        parts.append(address)
    if args.verify:
        parts.append("verify")
    if args.reset:
        parts.append("reset")
    if args.exit:
        parts.append("exit")
    return " ".join(parts)


def build_flash_plan(args: argparse.Namespace) -> FlashPlan:
    config = load_config(args.config)
    firmware = validate_firmware(args.file, require_exists=not args.dry_run)
    address = validate_bin_address(firmware, args.address)
    scripts_dir = resolve_scripts_dir(args, config)
    interface_cfg, transport = resolve_adapter(args, config)
    target_cfg = resolve_target_cfg(args, config, scripts_dir)
    resolved_interface = resolve_cfg(scripts_dir, interface_cfg, "interface")
    resolved_target = resolve_cfg(scripts_dir, target_cfg, "target")
    speed = args.speed if args.speed is not None else int(config["default_speed"])
    timeout = None if args.timeout == 0 else args.timeout

    command = [
        resolve_openocd_executable(args.openocd),
        "-s",
        str(scripts_dir),
        "-f",
        resolved_interface,
        "-c",
        f"transport select {transport}",
        "-c",
        f"adapter speed {speed}",
        "-f",
        resolved_target,
    ]
    for extra_cmd in args.extra_cmd:
        command.extend(["-c", extra_cmd])
    command.extend(["-c", build_program_command(args, firmware, address)])

    return FlashPlan(
        command=command,
        scripts_dir=scripts_dir,
        interface_cfg=resolved_interface,
        target_cfg=resolved_target,
        firmware=firmware,
        transport=transport,
        speed=speed,
        timeout=timeout,
    )


def build_reset_plan(args: argparse.Namespace) -> FlashPlan:
    config = load_config(args.config)
    scripts_dir = resolve_scripts_dir(args, config)
    firmware = validate_firmware(args.file, require_exists=False)
    interface_cfg, transport = resolve_adapter(args, config)
    target_cfg = resolve_target_cfg(args, config, scripts_dir)
    resolved_interface = resolve_cfg(scripts_dir, interface_cfg, "interface")
    resolved_target = resolve_cfg(scripts_dir, target_cfg, "target")
    speed = args.speed if args.speed is not None else int(config["default_speed"])
    timeout = None if args.timeout == 0 else args.timeout
    command = [
        resolve_openocd_executable(args.openocd),
        "-s",
        str(scripts_dir),
        "-f",
        resolved_interface,
        "-c",
        f"transport select {transport}",
        "-c",
        f"adapter speed {speed}",
        "-f",
        resolved_target,
        "-c",
        "init; reset run; shutdown",
    ]
    return FlashPlan(
        command=command,
        scripts_dir=scripts_dir,
        interface_cfg=resolved_interface,
        target_cfg=resolved_target,
        firmware=firmware,
        transport=transport,
        speed=speed,
        timeout=timeout,
    )


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def print_verbose(plan: FlashPlan) -> None:
    print("OpenOCD diagnostics:")
    print(f"  scripts_dir: {plan.scripts_dir}")
    print(f"  interface_cfg: {plan.interface_cfg}")
    print(f"  target_cfg: {plan.target_cfg}")
    print(f"  firmware: {plan.firmware}")
    print(f"  transport: {plan.transport}")
    print(f"  speed: {plan.speed} kHz")
    print(f"  timeout: {'disabled' if plan.timeout is None else str(plan.timeout) + 's'}")


def check_openocd_available(openocd: str) -> None:
    path = Path(openocd).expanduser()
    if path.is_absolute() or len(path.parts) > 1:
        if path.is_file():
            return
    elif shutil.which(openocd):
        return
    raise OpenOCDError(
        "OpenOCD executable not found.\n"
        "Install OpenOCD under ~/.local/openocd-git, run scripts/setup_openocd_git.sh, "
        "or pass --openocd explicitly."
    )


def resolve_openocd_executable(openocd: str | None) -> str:
    if openocd:
        return openocd
    for candidate in [
        Path.home() / ".local/openocd-git/bin/openocd",
        Path(FALLBACK_OPENOCD),
    ]:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "openocd"


def is_openocd_permission_error(output: str) -> bool:
    output_lower = output.lower()
    return any(keyword.lower() in output_lower for keyword in OPENOCD_PERMISSION_ERROR_KEYWORDS)


def explain_openocd_failure(output: str) -> str:
    if is_openocd_permission_error(output):
        return (
            "\nDAPLink/CMSIS-DAP appears to be plugged in, but the current user does not have USB/HID access.\n"
            "- Avoid using sudo openocd as a long-term workaround.\n"
            "- Install OpenOCD udev rules and add your user to plugdev, then log out/in and replug the probe.\n"
            "- Temporary chmod on /dev/bus/usb/... and /dev/hidrawX is only for emergency recovery.\n"
            "- DAPLink can re-enumerate after reset, so /dev/bus/usb bus/device numbers can change."
        )
    if "unable to find a matching CMSIS-DAP device" in output:
        return (
            "\nDAPLink/CMSIS-DAP device was not found.\n"
            "- Check that DAPLink is plugged in.\n"
            "- Check lsusb output.\n"
            "- Check OpenOCD udev rules.\n"
            "- Unplug and replug the debug probe.\n"
            "- Avoid using sudo as a long-term OpenOCD workaround."
        )
    return ""


def run_openocd(plan: FlashPlan, dry_run: bool) -> int:
    print("OpenOCD command:")
    print(format_command(plan.command))
    if dry_run:
        return 0

    check_openocd_available(plan.command[0])
    try:
        result = subprocess.run(
            plan.command,
            shell=False,
            text=True,
            capture_output=True,
            timeout=plan.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"OpenOCD timed out after {plan.timeout} seconds.", file=sys.stderr)
        if exc.stdout:
            print("OpenOCD stdout:", file=sys.stderr)
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print("OpenOCD stderr:", file=sys.stderr)
            print(exc.stderr, file=sys.stderr)
        return 124

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        hint = explain_openocd_failure(combined)
        if hint:
            print(hint, file=sys.stderr)
    return result.returncode


def run(args: argparse.Namespace) -> int:
    try:
        plan = build_flash_plan(args)
        if args.verbose:
            print_verbose(plan)
        return run_openocd(plan, args.dry_run)
    except OpenOCDError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


def run_reset(args: argparse.Namespace) -> int:
    try:
        plan = build_reset_plan(args)
        return run_openocd(plan, args.dry_run)
    except OpenOCDError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


def main(argv: list[str] | argparse.Namespace | None = None) -> int:
    if isinstance(argv, argparse.Namespace):
        return run(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
