# EmbedForge

[English](README.md)

部署文档：[中文](docs/deployment.zh-CN.md) / [English](docs/deployment.md)

EmbedForge 是一个嵌入式开发自动化工具链，目标是在 Linux 环境下提供统一的 CLI 入口，串起编译、烧录、复位、串口日志和后续回归测试流程。

当前主要面向 Ubuntu 24.x，重点支持：

- 通过 Wine 调用 Windows Keil C51 / C251 / ARM 编译器
- 后续接入 CMake / GCC 工具链
- 使用 OpenOCD + DAPLink / ST-Link / J-Link 烧录
- 烧录后复位目标板
- 为串口日志和自动化回归测试预留结构

## 命令入口

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

## 示例模板

当前仓库内置的可复制模板：

- `examples/stm32f103-cmake-blink`：STM32F103C8T6 / CMake / GCC / PC13 1 秒闪烁。
- `examples/mspm0-openocd-blink`：TI MSPM0G3507 / CMake / GCC / DriverLib LED 闪烁。

模板只包含源码、CMake、链接脚本和 EmbedForge 配置；SDK、OpenOCD、Keil、Wine 和构建产物不进 Git。

## 快速开始

```bash
chmod +x ef
./ef doctor
```

`doctor` 会检查 Wine、Keil、OpenOCD、USB 和串口环境。

查看可安装 SDK：

```bash
./ef sdk list
```

安装 STM32CubeF1：

```bash
./ef sdk install stm32f1
```

安装 TI MSPM0 SDK：

```bash
./ef sdk install mspm0
```

## OpenOCD Git 版安装

EmbedForge 推荐使用 OpenOCD 上游 Git `master` 分支构建版本，不把 apt 仓库里的 OpenOCD 作为主要部署基线。发行版包通常较旧，遇到新芯片支持时更容易缺 cfg 或驱动。

安装 Git 版 OpenOCD：

```bash
./scripts/setup_openocd_git.sh
./ef doctor
```

默认安装位置：

```text
/opt/openocd-git
```

wrapper：

```text
~/.local/bin/openocd-git
```

如果 `./ef doctor` 只看到 `/usr/bin/openocd`，说明还不是推荐的 Git 版 OpenOCD 状态。

## OpenOCD 烧录快速开始

EmbedForge 的 OpenOCD 烧录模型不是单芯片脚本，而是可扩展后端：

```text
Build artifact: build/app.hex
Adapter: cmsis-dap -> interface/cmsis-dap.cfg
Transport: swd
Target: stm32f103 -> target/stm32f1x.cfg
Action: program artifact verify reset exit
```

先用 dry-run 检查命令生成，不接触硬件：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run \
  --verbose
```

使用 DAPLink / CMSIS-DAP 烧录 STM32F103：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex
```

使用 ST-Link 烧录 STM32F407：

```bash
./ef flash \
  --adapter stlink \
  --target stm32f407 \
  --file build/app.elf
```

烧录 `.bin` 时必须显式指定地址，因为 `.bin` 不包含烧录地址：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.bin \
  --address 0x08000000
```

也可以直接调用独立 wrapper：

```bash
python3 tools/openocd_flash.py \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run
```

## OpenOCD Scripts 路径

OpenOCD scripts 目录按以下顺序查找：

1. `--scripts-dir`
2. `OPENOCD_SCRIPTS`
3. `/opt/openocd-git/share/openocd/scripts`
4. `/usr/local/share/openocd/scripts`
5. `/usr/share/openocd/scripts`

如果你在 CI 或自定义环境中维护 OpenOCD，可以直接设置：

```bash
export OPENOCD_SCRIPTS=/opt/openocd-git/share/openocd/scripts
```

## 可扩展配置

adapter 和 target 映射在这里：

```text
configs/openocd_targets.json
```

新增芯片或调试器时，优先扩展配置，不要把逻辑写死进 Python 主流程。

当前内置 adapter：

- `cmsis-dap`
- `daplink`
- `stlink`
- `jlink`
- `ftdi`，需要手动指定具体 `--interface-cfg`

当前内置 target：

- `stm32f103` / `stm32f1` / `stm32f1x`
- `stm32f407` / `stm32f4` / `stm32f4x`
- `stm32g431` / `stm32g4` / `stm32g4x`
- `stm32h743` / `stm32h7` / `stm32h7x`
- `mspm0` / `mspm0g3507`，运行时检测 OpenOCD scripts 里是否真的存在 MSPM0 cfg

MSPM0 不假定一定支持。如果当前 OpenOCD 没有 `target/ti_mspm0.cfg` 或 `target/mspm0.cfg`，请使用 TI SDK、UniFlash、厂商 OpenOCD fork，或手动传 `--target-cfg`。

## 更多文档

- [部署文档](docs/deployment.zh-CN.md)
- [MSPM0 快速开始](docs/mspm0_quickstart.md)
- [OpenOCD 烧录说明](docs/openocd_flash.md)
- [OpenOCD Git 构建说明](docs/openocd.md)
- [Wine Keil 说明](docs/wine-keil.md)
- [架构说明](docs/architecture.md)
