from __future__ import annotations

import contextlib
import io
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


if __name__ == "__main__":
    unittest.main()
