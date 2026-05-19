"""Environment doctor for EmbedForge."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import grp
import os
from pathlib import Path
import platform
import shutil
import sys

from embedforge.core.config import ConfigError, get_nested, load_project_config
from embedforge.flash import openocd as openocd_flash
from embedforge.probe import find_executable, run_command
from embedforge.sdk import (
    MSPM0_REQUIRED_PATHS,
    STM32F1_REQUIRED_PATHS,
    SdkPath,
    resolve_mspm0_path,
    resolve_stm32f1_path,
)
from embedforge.util import Status, print_status, readiness


DEFAULT_KEIL_ROOT = "/mnt/win/Keil_v5"
DEFAULT_OPENOCD = "~/.local/openocd-git/bin/openocd"
FALLBACK_OPENOCD = "/opt/openocd-git/bin/openocd"
OPENOCD_BUILD_INFO = "~/.local/openocd-git/EMBEDFORGE_BUILD_INFO"
DEFAULT_OPENOCD_SCRIPTS = [
    "~/.local/openocd-git/share/openocd/scripts",
    "/opt/openocd-git/share/openocd/scripts",
    "/usr/local/share/openocd/scripts",
    "/usr/share/openocd/scripts",
]
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CheckResult:
    status: Status
    name: str
    detail: str
    required: bool = True
    fix: str | None = None


def run_doctor(args: argparse.Namespace) -> int:
    if getattr(args, "example", None):
        return run_example_doctor(args.example)
    if getattr(args, "stm32", False):
        return run_stm32_doctor()
    if getattr(args, "legacy_keil", False):
        return run_legacy_keil_doctor()
    if not getattr(args, "all", False):
        print("EmbedForge Doctor")
        print("=================")
        print("No project selected. For CMake-first workflows, run:")
        print("  ./ef doctor --example stm32f103-cmake-blink")
        print("  ./ef doctor --example mspm0-openocd-blink")
        print()
        print("Optional legacy Keil/Wine check:")
        print("  ./ef doctor --legacy-keil")
        return 0

    return run_legacy_keil_doctor()


def run_legacy_keil_doctor() -> int:

    keil_root = Path(os.environ.get("EMBEDFORGE_KEIL_ROOT", DEFAULT_KEIL_ROOT))
    openocd_override = os.environ.get("EMBEDFORGE_OPENOCD")

    print("EmbedForge Doctor")
    print("=================")
    print_status(Status.OK, "platform", platform.platform())
    print_status(Status.OK, "python", sys.version.split()[0])
    print()

    check_wine()
    print()

    keil_exists = keil_root.exists()
    print_status(Status.OK if keil_exists else Status.MISS, "Keil root", str(keil_root) if keil_exists else f"not found ({keil_root})")

    c51_found, c51_total = check_keil_group(
        "Keil C51",
        keil_root,
        {
            "C51": ["C51.EXE"],
            "A51": ["A51.EXE"],
            "BL51": ["BL51.EXE"],
            "LX51": ["LX51.EXE"],
            "OH51": ["OH51.EXE"],
            "OHX51": ["OHX51.EXE"],
        },
    )
    c251_found, c251_total = check_keil_group(
        "Keil C251",
        keil_root,
        {
            "C251": ["C251.EXE"],
            "A251": ["A251.EXE"],
            "L251": ["L251.EXE", "l251.exe"],
            "OH251": ["OH251.EXE"],
        },
    )
    arm_found, arm_total = check_keil_group(
        "Keil ARM",
        keil_root,
        {
            "armcc": ["armcc.exe"],
            "armclang": ["armclang.exe"],
            "armasm": ["armasm.exe"],
            "armlink": ["armlink.exe"],
            "fromelf": ["fromelf.exe"],
        },
    )

    print()
    openocd_state = check_openocd(openocd_override)

    print()
    check_usb()

    print()
    serial_ready = check_serial()

    print()
    print("Summary")
    print("-------")
    print_status(summary_status(c51_found, c51_total), "C51", readiness(c51_found, c51_total))
    print_status(summary_status(c251_found, c251_total), "C251", readiness(c251_found, c251_total))
    print_status(summary_status(arm_found, arm_total), "Keil ARM", readiness(arm_found, arm_total))
    print_status(openocd_summary_status(openocd_state), "OpenOCD", openocd_state)
    print_status(Status.OK if serial_ready else Status.MISS, "Serial", "ready" if serial_ready else "missing")
    return 0


def run_example_doctor(example: str) -> int:
    project_dir = REPO_ROOT / "examples" / example
    try:
        config = load_project_config(project_dir)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"EmbedForge Doctor: {example}")
    print("=" * (19 + len(example)))
    print_status(Status.OK, "platform", platform.platform())
    print_status(Status.OK, "python", sys.version.split()[0])
    print()

    results = check_example_project(project_dir, config)
    print_results("Required", [item for item in results if item.required])
    print_results("Optional / Hardware", [item for item in results if not item.required])

    failures = [item for item in results if item.required and item.status == Status.MISS]
    warnings = [item for item in results if item.required and item.status == Status.WARN]
    print()
    print("Summary")
    print("-------")
    if failures:
        print_status(Status.MISS, "example", f"blocked by {len(failures)} missing required item(s)")
        print_fixes(failures)
        return 1
    if warnings:
        print_status(Status.WARN, "example", f"ready with {len(warnings)} warning(s)")
        print_fixes(warnings)
        return 0
    print_status(Status.OK, "example", "ready")
    return 0


def check_example_project(project_dir: Path, config: dict[str, object]) -> list[CheckResult]:
    build_system = str(get_nested(config, "build.system", ""))
    if build_system != "cmake":
        return [
            CheckResult(
                Status.WARN,
                "build system",
                f"{build_system or 'missing'} is not covered by CMake-first doctor",
                required=False,
            )
        ]

    results: list[CheckResult] = []
    results.extend(check_required_tools())
    results.extend(check_project_sdk(config))
    results.extend(check_project_openocd(project_dir, config))
    results.extend(check_project_hardware(config))
    results.extend(check_project_serial(config))
    return results


def check_required_tools() -> list[CheckResult]:
    tools = [
        ("git", "sudo apt install -y git"),
        ("cmake", "sudo apt install -y cmake"),
        ("ninja", "sudo apt install -y ninja-build"),
        ("arm-none-eabi-gcc", "sudo apt install -y gcc-arm-none-eabi"),
        ("arm-none-eabi-objcopy", "sudo apt install -y binutils-arm-none-eabi"),
        ("arm-none-eabi-size", "sudo apt install -y binutils-arm-none-eabi"),
    ]
    results = []
    for tool, fix in tools:
        found = shutil.which(tool)
        results.append(
            CheckResult(
                Status.OK if found else Status.MISS,
                tool,
                found or "not found",
                fix=fix,
            )
        )
    return results


def check_project_sdk(config: dict[str, object]) -> list[CheckResult]:
    family = str(get_nested(config, "sdk.family", ""))
    sdk_type = str(get_nested(config, "sdk.type", ""))
    if family == "stm32f1" or sdk_type == "stm32cube":
        return check_sdk_layout("STM32CubeF1", resolve_stm32f1_path(), STM32F1_REQUIRED_PATHS, "  ./ef sdk install stm32f1")
    if family == "mspm0" or sdk_type in {"mspm0", "ti-mspm0"}:
        return check_sdk_layout("MSPM0 SDK", resolve_mspm0_path(), MSPM0_REQUIRED_PATHS, "  ./ef sdk install mspm0")
    return [
        CheckResult(
            Status.WARN,
            "SDK",
            f"unknown sdk family/type: family={family or 'unset'}, type={sdk_type or 'unset'}",
            fix="Configure sdk.family in embedforge.yaml or install SDK manually.",
        )
    ]


def check_sdk_layout(label: str, sdk: SdkPath, required_paths: list[str], install_command: str) -> list[CheckResult]:
    if not sdk.path.is_dir():
        return [
            CheckResult(
                Status.MISS,
                label,
                f"not found ({sdk.path})",
                fix=f"Run:\n{install_command}\nOr set the SDK environment variable to the installed SDK path.",
            )
        ]

    missing = [relative for relative in required_paths if not (sdk.path / relative).exists()]
    if missing:
        return [
            CheckResult(
                Status.MISS,
                label,
                f"incomplete ({sdk.path}); missing: {', '.join(missing)}",
                fix=f"Reinstall or fix the SDK layout. Suggested command:\n{install_command}",
            )
        ]
    return [CheckResult(Status.OK, label, str(sdk.path))]


def check_project_openocd(project_dir: Path, config: dict[str, object]) -> list[CheckResult]:
    if str(get_nested(config, "flash.backend", "openocd")) != "openocd":
        return [CheckResult(Status.WARN, "OpenOCD", "flash backend is not openocd", required=False)]

    results: list[CheckResult] = []
    openocd_exe = openocd_flash.resolve_openocd_executable(None)
    openocd_path = Path(openocd_exe).expanduser()
    openocd_found = openocd_path.is_file() if len(openocd_path.parts) > 1 else shutil.which(openocd_exe) is not None
    results.append(
        CheckResult(
            Status.OK if openocd_found else Status.MISS,
            "OpenOCD executable",
            str(openocd_path) if openocd_found else "not found",
            fix="Run:\n  ./scripts/setup_openocd_git.sh\nOr pass --openocd to flash commands.",
        )
    )

    scripts_value = get_nested(config, "flash.scripts_dir", None)
    scripts_dir = resolve_project_path(project_dir, scripts_value) if scripts_value is not None else resolve_openocd_scripts_dir()
    scripts_ok = bool(scripts_dir and Path(scripts_dir).is_dir())
    results.append(
        CheckResult(
            Status.OK if scripts_ok else Status.MISS,
            "OpenOCD scripts",
            str(scripts_dir) if scripts_ok else "not found",
            fix="Run ./scripts/setup_openocd_git.sh, set OPENOCD_SCRIPTS, or configure flash.scripts_dir.",
        )
    )

    if scripts_ok:
        results.extend(check_openocd_cfgs(Path(str(scripts_dir)), config))
    return results


def check_openocd_cfgs(scripts_dir: Path, config: dict[str, object]) -> list[CheckResult]:
    results: list[CheckResult] = []
    interface_cfg = get_nested(config, "flash.interface_cfg", None)
    if isinstance(interface_cfg, dict):
        adapter = str(get_nested(config, "flash.adapter", "cmsis-dap"))
        interface_cfg = interface_cfg.get(adapter)
    if not interface_cfg:
        adapter = str(get_nested(config, "flash.adapter", "cmsis-dap"))
        interface_cfg = openocd_flash.DEFAULT_CONFIG["adapters"].get(adapter, {}).get("interface")
    if interface_cfg:
        results.append(check_cfg_file(scripts_dir, str(interface_cfg), "OpenOCD interface cfg"))

    target_cfg = get_nested(config, "flash.target_cfg", None)
    if target_cfg:
        results.append(check_cfg_file(scripts_dir, str(target_cfg), "OpenOCD target cfg"))
    else:
        target = str(get_nested(config, "flash.target", ""))
        target_value = openocd_flash.DEFAULT_CONFIG["targets"].get(target)
        candidates = target_value if isinstance(target_value, list) else [target_value] if target_value else []
        if candidates:
            found = next((candidate for candidate in candidates if candidate and (scripts_dir / str(candidate)).is_file()), None)
            results.append(
                CheckResult(
                    Status.OK if found else Status.MISS,
                    "OpenOCD target cfg",
                    str(found) if found else "not found for " + target,
                    fix=target_cfg_fix(target),
                )
            )
    return results


def check_cfg_file(scripts_dir: Path, cfg: str, label: str) -> CheckResult:
    path = Path(cfg).expanduser()
    exists = path.is_file() if path.is_absolute() else (scripts_dir / path).is_file()
    return CheckResult(
        Status.OK if exists else Status.MISS,
        label,
        str(path if path.is_absolute() else scripts_dir / path) if exists else f"not found ({cfg})",
        fix=target_cfg_fix(cfg),
    )


def target_cfg_fix(target_or_cfg: str) -> str:
    if "mspm0" in target_or_cfg:
        return (
            "Current OpenOCD scripts may not include MSPM0 support. Use TI SDK / UniFlash / "
            "a vendor OpenOCD fork, or pass --target-cfg manually."
        )
    return "Check OPENOCD_SCRIPTS, run ./scripts/setup_openocd_git.sh, or pass --target-cfg/--interface-cfg."


def check_project_hardware(config: dict[str, object]) -> list[CheckResult]:
    adapter = str(get_nested(config, "flash.adapter", ""))
    if adapter not in {"cmsis-dap", "daplink"}:
        return []
    daplink_status = check_daplink_lsusb()
    status = Status.OK if daplink_status.startswith("FOUND") else Status.WARN
    plugdev_status = "YES" if user_in_group("plugdev") else "NO"
    return [
        CheckResult(
            status,
            "DAPLink/CMSIS-DAP lsusb",
            daplink_status,
            required=False,
            fix="Plug in the probe, install OpenOCD udev rules, add user to plugdev, then replug the probe.",
        ),
        CheckResult(
            Status.OK if plugdev_status == "YES" else Status.WARN,
            "plugdev group",
            plugdev_status,
            required=False,
            fix="sudo groupadd -f plugdev && sudo usermod -aG plugdev \"$USER\"; log out/in afterwards.",
        ),
    ]


def check_project_serial(config: dict[str, object]) -> list[CheckResult]:
    port = get_nested(config, "serial.port", None)
    if not port:
        return []
    path = Path(str(port))
    return [
        CheckResult(
            Status.OK if path.exists() else Status.WARN,
            "serial port",
            str(path) if path.exists() else f"not found ({path})",
            required=False,
            fix="Connect the board, update serial.port in embedforge.yaml, or run with --no-monitor.",
        )
    ]


def resolve_project_path(project_dir: Path, value: object) -> str:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return str(path)
    return str((project_dir / path).resolve())


def print_results(title: str, results: list[CheckResult]) -> None:
    if not results:
        return
    print(title)
    print("-" * len(title))
    for result in results:
        print_status(result.status, result.name, result.detail)
    print()


def print_fixes(results: list[CheckResult]) -> None:
    fixes = []
    for result in results:
        if result.fix and result.fix not in fixes:
            fixes.append(result.fix)
    if not fixes:
        return
    print()
    print("Suggested fixes")
    print("---------------")
    for fix in fixes:
        print(fix)


def run_stm32_doctor() -> int:
    tools = [
        "cmake",
        "ninja",
        "arm-none-eabi-gcc",
        "arm-none-eabi-objcopy",
        "arm-none-eabi-size",
        "git",
    ]
    missing: list[str] = []

    print("STM32 Toolchain:")
    for tool in tools:
        found = shutil.which(tool)
        print(f"  {tool}: {'OK' if found else 'MISSING'}")
        if not found:
            missing.append(tool)

    openocd = resolve_openocd_tool()
    scripts_dir = resolve_openocd_scripts_dir()
    print(f"  openocd: {'OK (' + openocd + ')' if openocd else 'MISSING'}")
    print(f"  openocd scripts: {'OK (' + scripts_dir + ')' if scripts_dir else 'MISSING'}")
    if not openocd:
        missing.append("openocd")
    if not scripts_dir:
        missing.append("openocd scripts")

    gdb = shutil.which("arm-none-eabi-gdb") or shutil.which("gdb-multiarch")
    print(f"  gdb: {'OK (' + gdb + ')' if gdb else 'MISSING'}")
    if not gdb:
        missing.append("arm-none-eabi-gdb or gdb-multiarch")

    sdk = resolve_stm32f1_path()
    sdk_missing = [relative for relative in STM32F1_REQUIRED_PATHS if not (sdk.path / relative).exists()]
    print()
    print("STM32 SDK:")
    print(f"  STM32CubeF1: {'OK' if not sdk_missing and sdk.path.is_dir() else 'MISSING'}")
    print(f"  path: {sdk.path}")

    if missing:
        print()
        print("Ubuntu 24 install:")
        print("sudo apt update")
        print("sudo apt install -y \\")
        print("  git build-essential \\")
        print("  cmake ninja-build \\")
        print("  gcc-arm-none-eabi binutils-arm-none-eabi \\")
        print("  gdb-multiarch openocd \\")
        print("  python3 python3-pip python3-venv")

    if sdk_missing or not sdk.path.is_dir():
        print()
        print("STM32CubeF1 SDK not found.")
        print("Run:")
        print("  ./ef sdk install stm32f1")
        print()
        print("Or set:")
        print("  export STM32CUBE_F1_PATH=~/SDK/STM32/STM32CubeF1")

    print()
    print("STM32 Probe Access:")
    daplink_status = check_daplink_lsusb()
    print(f"  DAPLink/CMSIS-DAP lsusb: {daplink_status}")
    plugdev_status = "YES" if user_in_group("plugdev") else "NO"
    print(f"  current user in plugdev: {plugdev_status}")
    print("  note: permission checks only provide guidance; doctor never runs sudo or changes the system.")

    return 0 if not missing and not sdk_missing and sdk.path.is_dir() else 1


def resolve_openocd_tool() -> str | None:
    for candidate in [
        Path(DEFAULT_OPENOCD).expanduser(),
        Path(FALLBACK_OPENOCD),
    ]:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    path_openocd = shutil.which("openocd")
    if path_openocd:
        return path_openocd
    return None


def resolve_openocd_scripts_dir() -> str | None:
    env_scripts = os.environ.get("OPENOCD_SCRIPTS")
    candidates = [env_scripts] if env_scripts else []
    candidates.extend(DEFAULT_OPENOCD_SCRIPTS)
    for item in candidates:
        path = Path(item).expanduser()
        if path.is_dir():
            return str(path)
    return None


def check_daplink_lsusb() -> str:
    result = run_command(["lsusb"])
    if not result.ok:
        return f"UNKNOWN ({result.error or first_line(result.stderr) or 'lsusb failed'})"
    if not result.stdout:
        return "NOT FOUND"
    matches = []
    for line in result.stdout.splitlines():
        lowered = line.lower()
        if "0d28:0204" in lowered or "cmsis-dap" in lowered or "daplink" in lowered or "nxp arm mbed" in lowered:
            matches.append(line)
    if not matches:
        return "NOT FOUND"
    return "FOUND (" + "; ".join(matches) + ")"


def user_in_group(group_name: str) -> bool:
    try:
        group_ids = set(os.getgroups())
        return grp.getgrnam(group_name).gr_gid in group_ids
    except KeyError:
        return False


def check_wine() -> None:
    which = run_command(["which", "wine"])
    if not which.ok:
        print_status(Status.MISS, "wine", "not found")
        return

    version = run_command(["wine", "--version"])
    if version.ok and version.stdout:
        print_status(Status.OK, "wine", version.stdout.splitlines()[0])
    else:
        detail = version.error or version.stderr or "version check failed"
        print_status(Status.WARN, "wine", f"{which.stdout} ({detail})")


def check_keil_group(title: str, root: Path, tools: dict[str, list[str]]) -> tuple[int, int]:
    print()
    print(title)
    found = 0
    for label, names in tools.items():
        path = find_executable(root, names)
        if path is None:
            print_status(Status.MISS, label, "not found")
            continue
        found += 1
        print_status(Status.OK, label, str(path))
    return found, len(tools)


def check_openocd(openocd_override: str | None) -> str:
    print("OpenOCD")
    ready = False
    partial = False

    if openocd_override:
        override_path = Path(openocd_override)
        if not override_path.exists():
            print_status(Status.MISS, "EMBEDFORGE_OPENOCD", f"not found ({openocd_override})")
        elif not os.access(override_path, os.X_OK):
            print_status(Status.WARN, "EMBEDFORGE_OPENOCD", f"not executable ({openocd_override})")
            partial = True
        else:
            result = run_command([openocd_override, "--version"])
            detail = first_line(result.stdout) or first_line(result.stderr) or openocd_override
            if result.ok and is_embedforge_openocd(override_path):
                print_status(Status.OK, "EMBEDFORGE_OPENOCD", detail)
                print_openocd_build_info(override_path)
                ready = True
            elif result.ok:
                print_status(Status.WARN, "EMBEDFORGE_OPENOCD", f"{detail}; not an EmbedForge-managed git build")
                partial = True
            else:
                print_status(Status.WARN, "EMBEDFORGE_OPENOCD", result.error or detail or "version check failed")
                partial = True

    opt_openocd = Path(DEFAULT_OPENOCD).expanduser()
    if opt_openocd.exists() and os.access(opt_openocd, os.X_OK):
        result = run_command([str(opt_openocd), "--version"])
        detail = first_line(result.stdout) or first_line(result.stderr) or str(opt_openocd)
        if result.ok:
            print_status(Status.OK, "OpenOCD git build", detail)
            print_openocd_build_info(opt_openocd)
            ready = True
        else:
            print_status(Status.WARN, "OpenOCD git build", result.error or detail or "version check failed")
            partial = True
    else:
        print_status(Status.MISS, "OpenOCD git build", f"not found ({opt_openocd})")

    fallback_openocd = Path(FALLBACK_OPENOCD)
    if fallback_openocd.exists() and os.access(fallback_openocd, os.X_OK):
        result = run_command([str(fallback_openocd), "--version"])
        detail = first_line(result.stdout) or first_line(result.stderr) or str(fallback_openocd)
        if result.ok:
            print_status(Status.OK, "OpenOCD /opt fallback", detail)
            print_openocd_build_info(fallback_openocd)
            ready = True
        else:
            print_status(Status.WARN, "OpenOCD /opt fallback", result.error or detail or "version check failed")
            partial = True
    else:
        print_status(Status.WARN, "OpenOCD /opt fallback", f"not found ({FALLBACK_OPENOCD})")

    local_wrapper = Path.home() / ".local/bin/openocd-git"
    if local_wrapper.exists() and os.access(local_wrapper, os.X_OK):
        result = run_command([str(local_wrapper), "--version"])
        detail = first_line(result.stdout) or first_line(result.stderr) or str(local_wrapper)
        if result.ok:
            print_status(Status.OK, "openocd-git wrapper", detail)
            ready = True
        else:
            print_status(Status.WARN, "openocd-git wrapper", result.error or detail or "version check failed")
            partial = True
    else:
        print_status(Status.WARN, "openocd-git wrapper", f"not found ({local_wrapper})")

    path_openocd_git = shutil.which("openocd-git")
    if path_openocd_git:
        result = run_command([path_openocd_git, "--version"])
        detail = first_line(result.stdout) or first_line(result.stderr) or path_openocd_git
        if result.ok:
            print_status(Status.OK, "PATH openocd-git", f"{path_openocd_git}; {detail}")
            ready = True
        else:
            print_status(Status.WARN, "PATH openocd-git", result.error or detail or "version check failed")
            partial = True
    else:
        print_status(Status.WARN, "PATH openocd-git", "not found")

    path_openocd = shutil.which("openocd")
    if path_openocd:
        print_status(
            Status.WARN,
            "OpenOCD",
            f"{path_openocd} found; user-local ~/.local/openocd-git is preferred",
        )
        partial = True
    elif not ready:
        print_status(Status.MISS, "OpenOCD", "missing")

    if ready:
        return "ready"
    if partial:
        return "partial"
    return "missing"


def is_embedforge_openocd(path: Path) -> bool:
    text = str(path)
    return "/.local/openocd-git" in text or "/opt/openocd-git" in text or openocd_build_info_for(path).exists()


def openocd_build_info_for(path: Path) -> Path:
    candidates = [
        path.parent.parent / "EMBEDFORGE_BUILD_INFO",
        path.parent / "EMBEDFORGE_BUILD_INFO",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(OPENOCD_BUILD_INFO).expanduser()


def print_openocd_build_info(path: Path) -> None:
    info = openocd_build_info_for(path)
    if not info.exists():
        return
    commit = ""
    for line in info.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("commit="):
            commit = line.split("=", 1)[1]
            break
    if commit:
        print_status(Status.OK, "OpenOCD commit", commit)


def openocd_summary_status(state: str) -> Status:
    if state == "ready":
        return Status.OK
    if state == "partial":
        return Status.WARN
    return Status.MISS


def check_usb() -> None:
    result = run_command(["lsusb"])
    if result.ok and result.stdout:
        print_status(Status.OK, "lsusb", "available")
        for line in result.stdout.splitlines():
            print(f"  {line}")
    elif result.ok:
        print_status(Status.WARN, "lsusb", "no USB devices listed")
    else:
        print_status(Status.WARN, "lsusb", result.error or first_line(result.stderr) or "not found")


def check_serial() -> bool:
    ports = sorted(Path("/dev").glob("ttyUSB*")) + sorted(Path("/dev").glob("ttyACM*"))
    if ports:
        print_status(Status.OK, "serial", ", ".join(str(port) for port in ports))
        return True
    print_status(Status.MISS, "serial", "no /dev/ttyUSB* or /dev/ttyACM* devices")
    return False


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def summary_status(found: int, total: int) -> Status:
    if found == total and total > 0:
        return Status.OK
    if found > 0:
        return Status.WARN
    return Status.MISS
