from __future__ import annotations

import argparse
import unittest
from unittest import mock

from embedforge import cli


class RunnerTests(unittest.TestCase):
    def test_run_uses_example_doctor_not_stm32_sdk_check(self) -> None:
        args = argparse.Namespace(example="mspm0-openocd-blink", adapter=None, no_monitor=False, dry_run=True, timeout=1.0)
        with mock.patch("embedforge.cli.doctor.run_example_doctor", return_value=0) as project_doctor, mock.patch(
            "embedforge.cli.sdk.check_stm32f1"
        ) as stm32_check, mock.patch(
            "embedforge.cli.cmake_build.run", return_value=0
        ), mock.patch(
            "embedforge.cli.openocd_flash_handler", return_value=0
        ), mock.patch(
            "embedforge.cli.handle_reset", return_value=0
        ), mock.patch(
            "embedforge.cli.handle_monitor", return_value=0
        ):
            self.assertEqual(cli.handle_run(args), 0)

        project_doctor.assert_called_once_with("mspm0-openocd-blink")
        stm32_check.assert_not_called()

    def test_example_flash_defaults_resolve_interface_cfg_mapping(self) -> None:
        args = argparse.Namespace(
            example="stm32f103-cmake-blink",
            file=None,
            adapter=None,
            target=None,
            scripts_dir=None,
            interface_cfg=None,
            target_cfg=None,
            config=None,
        )
        cli.apply_example_flash_defaults(args)
        self.assertEqual(args.interface_cfg, "interface/cmsis-dap.cfg")
        self.assertIsInstance(args.interface_cfg, str)
        self.assertTrue(args.scripts_dir.endswith("configs/openocd"))


if __name__ == "__main__":
    unittest.main()
