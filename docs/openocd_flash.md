# OpenOCD Flashing

OpenOCD flashing needs four pieces of information:

- Firmware file: `.hex`, `.elf`, or `.bin`
- Interface cfg: for example `interface/cmsis-dap.cfg`
- Target cfg: for example `target/stm32f1x.cfg`
- Program action: for example `program firmware.hex verify reset exit`

EmbedForge maps adapter and target names to OpenOCD cfg files, then generates the OpenOCD command.

## Firmware Formats

- `.hex` contains flash addresses.
- `.elf` contains flash addresses and symbol/debug information.
- `.bin` is raw bytes and does not contain an address. You must pass `--address`, for example `0x08000000` for many STM32 parts.

## DAPLink And SWD

DAPLink usually exposes CMSIS-DAP. It is normally used with SWD, not JTAG.

Typical SWD wiring:

- `SWDIO`
- `SWCLK`
- `GND`
- `VTref` / target `3V3` reference
- `NRST` optional, but recommended

## Examples

DAPLink / CMSIS-DAP flashing STM32F103 `.hex`:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/output.hex \
  --speed 1000 \
  --verify \
  --reset \
  --exit
```

ST-Link flashing STM32F407 `.elf`:

```bash
./ef flash \
  --adapter stlink \
  --target stm32f407 \
  --file build/app.elf \
  --verify \
  --reset \
  --exit
```

DAPLink flashing raw `.bin`:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.bin \
  --address 0x08000000 \
  --verify \
  --reset \
  --exit
```

Dry-run command generation:

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/output.hex \
  --dry-run \
  --verbose
```

Standalone wrapper:

```bash
python3 tools/openocd_flash.py \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/output.hex \
  --dry-run
```

## Scripts Directory

EmbedForge searches OpenOCD scripts in this order:

1. `--scripts-dir`
2. `OPENOCD_SCRIPTS`
3. `/opt/openocd-git/share/openocd/scripts`
4. `/usr/local/share/openocd/scripts`
5. `/usr/share/openocd/scripts`

If OpenOCD was built by `scripts/setup_openocd_git.sh`, the expected scripts directory is:

```text
/opt/openocd-git/share/openocd/scripts
```

## Common Issues

If CMSIS-DAP is not found, check:

- DAPLink is plugged in.
- `lsusb` shows the probe.
- OpenOCD udev rules are installed.
- The probe has been unplugged and replugged after udev changes.
- Avoid using `sudo openocd` as a long-term fix.

If a target cfg is missing, the current OpenOCD install may not support that chip yet. Pass `--target-cfg` manually or use a newer/vendor OpenOCD.

MSPM0 support is detected from the actual OpenOCD scripts directory. If `target/ti_mspm0.cfg` or `target/mspm0.cfg` is missing, use TI SDK, UniFlash, a vendor fork, or pass `--target-cfg`.

If `.bin` flashing fails before OpenOCD starts, check that `--address` is present and looks like `0x08000000`.
