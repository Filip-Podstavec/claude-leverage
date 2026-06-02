"""Deterministic code-convention adherence scorer.

No network, no model: same input -> same output. Emits per-metric 0..1 scores
plus raw counts as JSON. Two modes: --repo (whole tree) and --diff (a git
range). Phase 1 covers naming, casing, and structure for Python.
"""
from __future__ import annotations

import re

_PY_FUNC = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)", re.M)
_PY_CLASS = re.compile(r"^[ \t]*class[ \t]+([A-Za-z_]\w*)", re.M)
_PY_CONST = re.compile(r"^([A-Z][A-Z0-9_]*)[ \t]*[:=]", re.M)
_PY_VAR = re.compile(r"^[ \t]*([a-z_]\w*)[ \t]*(?::[^=]+)?=(?!=)", re.M)


def extract_python_identifiers(src: str) -> list[tuple[str, str]]:
    """Return (kind, name) for declarations we own. Regex-based, not a full
    parse: cheap and good enough for scoring. Order-stable, de-duplicated."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, name: str) -> None:
        key = (kind, name)
        if key not in seen:
            seen.add(key)
            out.append(key)

    for m in _PY_FUNC.finditer(src):
        add("function", m.group(1))
    for m in _PY_CLASS.finditer(src):
        add("type", m.group(1))
    for m in _PY_CONST.finditer(src):
        add("constant", m.group(1))
    for m in _PY_VAR.finditer(src):
        name = m.group(1)
        if name.isupper() or name.startswith("__"):
            continue
        add("variable", name)
    return out
