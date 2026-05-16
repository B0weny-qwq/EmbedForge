#!/usr/bin/env python3
"""Standalone OpenOCD flash wrapper for EmbedForge."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from embedforge.flash.openocd import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
