from __future__ import annotations

import contextlib
import io
import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from embedforge import doctor
from embedforge.probe import CommandResult


class DoctorTests(unittest.TestCase):
    def test_daplink_lsusb_detection(self) -> None:
        result = CommandResult(
            cmd=["lsusb"],
            returncode=0,
            stdout="Bus 001 Device 010: ID 0d28:0204 NXP ARM mbed\n",
            stderr="",
            error=None,
        )
        with mock.patch("embedforge.doctor.run_command", return_value=result):
            self.assertIn("FOUND", doctor.check_daplink_lsusb())

    def test_stm32_doctor_only_reports_permission_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sdk = Path(temp) / "STM32CubeF1"
            sdk.mkdir()
            lsusb = CommandResult(
                cmd=["lsusb"],
                returncode=0,
                stdout="Bus 001 Device 010: ID 0d28:0204 NXP ARM mbed\n",
                stderr="",
                error=None,
            )
            output = io.StringIO()
            with mock.patch("embedforge.doctor.shutil.which", return_value="/usr/bin/tool"), mock.patch(
                "embedforge.doctor.resolve_openocd_tool", return_value="/home/user/.local/openocd-git/bin/openocd"
            ), mock.patch(
                "embedforge.doctor.resolve_openocd_scripts_dir",
                return_value="/home/user/.local/openocd-git/share/openocd/scripts",
            ), mock.patch(
                "embedforge.doctor.resolve_stm32f1_path", return_value=SimpleNamespace(path=sdk)
            ), mock.patch(
                "embedforge.doctor.STM32F1_REQUIRED_PATHS", []
            ), mock.patch(
                "embedforge.doctor.check_daplink_lsusb", return_value="FOUND (" + lsusb.stdout.strip() + ")"
            ), mock.patch(
                "embedforge.doctor.user_in_group", return_value=False
            ), contextlib.redirect_stdout(output):
                self.assertEqual(doctor.run_stm32_doctor(), 0)

            text = output.getvalue()
            self.assertIn("openocd: OK (/home/user/.local/openocd-git/bin/openocd)", text)
            self.assertIn("openocd scripts: OK (/home/user/.local/openocd-git/share/openocd/scripts)", text)
            self.assertIn("DAPLink/CMSIS-DAP lsusb: FOUND", text)
            self.assertIn("current user in plugdev: NO", text)
            self.assertIn("doctor never runs sudo or changes the system", text)

    def test_example_doctor_reports_missing_stm32_sdk_fix(self) -> None:
        output = io.StringIO()
        with mock.patch("embedforge.doctor.shutil.which", return_value="/usr/bin/tool"), mock.patch(
            "embedforge.doctor.resolve_stm32f1_path",
            return_value=SimpleNamespace(path=Path("/missing/STM32CubeF1")),
        ), mock.patch(
            "embedforge.doctor.resolve_openocd_scripts_dir",
            return_value=str(doctor.REPO_ROOT / "configs" / "openocd"),
        ), mock.patch(
            "embedforge.doctor.check_daplink_lsusb", return_value="NOT FOUND"
        ), mock.patch(
            "embedforge.doctor.user_in_group", return_value=False
        ), contextlib.redirect_stdout(output):
            self.assertEqual(doctor.run_example_doctor("stm32f103-cmake-blink"), 1)

        text = output.getvalue()
        self.assertIn("STM32CubeF1", text)
        self.assertIn("./ef sdk install stm32f1", text)
        self.assertNotIn("wine", text.lower())
        self.assertNotIn("Keil C51", text)

    def test_example_doctor_reports_mspm0_target_cfg_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sdk = Path(temp) / "mspm0-sdk"
            for relative in doctor.MSPM0_REQUIRED_PATHS:
                path = sdk / relative
                if Path(relative).suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# file\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)

            scripts = Path(temp) / "scripts"
            (scripts / "interface").mkdir(parents=True)
            (scripts / "interface" / "cmsis-dap.cfg").write_text("# cfg\n", encoding="utf-8")

            output = io.StringIO()
            with mock.patch("embedforge.doctor.shutil.which", return_value="/usr/bin/tool"), mock.patch(
                "embedforge.doctor.resolve_mspm0_path", return_value=SimpleNamespace(path=sdk)
            ), mock.patch(
                "embedforge.doctor.resolve_project_path", return_value=str(scripts)
            ), mock.patch(
                "embedforge.doctor.check_daplink_lsusb", return_value="NOT FOUND"
            ), mock.patch(
                "embedforge.doctor.user_in_group", return_value=False
            ), contextlib.redirect_stdout(output):
                self.assertEqual(doctor.run_example_doctor("mspm0-openocd-blink"), 1)

            text = output.getvalue()
            self.assertIn("OpenOCD target cfg", text)
            self.assertIn("MSPM0 support", text)
            self.assertIn("UniFlash", text)

    def test_doctor_default_points_to_example_flow(self) -> None:
        output = io.StringIO()
        args = argparse.Namespace(example=None, stm32=False, legacy_keil=False, all=False)
        with contextlib.redirect_stdout(output):
            self.assertEqual(doctor.run_doctor(args), 0)
        self.assertIn("./ef doctor --example stm32f103-cmake-blink", output.getvalue())


if __name__ == "__main__":
    unittest.main()
