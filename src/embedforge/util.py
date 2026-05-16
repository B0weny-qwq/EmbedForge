"""Small formatting utilities for EmbedForge."""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    OK = "OK"
    MISS = "MISS"
    WARN = "WARN"


def print_status(status: Status, label: str, detail: str) -> None:
    print(f"[{status.value}] {label}: {detail}")


def readiness(found: int, total: int) -> str:
    if found == total and total > 0:
        return "ready"
    if found > 0:
        return "partial"
    return "missing"
