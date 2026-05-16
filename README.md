# EmbedForge

[中文说明](README.zh-CN.md)

Deployment: [English](docs/deployment.md) / [中文](docs/deployment.zh-CN.md)

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
./ef flash --adapter cmsis-dap --target stm32f103 --file build/app.hex
./ef reset
./ef monitor
./ef run
```

## Quick Start

```bash
chmod +x ef
./ef doctor
```

## OpenOCD Flash Quick Start

EmbedForge includes an OpenOCD flash backend for adapter + target + firmware workflows.
The intended abstraction is:

```text
Build artifact: build/app.hex
Adapter: cmsis-dap -> interface/cmsis-dap.cfg
Transport: swd
Target: stm32f103 -> target/stm32f1x.cfg
Action: program artifact verify reset exit
```

Generate and inspect the OpenOCD command without touching hardware:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run \
  --verbose
```

Flash an STM32F103 through DAPLink / CMSIS-DAP:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex
```

Flash an STM32F407 through ST-Link:

```bash
./ef flash \
  --adapter stlink \
  --target stm32f407 \
  --file build/app.elf
```

Raw `.bin` files do not contain a flash address, so pass `--address` explicitly:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.bin \
  --address 0x08000000
```

OpenOCD scripts are discovered in this order:

1. `--scripts-dir`
2. `OPENOCD_SCRIPTS`
3. `/opt/openocd-git/share/openocd/scripts`
4. `/usr/local/share/openocd/scripts`
5. `/usr/share/openocd/scripts`

Adapter and target mappings live in `configs/openocd_targets.json` and can be extended without changing the Python flash backend.
MSPM0 support is detected from the installed OpenOCD scripts directory; if no MSPM0 target cfg exists, use TI SDK, UniFlash, a vendor OpenOCD fork, or pass `--target-cfg`.

See [docs/openocd_flash.md](docs/openocd_flash.md) for details.

## OpenOCD Git Setup

EmbedForge expects OpenOCD to be built from the upstream Git `master` branch and installed under `/opt/openocd-git`.
The apt repository package may be useful for distribution defaults, but it is not the recommended EmbedForge deployment state.

```bash
./scripts/setup_openocd_git.sh
./ef doctor
```

If `./ef doctor` only shows `/usr/bin/openocd`, that is not the recommended EmbedForge OpenOCD setup. Run `./scripts/setup_openocd_git.sh` to install the Git build and wrapper.

The standalone OpenOCD wrapper is also available:

```bash
python3 tools/openocd_flash.py \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run
```
