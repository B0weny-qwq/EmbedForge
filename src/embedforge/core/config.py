"""Small project configuration helpers.

EmbedForge intentionally keeps its first-stage configuration needs small, so
this parser supports the subset of YAML used by embedforge.yaml files:
indent-based mappings, scalar strings, booleans/numbers, and simple lists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """User-facing configuration loading error."""


def load_project_config(project_dir: str | Path) -> dict[str, Any]:
    path = Path(project_dir).expanduser() / "embedforge.yaml"
    if not path.is_file():
        raise ConfigError(f"embedforge.yaml not found in {Path(project_dir).expanduser()}")
    return parse_simple_yaml(path.read_text(encoding="utf-8"))


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = text.splitlines()

    for index, raw_line in enumerate(lines):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            value = parse_scalar(stripped[2:].strip())
            if not isinstance(parent, list):
                raise ConfigError(f"List item without list parent: {raw_line}")
            parent.append(value)
            continue

        if ":" not in stripped:
            raise ConfigError(f"Invalid config line: {raw_line}")
        key, value_text = stripped.split(":", 1)
        key = key.strip()
        value_text = value_text.strip()

        if value_text:
            if not isinstance(parent, dict):
                raise ConfigError(f"Mapping item without mapping parent: {raw_line}")
            parent[key] = parse_scalar(value_text)
            continue

        next_container: Any = [] if next_significant_line_is_list(lines, index) else {}
        if not isinstance(parent, dict):
            raise ConfigError(f"Mapping item without mapping parent: {raw_line}")
        parent[key] = next_container
        stack.append((indent, next_container))

    return root


def next_significant_line_is_list(lines: list[str], index: int) -> bool:
    current = lines[index]
    current_indent = len(current) - len(current.lstrip(" "))
    for raw_line in lines[index + 1 :]:
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        return indent > current_indent and line.strip().startswith("- ")
    return False


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def get_nested(config: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = config
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current
