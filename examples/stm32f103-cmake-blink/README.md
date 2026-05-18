# STM32F103 CMake Blink

Minimal STM32F103C8T6 HAL blink project for EmbedForge.

This example does not vendor STM32CubeF1. Install it externally and point
`STM32CUBE_F1_PATH` at the SDK root:

```sh
./ef sdk install stm32f1
export STM32CUBE_F1_PATH=~/SDK/STM32/STM32CubeF1
./ef build --example stm32f103-cmake-blink
./ef flash --example stm32f103-cmake-blink --adapter cmsis-dap --dry-run
```

The default LED pin is `PC13`, which matches common STM32F103C8T6 blue-pill
boards. UART output is intentionally optional in this first-stage template.
