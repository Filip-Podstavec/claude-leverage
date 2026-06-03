"""Deterministic code-convention adherence scorer.

No network, no model: same input -> same output. Emits per-metric 0..1 scores
plus raw counts as JSON. Two modes: --repo (whole tree) and --diff (a git
range). Phase 1 covers naming, casing, and structure for Python.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

_PY_FUNC = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)", re.M)
_PY_CLASS = re.compile(r"^[ \t]*class[ \t]+([A-Za-z_]\w*)", re.M)
_PY_CONST = re.compile(r"^([A-Z][A-Z0-9_]*)[ \t]*[:=]", re.M)
_PY_VAR = re.compile(r"^[ \t]*([a-z_]\w*)[ \t]*(?::[^=]+)?=(?!=)", re.M)
# AIDEV-NOTE: these regexes are a column-0 / first-target SAMPLING heuristic,
# not an AST parse: _PY_CONST ignores indented constants, _PY_VAR takes only the
# first assignment target. Deliberate for cheap scoring -- don't "fix" into noise.


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


def classify_casing(name: str) -> str:
    core = name.strip("_")
    if not core:
        return "other"
    if core.isupper() and ("_" in core or core.isalpha()):
        return "UPPER_SNAKE"
    if "_" in core:
        return "snake_case" if core.islower() else "other"
    if core[0].isupper() and any(c.islower() for c in core):
        return "PascalCase"
    if core[0].islower() and any(c.isupper() for c in core):
        return "camelCase"
    if core.islower():
        return "snake_case"  # single lowercase word is valid snake_case
    return "other"


def score_casing_consistency(ids: list[tuple[str, str]]) -> dict:
    by_kind_names: dict[str, list[str]] = {}
    for kind, name in ids:
        by_kind_names.setdefault(kind, []).append(name)

    total = 0
    deviating = 0
    by_kind: dict[str, dict] = {}
    for kind, names in sorted(by_kind_names.items()):
        styles = Counter(classify_casing(n) for n in names)
        # Deterministic dominant: highest count, ties broken by style name.
        dominant = sorted(styles.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        dev = sum(1 for n in names if classify_casing(n) != dominant)
        total += len(names)
        deviating += dev
        by_kind[kind] = {"dominant": dominant, "count": len(names), "deviating": dev}

    score = 1.0 if total == 0 else round(1 - deviating / total, 4)
    return {"score": score, "total": total, "deviating": deviating, "by_kind": by_kind}


DEFAULT_FILE_LOC_CEILING = 400
DEFAULT_FUNC_LOC_CEILING = 60

_PY_DEF_LINE = re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]")


def _python_function_lengths(src: str) -> list[int]:
    """Length of each def block: from the `def` line through the last body line
    whose indent exceeds the def's. Nested defs are counted independently (the
    outer's span still includes them). Heuristic, not an AST: signature end is
    found by paren-balance, adequate for scoring."""
    lines = src.splitlines()
    lengths: list[int] = []
    i = 0
    while i < len(lines):
        m = _PY_DEF_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1).expandtabs())
        # Skip a (possibly multi-line) signature: advance until parens balance
        # and the line ends with ':'. For a single-line `def f():` this stops
        # on the def line itself.
        sig_end = i
        depth = 0
        while sig_end < len(lines):
            depth += lines[sig_end].count("(") - lines[sig_end].count(")")
            if depth <= 0 and lines[sig_end].rstrip().endswith(":"):
                break
            sig_end += 1
        j = sig_end + 1
        last_content = sig_end
        while j < len(lines):
            ln = lines[j]
            if ln.strip() == "":
                j += 1
                continue
            cur_indent = len(ln[: len(ln) - len(ln.lstrip())].expandtabs())
            if cur_indent <= indent:
                break
            last_content = j
            j += 1
        lengths.append(last_content - i + 1)
        i += 1  # advance one line (not past the block) so nested defs are seen
    return lengths


def _non_blank_loc(src: str) -> int:
    return sum(1 for ln in src.splitlines() if ln.strip())


def score_structure(
    files: dict[str, str],
    file_loc_ceiling: int = DEFAULT_FILE_LOC_CEILING,
    func_loc_ceiling: int = DEFAULT_FUNC_LOC_CEILING,
) -> dict:
    god_files: list[str] = []
    funcs_total = 0
    funcs_over = 0
    for path in sorted(files):
        src = files[path]
        if _non_blank_loc(src) > file_loc_ceiling:
            god_files.append(path)
        for length in _python_function_lengths(src):
            funcs_total += 1
            if length > func_loc_ceiling:
                funcs_over += 1

    n_files = len(files)
    file_ok = 1.0 if n_files == 0 else 1 - len(god_files) / n_files
    func_ok = 1.0 if funcs_total == 0 else 1 - funcs_over / funcs_total
    score = round((file_ok + func_ok) / 2, 4)
    return {
        "score": score,
        "god_files": god_files,
        "functions_total": funcs_total,
        "functions_over": funcs_over,
    }


_CASING_KEY = {"function": "functions", "type": "types", "constant": "constants"}


def flag_blob_violations(blob, casing=None, denylist=None):
    """Flag identifiers in an edit BLOB that violate naming conventions: a
    denylisted/built-in vague name, or a casing that clearly disagrees with the
    declared per-kind casing. Scores only the blob, so it reflects what the edit
    introduces (not the whole file's history). Python-only. Returns a list of
    {name, kind, reason}."""
    casing = casing or {}
    vague = DEFAULT_VAGUE | frozenset(denylist or ())
    flags = []
    for kind, name in extract_python_identifiers(blob):
        if _is_unclear(name, vague, DEFAULT_MIN_LEN, DEFAULT_MAX_LEN):
            flags.append({"name": name, "kind": kind, "reason": "vague"})
            continue
        want = casing.get(_CASING_KEY.get(kind, ""))
        if want:
            cc = classify_casing(name)
            if cc != "other" and cc != want:
                flags.append({"name": name, "kind": kind, "reason": f"casing!={want}"})
    return flags


# extension -> identifier extractor. Phase 1 ships Python only; the dict is the
# seam where TS/Go packs slot in later without touching the scorers.
LANG_PACKS = {".py": extract_python_identifiers}


def score_files(files: dict[str, str]) -> dict:
    supported: dict[str, str] = {}
    skipped_exts: set[str] = set()
    for path, src in files.items():
        ext = os.path.splitext(path)[1].lower()
        if ext in LANG_PACKS:
            supported[path] = src
        else:
            skipped_exts.add(ext or "<none>")

    ids: list[tuple[str, str]] = []
    for path in sorted(supported):
        ids.extend(LANG_PACKS[os.path.splitext(path)[1].lower()](supported[path]))

    metrics = {
        "naming_clarity": score_naming_clarity(ids),
        "casing_consistency": score_casing_consistency(ids),
        "structure": score_structure(supported),
    }
    overall = round(sum(m["score"] for m in metrics.values()) / len(metrics), 4)
    return {
        "overall": overall,
        "metrics": metrics,
        "coverage": {
            "files_scored": len(supported),
            "files_skipped": len(files) - len(supported),
            "skipped_extensions": sorted(skipped_exts),
        },
    }


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_repo(root: str) -> dict[str, str]:
    base = Path(root)
    out: dict[str, str] = {}
    for ext in LANG_PACKS:
        for p in base.rglob(f"*{ext}"):
            parts = set(p.parts)
            if parts & {".git", "node_modules", "__pycache__", "dist", "build", "target"}:
                continue
            out[str(p.relative_to(base))] = _read(p)
    return out


def collect_diff(git_range: str) -> dict[str, str]:
    root_res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
    )
    if root_res.returncode != 0:
        raise SystemExit(f"not a git repo: {root_res.stderr.strip()}")
    root = Path(root_res.stdout.strip())
    res = subprocess.run(
        ["git", "diff", "--name-only", git_range], capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise SystemExit(f"git diff failed: {res.stderr.strip()}")
    out: dict[str, str] = {}
    for name in res.stdout.splitlines():
        # git reports paths relative to the repo root regardless of CWD.
        ext = os.path.splitext(name)[1].lower()
        p = root / name
        if ext in LANG_PACKS and p.exists():
            out[name] = _read(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic convention-adherence scorer.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--repo", metavar="PATH", help="score the whole tree at PATH")
    mode.add_argument("--diff", metavar="GITRANGE", help="score files changed in a git range")
    args = ap.parse_args(argv)

    files = collect_repo(args.repo) if args.repo else collect_diff(args.diff)
    report = score_files(files)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
