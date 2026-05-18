# MSPM0G3507 CMake Blink

Minimal MSPM0G3507 no-RTOS blink project for EmbedForge.

This example uses TI MSPM0 SDK DriverLib through CMake/GCC. It does not use
Wine or Keil for the build path.

The blink pin is `GPIOB.22`, which is `USER_LED_1` on LP_MSPM0G3507
(`IOMUX_PINCM50`, package pin 21).

Install and check the SDK:

```sh
./ef sdk install mspm0
./ef sdk check mspm0
export MSPM0_SDK_PATH=~/SDK/TI/mspm0-sdk
```

Build:

```sh
./ef build --example mspm0-openocd-blink
```

Dry-run flash command generation:

```sh
./ef flash --example mspm0-openocd-blink --adapter cmsis-dap --dry-run --verbose
```

Real MSPM0 flashing depends on OpenOCD MSPM0 target cfg support. If your
OpenOCD scripts do not include `target/ti_mspm0.cfg` or `target/mspm0.cfg`,
use TI tooling, UniFlash, a vendor OpenOCD fork, or pass a working
`--target-cfg` explicitly.
