from __future__ import annotations

import argparse
import ast
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embedforge.flash import openocd


class OpenOCDFlashTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.scripts = self.root / "scripts"
        for path in [
            "interface/cmsis-dap.cfg",
            "interface/stlink.cfg",
            "interface/jlink.cfg",
            "target/stm32f1x.cfg",
            "target/stm32f4x.cfg",
            "target/stm32g4x.cfg",
            "target/stm32h7x.cfg",
        ]:
            target = self.scripts / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# cfg\n", encoding="utf-8")
        self.firmware = self.root / "build output.hex"
        self.firmware.write_text(":00000001FF\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def args(self, **overrides: object) -> argparse.Namespace:
        data = {
            "adapter": "cmsis-dap",
            "probe": None,
            "target": "stm32f103",
            "file": str(self.firmware),
            "address": None,
            "openocd": "openocd",
            "scripts_dir": str(self.scripts),
            "interface_cfg": None,
            "target_cfg": None,
            "config": None,
            "transport": None,
            "speed": None,
            "timeout": 60.0,
            "extra_cmd": [],
            "dry_run": False,
            "verbose": False,
            "verify": True,
            "reset": True,
            "exit": True,
        }
        data.update(overrides)
        return argparse.Namespace(**data)

    def test_hex_does_not_need_address(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        self.assertIn(f"program {{{self.firmware}}} verify reset exit", plan.command)

    def test_elf_does_not_need_address(self) -> None:
        elf = self.root / "app.elf"
        elf.write_text("elf\n", encoding="utf-8")
        plan = openocd.build_flash_plan(self.args(file=str(elf)))
        self.assertIn(f"program {{{elf}}} verify reset exit", plan.command)

    def test_bin_without_address_fails(self) -> None:
        bin_file = self.root / "app.bin"
        bin_file.write_bytes(b"\x00")
        with self.assertRaises(openocd.OpenOCDError):
            openocd.build_flash_plan(self.args(file=str(bin_file)))

    def test_bin_address_must_be_hex(self) -> None:
        bin_file = self.root / "app.bin"
        bin_file.write_bytes(b"\x00")
        with self.assertRaises(openocd.OpenOCDError):
            openocd.build_flash_plan(self.args(file=str(bin_file), address="08000000"))

    def test_cmsis_dap_mapping(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        self.assertEqual(plan.interface_cfg, "interface/cmsis-dap.cfg")

    def test_stm32f103_mapping(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        self.assertEqual(plan.target_cfg, "target/stm32f1x.cfg")

    def test_dry_run_does_not_call_subprocess(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        with mock.patch("subprocess.run") as run, mock.patch(
            "embedforge.flash.openocd.check_openocd_available"
        ) as check:
            result = openocd.run_openocd(plan, dry_run=True)
        self.assertEqual(result, 0)
        run.assert_not_called()
        check.assert_not_called()

    def test_custom_cfg_overrides_mapping(self) -> None:
        custom_interface = self.scripts / "interface/custom.cfg"
        custom_target = self.scripts / "target/custom.cfg"
        custom_interface.write_text("# custom\n", encoding="utf-8")
        custom_target.write_text("# custom\n", encoding="utf-8")
        plan = openocd.build_flash_plan(
            self.args(interface_cfg="interface/custom.cfg", target_cfg="target/custom.cfg")
        )
        self.assertEqual(plan.interface_cfg, "interface/custom.cfg")
        self.assertEqual(plan.target_cfg, "target/custom.cfg")

    def test_scripts_dir_beats_env(self) -> None:
        missing = self.root / "missing"
        with mock.patch.dict(os.environ, {"OPENOCD_SCRIPTS": str(missing)}):
            plan = openocd.build_flash_plan(self.args())
        self.assertEqual(plan.scripts_dir, self.scripts)

    def test_env_scripts_dir_used_before_defaults(self) -> None:
        with mock.patch.dict(os.environ, {"OPENOCD_SCRIPTS": str(self.scripts)}):
            plan = openocd.build_flash_plan(self.args(scripts_dir=None))
        self.assertEqual(plan.scripts_dir, self.scripts)

    def test_timeout_expired_returns_124(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        with mock.patch("embedforge.flash.openocd.check_openocd_available"), mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(plan.command, 60.0)
        ):
            self.assertEqual(openocd.run_openocd(plan, dry_run=False), 124)

    def test_permission_error_gets_human_hint(self) -> None:
        plan = openocd.build_flash_plan(self.args())
        completed = subprocess.CompletedProcess(
            plan.command,
            1,
            stdout="",
            stderr="Error: unable to open CMSIS-DAP device 0xd28:0x204\nhidapi open failed\n",
        )
        stderr = io.StringIO()
        with mock.patch("embedforge.flash.openocd.check_openocd_available"), mock.patch(
            "subprocess.run", return_value=completed
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(openocd.run_openocd(plan, dry_run=False), 1)
        hint = stderr.getvalue()
        self.assertIn("current user does not have USB/HID access", hint)
        self.assertIn("Avoid using sudo openocd", hint)
        self.assertIn("Temporary chmod", hint)

    def test_default_openocd_prefers_user_local_install(self) -> None:
        local_openocd = self.root / ".local/openocd-git/bin/openocd"
        local_openocd.parent.mkdir(parents=True)
        local_openocd.write_text("#!/bin/sh\n", encoding="utf-8")
        local_openocd.chmod(0o755)
        with mock.patch.object(Path, "home", return_value=self.root):
            self.assertEqual(openocd.resolve_openocd_executable(None), str(local_openocd))

    def test_firmware_path_with_closing_brace_fails(self) -> None:
        bad = self.root / "bad}.hex"
        bad.write_text(":00000001FF\n", encoding="utf-8")
        with self.assertRaises(openocd.OpenOCDError):
            openocd.build_flash_plan(self.args(file=str(bad)))

    def test_mspm0_missing_cfg_fails_clearly(self) -> None:
        with self.assertRaises(openocd.OpenOCDError) as ctx:
            openocd.build_flash_plan(self.args(target="mspm0"))
        self.assertIn("MSPM0", str(ctx.exception))

    def test_flash_cli_code_does_not_call_sudo_or_chmod(self) -> None:
        for source_path in [
            Path("src/embedforge/flash/openocd.py"),
            Path("src/embedforge/cli.py"),
        ]:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "run":
                    continue
                if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
                    continue
                if not node.args or not isinstance(node.args[0], ast.List) or not node.args[0].elts:
                    continue
                first = node.args[0].elts[0]
                if isinstance(first, ast.Constant):
                    self.assertNotIn(first.value, {"sudo", "chmod"})


if __name__ == "__main__":
    unittest.main()
