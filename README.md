# EmbedForge

EmbedForge is an embedded development automation toolkit.

The project is designed to provide one command entry point for common embedded workflows:

- `build`: compile projects with Keil C51, Keil C251, Keil ARM, or future CMake/GCC flows.
- `flash`: program firmware through OpenOCD or other programmer backends.
- `reset`: reset or control a target through the selected debug probe.
- `monitor`: open a serial monitor and prepare for log parsing.
- `doctor`: check the local toolchain, Wine, Keil, OpenOCD, and serial environment.

Initial command shape:

```bash
./ef doctor
./ef build
./ef build --target c51
./ef build --target c251
./ef build --target keil-arm
./ef build --target cmake-arm
./ef flash --probe daplink
./ef reset
./ef monitor
./ef run
```

## Quick Start

```bash
chmod +x ef
./ef doctor
```

## OpenOCD Git Setup

EmbedForge expects OpenOCD to be built from the upstream Git `master` branch and installed under `/opt/openocd-git`.
The apt repository package may be useful for distribution defaults, but it is not the recommended EmbedForge deployment state.

```bash
./scripts/setup_openocd_git.sh
./ef doctor
```

If `./ef doctor` only shows `/usr/bin/openocd`, that is not the recommended EmbedForge OpenOCD setup. Run `./scripts/setup_openocd_git.sh` to install the Git build and wrapper.

This repository currently contains the project skeleton and placeholder extension points.
