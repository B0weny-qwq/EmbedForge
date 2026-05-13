#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: run-keil-exe.sh EXE [args...]" >&2
    exit 2
fi

exec wine "$@"
