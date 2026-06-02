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


DEFAULT_VAGUE = frozenset({
    "data", "info", "tmp", "temp", "val", "value", "obj", "item", "items",
    "handle", "process", "do", "dostuff", "stuff", "util", "utils",
    "helper", "helpers", "manager", "mgr", "foo", "bar", "baz", "thing",
})
DEFAULT_MIN_LEN = 3
DEFAULT_MAX_LEN = 40
LOOP_VAR_OK = frozenset({"i", "j", "k", "n", "x", "y", "z", "_"})


def _is_unclear(name: str, vague: frozenset[str], min_len: int, max_len: int) -> bool:
    base = name.strip("_").lower()
    if not base:
        return False  # pure underscores: intentional throwaway, not "unclear"
    if base in vague:
        return True
    if name in LOOP_VAR_OK:
        return False
    if len(base) < min_len or len(base) > max_len:
        return True
    return False


def score_naming_clarity(
    ids: list[tuple[str, str]],
    vague: frozenset[str] = DEFAULT_VAGUE,
    min_len: int = DEFAULT_MIN_LEN,
    max_len: int = DEFAULT_MAX_LEN,
) -> dict:
    total = len(ids)
    unclear_names = [name for _, name in ids if _is_unclear(name, vague, min_len, max_len)]
    unclear = len(unclear_names)
    score = 1.0 if total == 0 else round(1 - unclear / total, 4)
    return {
        "score": score,
        "total": total,
        "unclear": unclear,
        "examples": sorted(set(unclear_names))[:10],
    }
