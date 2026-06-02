# Adherence Scorer (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic CLI that scores how well code conforms to naming, casing, and structure conventions, emitting per-metric 0–1 scores as JSON — the cheap, repeatable signal that powers both the eval delta and (later) the pre-write steering.

**Architecture:** A single importable module `scripts/score_adherence.py` with pure functions (identifier extraction → per-metric scorers → JSON assembly) behind an `argparse` CLI with `--repo` and `--diff` modes. Language handling sits behind a `LANG_PACKS` dict keyed by file extension; Phase 1 ships only a Python extractor. No network, no model, no third-party deps — same input always yields the same output, which is what makes it trustworthy as an eval signal.

**Tech Stack:** Python 3.11 stdlib only (`argparse`, `re`, `json`, `subprocess`, `pathlib`). Tests via pytest, stdlib-only, in the style of `tests/test_hook_behavior.py`.

**Scope (Phase 1):** naming_clarity, casing_consistency, structure — Python only. Out of scope (later phases): `context_freshness` (reuses repo-doctor Sync logic), non-Python packs, line-level `--diff` attribution, repo-doctor dimension wiring, the `conventions.yml` profile (this phase uses built-in defaults and an optional profile override).

---

## File Structure

- **Create `scripts/score_adherence.py`** — the whole scorer: extraction, the three metric functions, JSON assembly, CLI. One file is right here; it is ~250 LOC of cohesive logic with no reuse pressure yet (the repo's other `scripts/*.py` are likewise single-file).
- **Create `tests/test_score_adherence.py`** — unit tests importing the pure functions, plus two CLI/integration tests over golden fixture trees built in `tmp_path`.

Defaults live as module constants so a later `conventions.yml` can override them without restructuring:

```python
DEFAULT_VAGUE = frozenset({
    "data", "info", "tmp", "temp", "val", "value", "obj", "item", "items",
    "handle", "process", "do", "dostuff", "stuff", "util", "utils",
    "helper", "helpers", "manager", "mgr", "foo", "bar", "baz", "thing",
})
DEFAULT_MIN_LEN = 3
DEFAULT_MAX_LEN = 40
LOOP_VAR_OK = frozenset({"i", "j", "k", "n", "x", "y", "z", "_"})
DEFAULT_FILE_LOC_CEILING = 400
DEFAULT_FUNC_LOC_CEILING = 60
```

The identifier record used throughout is a plain tuple `(kind, name)` where `kind ∈ {"function", "type", "constant", "variable"}`. Keeping it a tuple (not a class) keeps the pure functions trivially testable.

---

## Task 1: Python identifier extraction

**Files:**
- Create: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_adherence.py
from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "score_adherence", REPO_ROOT / "scripts" / "score_adherence.py"
)
sa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sa)


def test_extract_python_identifiers_kinds():
    src = (
        "import os\n"
        "MAX_RETRIES = 3\n"
        "def fetch_user(user_id):\n"
        "    result = user_id + 1\n"
        "    return result\n"
        "class UserRepository:\n"
        "    pass\n"
    )
    ids = sa.extract_python_identifiers(src)
    assert ("function", "fetch_user") in ids
    assert ("type", "UserRepository") in ids
    assert ("constant", "MAX_RETRIES") in ids
    assert ("variable", "result") in ids
    # imports are not identifiers we own
    assert all(name != "os" for _, name in ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py::test_extract_python_identifiers_kinds -v`
Expected: FAIL — `ModuleNotFoundError`/`AttributeError: module 'score_adherence' has no attribute 'extract_python_identifiers'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/score_adherence.py
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
        # UPPER-only names are constants (already captured); skip dunder noise.
        if name.isupper() or name.startswith("__"):
            continue
        add("variable", name)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score_adherence.py::test_extract_python_identifiers_kinds -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): python identifier extraction"
