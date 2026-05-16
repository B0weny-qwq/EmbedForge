"""Environment doctor for EmbedForge."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import sys

from embedforge.probe import find_executable, run_command
from embedforge.util import Status, print_status, readiness


DEFAULT_KEIL_ROOT = "/mnt/win/Keil_v5"
DEFAULT_OPENOCD = "/opt/openocd-git/bin/openocd"
OPENOCD_BUILD_INFO = "/opt/openocd-git/EMBEDFORGE_BUILD_INFO"


def run_doctor(args: argparse.Namespace) -> int:
    del args

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

    opt_openocd = Path(DEFAULT_OPENOCD)
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
        print_status(Status.MISS, "OpenOCD git build", f"not found ({DEFAULT_OPENOCD})")

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
            f"{path_openocd} found, but EmbedForge requires git build at /opt/openocd-git",
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
    return "/opt/openocd-git" in str(path) or openocd_build_info_for(path).exists()


def openocd_build_info_for(path: Path) -> Path:
    candidates = [
        path.parent.parent / "EMBEDFORGE_BUILD_INFO",
        path.parent / "EMBEDFORGE_BUILD_INFO",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(OPENOCD_BUILD_INFO)


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
