from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embedforge.build import cmake


class CMakeBuildTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "project"
        (project / "cmake").mkdir(parents=True)
        (project / "embedforge.yaml").write_text(
            "\n".join(
                [
                    "sdk:",
                    "  env: STM32CUBE_F1_PATH",
                    "build:",
                    "  system: cmake",
                    "  generator: ninja",
                    "  build_dir: build",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (project / "cmake" / "arm-none-eabi.cmake").write_text("# toolchain\n", encoding="utf-8")
        return project

    def test_build_cmake_dry_run_does_not_call_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp))
            config = cmake.load_project_config(project)
            with mock.patch.dict("os.environ", {"STM32CUBE_F1_PATH": "/tmp/STM32CubeF1"}), mock.patch(
                "subprocess.run"
            ) as run:
                self.assertEqual(cmake.build_cmake_project(project, config, dry_run=True), 0)
            run.assert_not_called()

    def test_build_cmake_invokes_configure_then_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp))
            config = cmake.load_project_config(project)
            completed = argparse.Namespace(returncode=0)
            with mock.patch.dict("os.environ", {"STM32CUBE_F1_PATH": "/tmp/STM32CubeF1"}), mock.patch(
                "subprocess.run", return_value=completed
            ) as run:
                self.assertEqual(cmake.build_cmake_project(project, config, dry_run=False), 0)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0][:3], ["cmake", "-S", "."])
            self.assertEqual(run.call_args_list[1].args[0], ["cmake", "--build", "build"])

    def test_build_cmake_uses_configured_sdk_env_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp))
            (project / "embedforge.yaml").write_text(
                "\n".join(
                    [
                        "sdk:",
                        "  type: ti-mspm0",
                        "  family: mspm0",
                        "  env: MSPM0_SDK_PATH",
                        "build:",
                        "  system: cmake",
                        "  generator: ninja",
                        "  build_dir: build",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = cmake.load_project_config(project)
            completed = argparse.Namespace(returncode=0)
            with mock.patch.dict("os.environ", {"MSPM0_SDK_PATH": "/tmp/mspm0-sdk"}), mock.patch(
                "subprocess.run", return_value=completed
            ) as run:
                self.assertEqual(cmake.build_cmake_project(project, config, dry_run=False), 0)
            configure = run.call_args_list[0].args[0]
            self.assertIn("-DMSPM0_SDK_PATH=/tmp/mspm0-sdk", configure)
            self.assertEqual(run.call_args_list[0].kwargs["env"]["MSPM0_SDK_PATH"], "/tmp/mspm0-sdk")

    def test_non_cmake_target_remains_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp))
            with mock.patch("embedforge.build.cmake.resolve_project_dir", return_value=project):
                args = argparse.Namespace(target="c51", example=None, dry_run=True)
                self.assertEqual(cmake.run(args), 0)


if __name__ == "__main__":
    unittest.main()