```

---

## Task 2: naming_clarity metric

**Files:**
- Modify: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_naming_clarity_flags_vague_and_short():
    ids = [
        ("variable", "user_id"),     # clear
        ("function", "fetch_user"),  # clear
        ("variable", "data"),        # vague
        ("variable", "tmp"),         # vague
        ("variable", "x"),           # too short, but loop-ok -> clear
        ("variable", "q"),           # too short, not loop-ok -> unclear
    ]
    m = sa.score_naming_clarity(ids)
    assert m["total"] == 6
    assert m["unclear"] == 3            # data, tmp, q
    assert "data" in m["examples"]
    assert m["score"] == round(3 / 6, 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py::test_naming_clarity_flags_vague_and_short -v`
Expected: FAIL — `AttributeError: ... 'score_naming_clarity'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/score_adherence.py`:

```python
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
```

Note: the test asserts `m["score"] == round(3/6, 4)` but the implementation returns `1 - unclear/total`. Fix the test expectation to `round(1 - 3/6, 4)` before running — the metric is "fraction clear", higher is better.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score_adherence.py::test_naming_clarity_flags_vague_and_short -v`
Expected: PASS (with the corrected `score` expectation `round(1 - 3/6, 4) == 0.5`).

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): naming_clarity metric"
```

---

## Task 3: casing_consistency metric

**Files:**
- Modify: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_casing_consistency_dominant_style_per_kind():
    ids = [
        ("function", "fetch_user"),
        ("function", "save_order"),
        ("function", "deleteThing"),   # camelCase outlier among snake funcs
        ("type", "UserRepo"),
        ("type", "OrderRepo"),
    ]
    m = sa.score_casing_consistency(ids)
    # functions: 2 snake of 3 -> dominant snake_case, 1 deviates
    # types: 2 of 2 PascalCase -> 0 deviate
    assert m["deviating"] == 1
    assert m["total"] == 5
    assert m["score"] == round(1 - 1 / 5, 4)
    assert m["by_kind"]["function"]["dominant"] == "snake_case"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py::test_casing_consistency_dominant_style_per_kind -v`
Expected: FAIL — `AttributeError: ... 'score_casing_consistency'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/score_adherence.py`:

```python
from collections import Counter


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score_adherence.py::test_casing_consistency_dominant_style_per_kind -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): casing_consistency metric"
```

---

## Task 4: structure metric (file + function size)

**Files:**
- Modify: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_structure_flags_god_file_and_long_function():
    long_func = "def big():\n" + "\n".join(f"    a{i} = {i}" for i in range(70)) + "\n"
    short_func = "def small():\n    return 1\n"
    src = short_func + long_func
    m = sa.score_structure({"svc.py": src}, file_loc_ceiling=400, func_loc_ceiling=60)
    assert m["functions_total"] == 2
    assert m["functions_over"] == 1          # big() is 71 lines > 60
    assert m["god_files"] == []              # under 400 LOC
    assert 0.0 <= m["score"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py::test_structure_flags_god_file_and_long_function -v`
Expected: FAIL — `AttributeError: ... 'score_structure'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/score_adherence.py`:

```python
DEFAULT_FILE_LOC_CEILING = 400
DEFAULT_FUNC_LOC_CEILING = 60

_PY_DEF_LINE = re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]")


def _python_function_lengths(src: str) -> list[int]:
    """Length of each def body block: from the `def` line until indentation
    returns to <= the def's own indent (or EOF). Blank lines count toward the
    block only when interior. Heuristic, not a parse — adequate for scoring."""
    lines = src.splitlines()
    lengths: list[int] = []
    i = 0
    while i < len(lines):
        m = _PY_DEF_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1).expandtabs())
        j = i + 1
        last_content = i
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
        i = j
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score_adherence.py::test_structure_flags_god_file_and_long_function -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): structure metric"
```

---

## Task 5: assemble report over a file set (with language coverage)

