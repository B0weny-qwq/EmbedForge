from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embedforge import sdk


class SdkTests(unittest.TestCase):
    def test_cli_path_accepts_sdk_root(self) -> None:
        path = sdk.resolve_stm32f1_path("/tmp/sdk-root")
        self.assertEqual(path.path, Path("/tmp/sdk-root") / "STM32CubeF1")
        self.assertEqual(path.source, "--path")

    def test_cli_path_accepts_cube_directory(self) -> None:
        path = sdk.resolve_stm32f1_path("/tmp/STM32CubeF1")
        self.assertEqual(path.path, Path("/tmp/STM32CubeF1"))

    def test_env_path_beats_default_root(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"STM32CUBE_F1_PATH": "/tmp/cube", "EMBEDFORGE_SDK_ROOT": "/tmp/root"},
            clear=False,
        ):
            path = sdk.resolve_stm32f1_path()
        self.assertEqual(path.path, Path("/tmp/cube"))
        self.assertEqual(path.source, "STM32CUBE_F1_PATH")

    def test_mspm0_cli_path_accepts_sdk_root(self) -> None:
        path = sdk.resolve_mspm0_path("/tmp/sdk-root")
        self.assertEqual(path.path, Path("/tmp/sdk-root") / "mspm0-sdk")
        self.assertEqual(path.source, "--path")

    def test_mspm0_env_path_beats_default_root(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"MSPM0_SDK_PATH": "/tmp/mspm0", "EMBEDFORGE_SDK_ROOT": "/tmp/root"},
            clear=False,
        ):
            path = sdk.resolve_mspm0_path()
        self.assertEqual(path.path, Path("/tmp/mspm0"))
        self.assertEqual(path.source, "MSPM0_SDK_PATH")

    def test_check_stm32f1_requires_expected_sdk_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "STM32CubeF1"
            for relative in sdk.STM32F1_REQUIRED_PATHS:
                (root / relative).mkdir(parents=True, exist_ok=True)
            self.assertEqual(sdk.check_stm32f1(sdk.SdkPath(root, "test")), 0)

    def test_check_mspm0_requires_expected_sdk_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "mspm0-sdk"
            for relative in sdk.MSPM0_REQUIRED_PATHS:
                path = root / relative
                if path.suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# file\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            self.assertEqual(sdk.check_mspm0(sdk.SdkPath(root, "test")), 0)

    def test_install_dry_run_does_not_create_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "SDK" / "STM32CubeF1"
            self.assertEqual(sdk.install_stm32f1(sdk.SdkPath(root, "test"), dry_run=True), 0)
            self.assertFalse(root.exists())

    def test_install_mspm0_dry_run_does_not_create_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "SDK" / "mspm0-sdk"
            self.assertEqual(sdk.install_mspm0(sdk.SdkPath(root, "test"), dry_run=True), 0)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
