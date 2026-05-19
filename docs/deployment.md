# Deployment Guide

This guide describes how to move EmbedForge to a new machine and verify that the toolchain is usable.

The primary supported host is Ubuntu 24.x. Other Linux distributions are best-effort because package names, Wine behavior, udev rules, and OpenOCD locations can differ.

## Portability Assessment

The Python side is intentionally portable:

- Python runtime requirement is `>=3.10`.
- Runtime Python dependencies are empty in `pyproject.toml`.
- The default CLI entry point is `./ef`, which sets `PYTHONPATH` to the local `src` tree.
- OpenOCD flashing is configured by adapter, target, scripts directory, and firmware path rather than a board-specific script.
- `--scripts-dir`, `OPENOCD_SCRIPTS`, `--openocd`, `--interface-cfg`, and `--target-cfg` allow host-specific overrides.

The less portable parts are host toolchains and hardware access:

- Keil is a Windows toolchain and must be installed or mounted separately.
- Wine behavior depends on host packages and the Keil installation.
- OpenOCD Git builds need native build dependencies and sudo for `/opt/openocd-git`.
- USB debug probes need udev rules and user group permissions.
- Serial ports depend on actual hardware and device names under `/dev`.

## Host Prerequisites

Install the base tools:

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip \
  wine usbutils
```

`usbutils` provides `lsusb`, which `./ef doctor` uses for USB visibility checks.

Optional but useful for editable Python installation:

```bash
python3 -m pip install --user -e .
```

This installs the `ef` console script from `pyproject.toml`. The repository-local `./ef` script remains the recommended zero-install entry point.

## Clone And First Check

```bash
git clone https://github.com/B0weny-qwq/EmbedForge.git
cd EmbedForge
chmod +x ef scripts/*.sh tools/*.py
./ef doctor --example stm32f103-cmake-blink
./ef doctor --example mspm0-openocd-blink
```

`doctor --example` checks the CMake, GCC, SDK, OpenOCD cfg, USB, and serial items required by that example and prints copyable fixes. Hardware items are warnings so build setup can still be validated without a connected board.

## Keil And Wine

EmbedForge expects Keil to be available to Wine. The default path is:

```text
/mnt/win/Keil_v5
```

For a different location, set:

```bash
export EMBEDFORGE_KEIL_ROOT=/path/to/Keil_v5
```

Verify Wine:

```bash
wine --version
```

Verify EmbedForge can see Keil tools:

```bash
./ef doctor --legacy-keil
```

Keil installers, license files, and Windows-side setup are not distributed by this repository. Keep those machine-specific details outside the repo and point EmbedForge to the installed Keil root.

## OpenOCD Git Build

EmbedForge prefers a Git build of OpenOCD instead of the distribution package because upstream support for new chips often lands before distro packages update.

Install OpenOCD from upstream Git:

```bash
./scripts/setup_openocd_git.sh
```

Expected install layout:

```text
/opt/openocd-git/bin/openocd
/opt/openocd-git/share/openocd/scripts
/opt/openocd-git/EMBEDFORGE_BUILD_INFO
~/.local/bin/openocd-git
```

Verify:

```bash
/opt/openocd-git/bin/openocd --version
~/.local/bin/openocd-git --version
./ef doctor
```

If OpenOCD is installed somewhere else:

```bash
export OPENOCD_SCRIPTS=/path/to/openocd/scripts
./ef flash \
  --openocd /path/to/openocd \
  --scripts-dir /path/to/openocd/scripts \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run
```

OpenOCD scripts are discovered in this order:

1. `--scripts-dir`
2. `OPENOCD_SCRIPTS`
3. `/opt/openocd-git/share/openocd/scripts`
4. `/usr/local/share/openocd/scripts`
5. `/usr/share/openocd/scripts`

## USB And Probe Permissions

OpenOCD needs permission to access debug probes.

The Git setup script installs OpenOCD udev rules when `contrib/60-openocd.rules` exists, reloads rules, and adds the current user to `plugdev`.

After installing rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then unplug and replug the debug probe. You may need to log out and log in again for group membership changes to take effect.

Check USB visibility:

```bash
lsusb
./ef doctor
```

Avoid using `sudo openocd` as a long-term solution. Fix udev rules and group permissions instead.

## Flash Validation

Start with dry-run command generation:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run \
  --verbose
```

Flash through DAPLink / CMSIS-DAP:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex
```

Flash through ST-Link:

```bash
./ef flash \
  --adapter stlink \
  --target stm32f407 \
  --file build/app.elf
```

Raw `.bin` files require an explicit address:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.bin \
  --address 0x08000000
```

MSPM0 support is detected from the actual OpenOCD scripts directory. If `target/ti_mspm0.cfg` or `target/mspm0.cfg` is not present, use TI SDK, UniFlash, a vendor OpenOCD fork, or pass `--target-cfg`.

## Configuration Portability

OpenOCD adapter and target mappings live in:

```text
configs/openocd_targets.json
```

Prefer extending this JSON file over hardcoding chip or probe logic in Python.

For one-off boards or vendor forks, pass explicit cfg paths:

```bash
./ef flash \
  --interface-cfg interface/cmsis-dap.cfg \
  --target-cfg target/stm32f1x.cfg \
  --file build/app.hex \
  --dry-run
```

For Keil root portability:

```bash
export EMBEDFORGE_KEIL_ROOT=/path/to/Keil_v5
```

For OpenOCD executable portability:

```bash
export EMBEDFORGE_OPENOCD=/opt/openocd-git/bin/openocd
```

`EMBEDFORGE_OPENOCD` is currently used by `./ef doctor`; flashing uses `--openocd`.

## CI Or No-Hardware Validation

CI should not assume hardware is attached. Recommended checks:

```bash
python3 -m compileall src tools tests/test_openocd_flash.py
PYTHONPATH=src python3 -m unittest discover -s tests
./ef flash --example stm32f103-cmake-blink --dry-run --verbose
./ef flash --example mspm0-openocd-blink --dry-run --verbose
```

Use real flashing only in a hardware-in-the-loop runner with known USB topology and udev setup.

## Troubleshooting

`Keil root not found`

Set `EMBEDFORGE_KEIL_ROOT` to the actual Keil installation root.

`OpenOCD git build not found`

Run `./scripts/setup_openocd_git.sh`, or pass `--openocd` and `--scripts-dir` to the flash command.

`cmsis-dap.cfg not found`

Check `OPENOCD_SCRIPTS`, pass `--scripts-dir`, or install a complete OpenOCD scripts tree.

`unable to find a matching CMSIS-DAP device`

Check wiring, `lsusb`, udev rules, group membership, and replug the probe.

`.bin does not contain a flash address`

Pass `--address`, for example `--address 0x08000000` for many STM32 parts.

`MSPM0 target cfg missing`

The current OpenOCD scripts do not include MSPM0 support. Use TI SDK, UniFlash, a vendor fork, or pass `--target-cfg`.
