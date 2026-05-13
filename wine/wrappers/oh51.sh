#!/usr/bin/env bash
set -euo pipefail
exec wine "${KEIL_ROOT:-/mnt/win/Keil_v5}/C51/BIN/OH51.EXE" "$@"
