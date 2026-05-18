# STM32F103 Quickstart

## Ubuntu 24 Dependencies

```sh
sudo apt update
sudo apt install -y \
  git build-essential \
  cmake ninja-build \
  gcc-arm-none-eabi binutils-arm-none-eabi \
  gdb-multiarch openocd \
  python3 python3-pip python3-venv
```

STM32CubeIDE, STM32CubeMX, and STM32CubeCLT are not required for this workflow.

## Install STM32CubeF1

Manual install:

```sh
mkdir -p ~/SDK/STM32
cd ~/SDK/STM32
git clone --recursive https://github.com/STMicroelectronics/STM32CubeF1.git
```

Or use EmbedForge:

```sh
./ef sdk install stm32f1
```

## Environment

```sh
export STM32CUBE_F1_PATH=~/SDK/STM32/STM32CubeF1
```

Optional shell startup:

```sh
echo 'export STM32CUBE_F1_PATH=~/SDK/STM32/STM32CubeF1' >> ~/.bashrc
```

## Check

```sh
./ef doctor --stm32
./ef sdk check stm32f1
```

## Build

```sh
./ef build --example stm32f103-cmake-blink
```

Expected outputs:

```text
examples/stm32f103-cmake-blink/build/app.elf
examples/stm32f103-cmake-blink/build/app.hex
examples/stm32f103-cmake-blink/build/app.bin
examples/stm32f103-cmake-blink/build/app.map
```

## Flash

Dry-run:

```sh
./ef flash --example stm32f103-cmake-blink --adapter cmsis-dap --dry-run
```

Real hardware:

```sh
./ef flash --example stm32f103-cmake-blink --adapter cmsis-dap
./ef flash --example stm32f103-cmake-blink --adapter stlink
```

## Run

Without serial:

```sh
./ef run --example stm32f103-cmake-blink --no-monitor
```

With serial connected:

```sh
./ef run --example stm32f103-cmake-blink
```
