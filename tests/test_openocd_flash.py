from __future__ import annotations

import argparse
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
        with mock.patch("subprocess.run") as run:
            result = openocd.run_openocd(plan, dry_run=True)
        self.assertEqual(result, 0)
        run.assert_not_called()

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

    def test_firmware_path_with_closing_brace_fails(self) -> None:
        bad = self.root / "bad}.hex"
        bad.write_text(":00000001FF\n", encoding="utf-8")
        with self.assertRaises(openocd.OpenOCDError):
            openocd.build_flash_plan(self.args(file=str(bad)))

    def test_mspm0_missing_cfg_fails_clearly(self) -> None:
        with self.assertRaises(openocd.OpenOCDError) as ctx:
            openocd.build_flash_plan(self.args(target="mspm0"))
        self.assertIn("MSPM0", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
