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
- OpenOCD Git 构建需要原生编译依赖，并需要 sudo 安装到 `/opt/openocd-git`。
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
./ef doctor
```

新机器上，`doctor` 报 Keil、OpenOCD、串口缺失是正常的，直到这些工具或硬件准备好。

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
./ef doctor
```

Keil 安装包、授权文件和 Windows 侧安装状态不由本仓库分发。建议把这些机器相关内容放在仓库外，只通过环境变量告诉 EmbedForge Keil 根目录。

## OpenOCD Git 版部署

EmbedForge 推荐使用 OpenOCD 上游 Git 构建版本，而不是发行版 apt 包。新芯片支持通常先进入上游，发行版包可能较旧。

安装 OpenOCD Git 版：

```bash
./scripts/setup_openocd_git.sh
```

预期安装布局：

```text
/opt/openocd-git/bin/openocd
/opt/openocd-git/share/openocd/scripts
/opt/openocd-git/EMBEDFORGE_BUILD_INFO
~/.local/bin/openocd-git
```

验证：

```bash
/opt/openocd-git/bin/openocd --version
~/.local/bin/openocd-git --version
./ef doctor
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
3. `/opt/openocd-git/share/openocd/scripts`
4. `/usr/local/share/openocd/scripts`
5. `/usr/share/openocd/scripts`

## USB 与调试器权限

OpenOCD 需要有权限访问调试器。

`scripts/setup_openocd_git.sh` 会在 OpenOCD 源码存在 `contrib/60-openocd.rules` 时安装 udev rules，reload rules，并把当前用户加入 `plugdev`。

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
```

不建议长期用 `sudo openocd` 解决权限问题。正确做法是修好 udev rules 和用户组权限。

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
./ef flash \
  --adapter cmsis-dap \
  --target stm32f103 \
  --file configs/openocd/target/stm32f1x.cfg \
  --scripts-dir configs/openocd \
  --dry-run \
  --verbose
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

`.bin does not contain a flash address`

传 `--address`，例如很多 STM32 使用 `--address 0x08000000`。

`MSPM0 target cfg missing`

当前 OpenOCD scripts 不包含 MSPM0 支持。使用 TI SDK、UniFlash、厂商 fork，或手动传 `--target-cfg`。
