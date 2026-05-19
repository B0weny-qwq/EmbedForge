# 部署文档

本文说明如何把 EmbedForge 迁移到一台新机器，并验证工具链是否可用。

当前主要支持 Ubuntu 24.x。其他 Linux 发行版可以尝试，但包名、Wine 行为、udev 规则和 OpenOCD 安装路径可能不同。

## 可移植性评估

Python 侧可移植性较好：

- Python 要求是 `>=3.10`。
- `pyproject.toml` 中没有运行时 Python 依赖。
- 默认入口是仓库内的 `./ef`，它会自动把本地 `src` 加进 `PYTHONPATH`。
- OpenOCD 烧录按 adapter、target、scripts 目录和 firmware 路径配置，不是单板硬编码脚本。
- `--scripts-dir`、`OPENOCD_SCRIPTS`、`--openocd`、`--interface-cfg`、`--target-cfg` 可以覆盖不同机器的差异。

不够可移植的部分主要来自宿主机工具链和硬件访问：

- Keil 是 Windows 工具链，必须由用户单独安装或挂载。
- Wine 行为取决于宿主机包版本和 Keil 安装状态。
- OpenOCD Git 构建需要原生编译依赖；默认安装到 `~/.local/openocd-git` 不需要 sudo，只有选择 `/opt/openocd-git` 时才需要 sudo。
- USB 调试器需要 udev 规则和用户组权限。
- 串口设备依赖实际硬件和 `/dev` 下的设备名。

## 宿主机基础依赖

安装基础工具：

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip \
  wine usbutils