**Files:**
- Modify: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_score_files_assembles_report_and_coverage():
    files = {
        "good.py": "def fetch_user(user_id):\n    return user_id\n",
        "notes.md": "# not code\n",          # unsupported lang -> skipped
    }
    rep = sa.score_files(files)
    assert set(rep["metrics"]) == {"naming_clarity", "casing_consistency", "structure"}
    assert rep["coverage"]["files_scored"] == 1
    assert rep["coverage"]["files_skipped"] == 1
    assert ".md" in rep["coverage"]["skipped_extensions"]
    assert 0.0 <= rep["overall"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py::test_score_files_assembles_report_and_coverage -v`
Expected: FAIL — `AttributeError: ... 'score_files'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/score_adherence.py`:

```python
import os

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score_adherence.py::test_score_files_assembles_report_and_coverage -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): assemble report with language coverage"
```

---

## Task 6: file collection for `--repo` and `--diff`, plus the CLI

**Files:**
- Modify: `scripts/score_adherence.py`
- Test: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import subprocess
import shutil
import pytest

GIT = shutil.which("git")
requires_git = pytest.mark.skipif(GIT is None, reason="git not on PATH")


def _run_cli(*args, cwd):
    import sys
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "score_adherence.py"), *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


def test_cli_repo_mode_emits_json(tmp_path):
    (tmp_path / "a.py").write_text("def fetch_user(uid):\n    return uid\n")
    res = _run_cli("--repo", str(tmp_path), cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    rep = json.loads(res.stdout)
    assert rep["coverage"]["files_scored"] == 1


@requires_git
def test_cli_diff_mode_scores_changed_files(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *a],
                       cwd=str(tmp_path), check=True, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / "base.py").write_text("def fetch_user(uid):\n    return uid\n")
    git("add", "."); git("commit", "-qm", "base")
    (tmp_path / "change.py").write_text("def data():\n    tmp = 1\n    return tmp\n")
    git("add", ".")
    res = _run_cli("--diff", "HEAD", cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    rep = json.loads(res.stdout)
    # only change.py is in the diff; base.py excluded
    assert rep["coverage"]["files_scored"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score_adherence.py -k cli -v`
