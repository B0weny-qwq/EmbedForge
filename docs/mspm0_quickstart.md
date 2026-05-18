# MSPM0 Quickstart

This workflow uses the public TI MSPM0 SDK Git repository and CMake/GCC.
It does not require Wine or Keil for the main build path.

## Install MSPM0 SDK

Manual install:

```sh
mkdir -p ~/SDK/TI
cd ~/SDK/TI
git clone --recursive https://github.com/TexasInstruments/mspm0-sdk.git
```

Or use EmbedForge:

```sh
./ef sdk install mspm0
```

## Environment

```sh
export MSPM0_SDK_PATH=~/SDK/TI/mspm0-sdk
```

Optional shell startup:

```sh
echo 'export MSPM0_SDK_PATH=~/SDK/TI/mspm0-sdk' >> ~/.bashrc
```

## Check

```sh
./ef sdk list
./ef sdk check mspm0
```

## CMake Build Direction

MSPM0 projects should use:

```yaml
sdk:
  type: ti-mspm0
  family: mspm0
  env: MSPM0_SDK_PATH

build:
  system: cmake
  generator: ninja
  toolchain: arm-none-eabi-gcc
```

EmbedForge passes `-DMSPM0_SDK_PATH=<path>` to CMake and also sets the
`MSPM0_SDK_PATH` environment variable for the configure/build subprocesses.

## Flash Direction

OpenOCD MSPM0 target support depends on the installed OpenOCD scripts. If
`target/ti_mspm0.cfg` or `target/mspm0.cfg` is unavailable, use TI tooling,
UniFlash, a vendor OpenOCD fork, or pass a working `--target-cfg` explicitly.