```

`usbutils` 提供 `lsusb`，`./ef doctor` 会用它检查 USB 可见性。

如果希望安装 `ef` 到用户环境，可以执行：

```bash
python3 -m pip install --user -e .
```

不过推荐优先使用仓库自带的零安装入口：

```bash
./ef
```

## 克隆项目并首次检查

```bash
git clone https://github.com/B0weny-qwq/EmbedForge.git
cd EmbedForge
chmod +x ef scripts/*.sh tools/*.py
./ef doctor --example stm32f103-cmake-blink
./ef doctor --example mspm0-openocd-blink
```

`doctor --example` 会按示例工程配置检查实际需要的 CMake、GCC、SDK、OpenOCD cfg、USB 和串口项，并输出可复制的修复命令。硬件相关项通常是 WARN，不阻塞无硬件机器上的构建准备。

## Keil 与 Wine

EmbedForge 通过 Wine 调用 Keil。默认 Keil 根目录是：

```text
/mnt/win/Keil_v5
```

如果你的 Keil 在其他位置，设置：

```bash
export EMBEDFORGE_KEIL_ROOT=/path/to/Keil_v5
```

验证 Wine：

```bash
wine --version
```

验证 EmbedForge 是否能看到 Keil 工具：

```bash
./ef doctor --legacy-keil
```

Keil 安装包、授权文件和 Windows 侧安装状态不由本仓库分发。建议把这些机器相关内容放在仓库外，只通过环境变量告诉 EmbedForge Keil 根目录。

## OpenOCD Git 版部署

EmbedForge 推荐使用 OpenOCD 上游 Git 构建版本，而不是发行版 apt 包。新芯片支持通常先进入上游，发行版包可能较旧。

安装 OpenOCD Git 版：

```bash
./scripts/setup_openocd_git.sh
```

默认安装到用户目录。如果明确要安装到 `/opt/openocd-git`，使用：

```bash
./scripts/setup_openocd_git.sh --system
```

预期安装布局：

```text
~/.local/openocd-git/bin/openocd
~/.local/openocd-git/share/openocd/scripts
~/.local/openocd-git/EMBEDFORGE_BUILD_INFO
```

EmbedForge 的 `build` / `flash` / `run` 主流程应在普通用户权限下运行。CLI 不会自动调用 `sudo`，也不会自动 `chmod /dev/bus/usb`、安装 udev rules、修改用户组或写入 `/opt`。

如果用户选择安装到 `/opt/openocd-git`，那是安装阶段的系统配置行为，需要由用户手动授权；运行 `./ef flash` 时不应依赖 sudo。

验证：

```bash
~/.local/openocd-git/bin/openocd --version
./ef doctor
./ef doctor --stm32
```

如果 OpenOCD 安装在自定义位置：

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

OpenOCD scripts 目录查找顺序：

1. `--scripts-dir`
2. `OPENOCD_SCRIPTS`
3. `~/.local/openocd-git/share/openocd/scripts`
4. `/opt/openocd-git/share/openocd/scripts`
5. `/usr/local/share/openocd/scripts`
6. `/usr/share/openocd/scripts`

OpenOCD 可执行文件默认查找顺序：

1. `--openocd`
2. `~/.local/openocd-git/bin/openocd`
3. `/opt/openocd-git/bin/openocd`
4. `PATH` 中的 `openocd`

## USB 与调试器权限

OpenOCD 需要有权限访问调试器。

`scripts/setup_openocd_git.sh` 默认不会自动安装 udev rules，也不会自动修改用户组。它会在 OpenOCD 源码存在 `contrib/60-openocd.rules` 时打印需要手动执行的命令。

需要 sudo 的阶段：

- `sudo apt install` 安装系统依赖。
- `sudo cp ... /etc/udev/rules.d/` 安装 udev rules。
- `sudo usermod -aG plugdev "$USER"` 配置调试器访问用户组。
- `sudo chmod a+rw /dev/bus/usb/... /dev/hidrawX` 临时救急。
- `sudo make install` 安装到 `/opt/openocd-git`，如果用户选择 `/opt` 安装。

不需要 sudo 的阶段：

- `./ef build`
- `./ef flash --dry-run`
- `./ef flash`
- `./ef run`
- `make install` 到 `~/.local/openocd-git`

安装 rules 后可以手动执行：

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

然后拔插调试器。用户组权限变更后，可能需要注销并重新登录。

检查 USB 可见性：

```bash
lsusb
./ef doctor
./ef doctor --stm32
```

如果 DAPLink / CMSIS-DAP 重新枚举，`/dev/bus/usb/001/010` 这类设备号会变化，之前临时放开的权限也会失效。救急时可以手动执行：

```bash
sudo chmod a+rw /dev/bus/usb/001/010 /dev/hidraw9
```

其中 `001/010` 和 `hidraw9` 必须替换为当前机器实际设备。这个命令只适合临时救急，不应写入 EmbedForge 的自动流程。

不建议长期用 `sudo openocd` 解决权限问题。正确做法是修好 udev rules 和用户组权限。EmbedForge 只做诊断和提示，不自动 sudo 修复系统权限。

## 烧录验证

先 dry-run，只检查命令生成：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex \
  --dry-run \
  --verbose
```

使用 DAPLink / CMSIS-DAP 烧录：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.hex
```

使用 ST-Link 烧录：

```bash
./ef flash \
  --adapter stlink \
  --target stm32f407 \
  --file build/app.elf
```

烧录原始 `.bin` 文件必须指定地址：

```bash
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file build/app.bin \
  --address 0x08000000
```

MSPM0 支持会从实际 OpenOCD scripts 目录检测。如果不存在 `target/ti_mspm0.cfg` 或 `target/mspm0.cfg`，请使用 TI SDK、UniFlash、厂商 OpenOCD fork，或手动传 `--target-cfg`。

## 配置可移植性

OpenOCD adapter 和 target 映射位于：

```text
configs/openocd_targets.json
```

新增芯片或调试器时，优先扩展 JSON 配置，不要把逻辑写死进 Python。

对单次实验板或厂商 fork，可以直接传 cfg：

```bash
./ef flash \
  --interface-cfg interface/cmsis-dap.cfg \
  --target-cfg target/stm32f1x.cfg \
  --file build/app.hex \
  --dry-run
```

Keil 根目录可移植配置：

```bash
export EMBEDFORGE_KEIL_ROOT=/path/to/Keil_v5
```

OpenOCD 可执行文件可移植配置：

```bash
export EMBEDFORGE_OPENOCD=/opt/openocd-git/bin/openocd
```

注意：`EMBEDFORGE_OPENOCD` 当前用于 `./ef doctor`。实际烧录命令使用 `--openocd` 指定。

## CI 或无硬件验证

CI 不应默认假设接了硬件。推荐检查：

```bash
python3 -m compileall src tools tests/test_openocd_flash.py
PYTHONPATH=src python3 -m unittest discover -s tests
./ef flash --example stm32f103-cmake-blink --dry-run --verbose
./ef flash --example mspm0-openocd-blink --dry-run --verbose
```

真实烧录应放在硬件在环 runner 中执行，并固定 USB 拓扑和 udev 环境。

## 常见问题

`Keil root not found`

设置 `EMBEDFORGE_KEIL_ROOT` 到实际 Keil 安装根目录。

`OpenOCD git build not found`

运行 `./scripts/setup_openocd_git.sh`，或在烧录命令中传 `--openocd` 和 `--scripts-dir`。

`cmsis-dap.cfg not found`

检查 `OPENOCD_SCRIPTS`，传 `--scripts-dir`，或安装完整的 OpenOCD scripts 树。

`unable to find a matching CMSIS-DAP device`

检查接线、`lsusb`、udev rules、用户组权限，并拔插调试器。

`unable to open CMSIS-DAP device 0xd28:0x204`

DAPLink 已插入，但当前用户通常没有 USB/HID 权限。检查 `lsusb` 是否能看到 `0d28:0204`，检查 `/dev/bus/usb/...` 和 `/dev/hidrawX` 权限。推荐安装 OpenOCD udev rules 并加入 `plugdev`，然后注销重新登录并拔插调试器。临时 `sudo chmod a+rw /dev/bus/usb/... /dev/hidrawX` 只适合救急，DAPLink 重新枚举后设备号会变化。

`.bin does not contain a flash address`

传 `--address`，例如很多 STM32 使用 `--address 0x08000000`。

`MSPM0 target cfg missing`

当前 OpenOCD scripts 不包含 MSPM0 支持。使用 TI SDK、UniFlash、厂商 fork，或手动传 `--target-cfg`。