Expected: FAIL — script has no CLI yet; `--repo`/`--diff` unrecognized or no stdout JSON.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/score_adherence.py`:

```python
import argparse
import json
import subprocess
import sys
from pathlib import Path


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
    res = subprocess.run(
        ["git", "diff", "--name-only", git_range],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise SystemExit(f"git diff failed: {res.stderr.strip()}")
    out: dict[str, str] = {}
    for name in res.stdout.splitlines():
        ext = os.path.splitext(name)[1].lower()
        if ext in LANG_PACKS and Path(name).exists():
            out[name] = _read(Path(name))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_score_adherence.py -k cli -v`
Expected: PASS (the `--diff` test skips only if git is absent).

- [ ] **Step 5: Commit**

```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): --repo and --diff CLI modes"
```

---

## Task 7: golden clean-vs-dirty fixture separation (sanity gate for the eval)

This is the check the spec's measurement plan calls for: confirm the scorer
*separates* a clean tree from a dirty one. It doubles as a regression guard.

**Files:**
- Modify: `tests/test_score_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_clean_tree_scores_higher_than_dirty_tree():
    clean = {
        "user_service.py": (
            "MAX_RETRIES = 3\n"
            "def fetch_user(user_id):\n    return user_id\n"
            "def save_order(order_id):\n    return order_id\n"
            "class UserRepository:\n    pass\n"
        ),
    }
    dirty = {
        "svc.py": (
            "maxRetries = 3\n"                 # casing outlier
            "def data():\n    tmp = 1\n    return tmp\n"   # vague names
            "def doStuff():\n    x = 2\n    return x\n"     # vague + casing
            "class user_repo:\n    pass\n"     # wrong type casing
        ),
    }
    clean_overall = sa.score_files(clean)["overall"]
    dirty_overall = sa.score_files(dirty)["overall"]
    assert clean_overall > dirty_overall
    assert clean_overall >= 0.9
    assert dirty_overall <= 0.6
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python -m pytest tests/test_score_adherence.py::test_clean_tree_scores_higher_than_dirty_tree -v`
Expected: PASS if Tasks 2–5 are correct. If it FAILS, the thresholds expose a real calibration gap — adjust the metric weighting or `DEFAULT_VAGUE`, not the assertion, until clean/dirty separate as a human would judge them.

- [ ] **Step 3: (only if Step 2 failed) calibrate**

If separation is too weak, the most likely cause is `class user_repo` being read as `snake_case` dominant when it is the only type. Confirm `classify_casing("user_repo") == "snake_case"` and `classify_casing("UserRepository") == "PascalCase"`; the dirty tree's single type makes its own casing "dominant", so type-casing won't penalize a lone wrong type. That is acceptable — the vague names and function-casing outliers carry the separation. Do not special-case single-identifier kinds.

- [ ] **Step 4: Run the whole scorer suite**

Run: `python -m pytest tests/test_score_adherence.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_score_adherence.py
git commit -m "test(scorer): clean-vs-dirty separation gate"
```

---

## Task 8: register the script in the repo's catalogue

The maintenance convention (`docs/maintaining.md`) requires that a new script be
listed where the others are and run in CI.

**Files:**
- Modify: `README.md` (the `#whats-inside` command/script catalogue)
- Modify: `.github/workflows/ci.yml` (the existing `pytest` + `pytest-windows` jobs already run `pytest tests/ -v`, so the new tests run automatically — verify, don't duplicate)

- [ ] **Step 1: Confirm CI already covers it**

Run: `grep -n "pytest tests/" .github/workflows/ci.yml`
Expected: two matches (ubuntu + windows jobs). No CI change needed — the new tests are picked up by the existing glob.

- [ ] **Step 2: Add the script to the README catalogue**

Locate the scripts list under the README "What's inside" section and add, in the same format as the neighbours:

```markdown
- `scripts/score_adherence.py` — deterministic naming/casing/structure
  adherence scorer (`--repo` / `--diff`); emits JSON. Powers the conventions
  eval and (later) pre-write steering.
```

- [ ] **Step 3: Verify the docs/maintaining checklist has nothing else outstanding**

Run: `grep -rn "score_adherence\|score-adherence" README.md docs/`
Expected: the README line just added, and the two design docs. No dangling references.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(scorer): list score_adherence in the catalogue"
```

---

## Self-Review

**Spec coverage (Phase 1 slice):**
- naming_clarity → Task 2 ✓
- casing_consistency → Task 3 ✓
- structure → Task 4 ✓
- `--repo` / `--diff` modes → Task 6 ✓
- JSON output + overall → Task 5 ✓
- language pack seam (Python first) → Task 1 + Task 5 (`LANG_PACKS`) ✓
- graceful degradation (unknown lang skipped, coverage noted) → Task 5 ✓
- clean-vs-dirty separation (measurement sanity gate) → Task 7 ✓
- catalogue/CI hygiene → Task 8 ✓
- **Deferred to later phases (documented in the spec, not gaps):** `context_freshness` metric, `conventions.yml` override wiring, non-Python packs, line-level `--diff`, repo-doctor dimension, the steering hook + nudge (Phase 2), the eval harness (Phase 3).

**Placeholder scan:** none — every code step carries complete function bodies; every run step has an exact command and expected outcome.

**Type consistency:** the `(kind, name)` tuple, the metric dict shapes (`score`/`total`/…), `score_files`'s `metrics`/`coverage`/`overall` keys, and `LANG_PACKS` are used identically across Tasks 1–8. `score_structure` takes `files: dict[str,str]` in both Task 4 and Task 5. CLI calls `score_files` which calls the three metric functions defined earlier. No drift found.

**Note for the implementer:** Task 2's first-draft test asserts the wrong `score` direction; the step text tells you to correct the expectation to "fraction clear" before running. This is intentional — fix the test, not the metric.
