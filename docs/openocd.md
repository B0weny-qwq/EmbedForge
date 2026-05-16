# OpenOCD Git Build

EmbedForge does not use the apt repository OpenOCD package as the primary deployment target.
Distribution packages are often behind upstream and are not a good baseline for new chip support.
EmbedForge uses the latest OpenOCD `master` source from Git.

Install location:

```text
/opt/openocd-git
```

Wrapper:

```text
~/.local/bin/openocd-git
```

Build information:

```text
/opt/openocd-git/EMBEDFORGE_BUILD_INFO
```

Install:

```bash
./scripts/setup_openocd_git.sh
```

Verify:

```bash
openocd-git --version
./ef doctor
lsusb
```

OpenOCD is suitable for:

- ARM Cortex-M
- SWD
- JTAG
- DAPLink / CMSIS-DAP
- ST-Link
- J-Link
- XDS110

STC32/C251 usually does not use OpenOCD. It should use an STC ISP or serial flashing flow in future EmbedForge adapters.

DAPLink + STM32F103 example:

```tcl
source [find interface/cmsis-dap.cfg]
transport select swd
adapter speed 1000
source [find target/stm32f1x.cfg]
```

Test:

```bash
openocd-git -f openocd.cfg
```
