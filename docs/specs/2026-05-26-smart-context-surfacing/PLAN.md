# Smart Context Surfacing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut per-session token overhead from leverage-stack docs by surfacing only the AIDEV anchors / per-dir AGENTS.md / ADR cross-references relevant to the specific file the agent is about to read or edit, via a `PreToolUse` hook that emits `hookSpecificOutput.additionalContext`.

**Architecture:** Manifest-based — a build script scans the repo once and writes `.claude-leverage-context-map.json` mapping each tracked file to its relevant context. The hook does an O(1) JSON lookup on every `Read/Edit/Write/MultiEdit` call and emits a system reminder with just that file's slice. Manifest stays in repo (committed) so it's deterministic; a `/refresh-context-map` skill rebuilds it on demand. Designed for **graceful no-op** when the manifest is missing (most users won't have one until they opt in) so the new hook does not regress existing repos.

**Tech Stack:** Python 3 stdlib (manifest builder, no third-party deps), Bash + `json_parse.sh` helper (hook runtime, follows existing convention), JSON manifest (jq-friendly).

**Cross-tool:** Same shell script + same output schema works for both Claude Code and Codex (both accept `hookSpecificOutput.additionalContext` per their respective specs — researched 2026-05-26). Codex `apply_patch` is out of scope for MVP (file path extraction from patch is fragile); deferred to Phase 2 of a future iteration.

**Versioning:** This is a feature addition → bump to **v1.8.0** in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

---

## File structure

| Path | Status | Purpose |
|---|---|---|
| `scripts/build-context-map.py` | NEW | Scans repo, writes `.claude-leverage-context-map.json` |
| `scripts/hooks/context-surface.sh` | NEW | PreToolUse hook — JSON lookup + emit `additionalContext` |
| `hooks/hooks.json` | MODIFY | Register new hook on `Read|Edit|Write|MultiEdit` matcher |
| `.codex/hooks.json` | MODIFY | Same registration for Codex parity |
| `tests/test_context_surfacing.py` | NEW | Unit tests for builder + behavioral tests for hook |
| `skills/refresh-context-map/SKILL.md` | NEW | User-facing skill to rebuild manifest |
| `docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md` | NEW | ADR documenting the design decision |
| `AGENTS.md` | MODIFY | Add row to "Commands available" table + brief mention in Maintenance |
| `README.md` | MODIFY | Update hook count (5→6), what's-inside table |
| `CHANGELOG.md` | MODIFY | New entry for v1.8.0 |
| `.claude-plugin/plugin.json` | MODIFY | Version bump 1.7.0 → 1.8.0 |
| `.claude-plugin/marketplace.json` | MODIFY | Version bump 1.7.0 → 1.8.0 |
| `hooks/README.md` | MODIFY | Document the new hook |
| `scripts/smoke-plugin.sh` | (already covers shellcheck on new script via glob) | no change needed |
| `.gitignore` | VERIFY | `.claude-leverage-context-map.json` does NOT need to be gitignored — it's intended to be checked in |
| `.gitattributes` | MODIFY/CREATE | Add `*.claude-leverage-context-map.json merge=union` to reduce conflicts on the committed manifest |
| `scripts/smoke-plugin.sh` | MODIFY | Add `python scripts/build-context-map.py --check` gate so a forgotten rebuild surfaces in CI |

---

## Manifest schema (concrete)

`.claude-leverage-context-map.json` at repo root:

```json
{
  "_meta": {
    "schema_version": 1,
    "builder_version": "1.8.0",
    "generated_at": "2026-05-26T20:00:00Z",
    "generator": "scripts/build-context-map.py",
    "file_count": 234,
    "anchor_count": 89,
    "repo_root": "."
  },
  "files": {
    "classes/db/clickhouse_reader.py": {
      "anchors_in_file": [
        {"line": 29, "type": "AIDEV-NOTE", "text": "never bind the int as key \"limit\" — CH 25.4 new analyzer treats it as a LIMIT override and fails parsing. Use row_cap / row_skip."}
      ],
      "anchors_in_dir": [
        {"file": "classes/db/clickhouse_writer.py", "line": 30, "type": "AIDEV-NOTE", "text": "every column (including DEFAULTed ones) must be in each row dict — KeyError on sample block otherwise"}
      ],
      "agents_md": ["classes/AGENTS.md", "AGENTS.md"],
      "adrs": ["docs/adr/0001-clickhouse-as-primary-warehouse.md"]
    }
  }
}
```

**Field semantics:**

- `anchors_in_file` — AIDEV-* anchors *inside* the target file. Most directly relevant.
- `anchors_in_dir` — AIDEV-* anchors in *sibling files* in the same directory. Often relevant gotchas the agent should be aware of.
- `agents_md` — chain of per-dir `AGENTS.md` files from `dirname(file)` up to repo root. Hook surfaces "read these for project conventions" without dumping their content (Claude Code already auto-loads `AGENTS.md` at session start; per-dir ones are a Read away).
- `adrs` — paths to ADR files that mention this file path verbatim. Surfaces "why" decisions.

**Storage decisions:**

- **Anchor text is stored verbatim** (no truncation in manifest; truncation happens at emit time). This way the manifest is the canonical record; emit-side decides what to show.
- **No content stored for AGENTS.md / ADRs** — just paths. The agent reads them via `Read` if needed (which itself triggers a hook fire — that's fine).
- **Paths are POSIX-style forward-slash, relative to repo root.** Hook normalizes Windows backslashes, drive-letter case, and absolutes to match on lookup. Uses the same `canon_path` helper logic as `scripts/hooks/ai-first-nudge.sh` (inlined into the new hook for now — promote to `json_parse.sh` if a third hook needs it).
- **Atomic write**: builder writes to `.claude-leverage-context-map.json.tmp` then `os.replace()`s into place, so a concurrent hook fire can never observe a half-written file.
- **`builder_version`** in `_meta` allows future schema changes — hook reads it and gracefully degrades on mismatch instead of crashing.

---

## Hook output format (concrete)

When the hook fires and finds context, it emits to stdout:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "[claude-leverage:context-surface]\nAIDEV anchors in classes/db/clickhouse_reader.py:\n  L29 NOTE: never bind the int as key \"limit\" — CH 25.4 new analyzer treats it as a LIMIT override and fails parsing. Use row_cap / row_skip.\n\nAnchors in same directory:\n  classes/db/clickhouse_writer.py:30 NOTE: every column (including DEFAULTed ones) must be in each row dict — KeyError on sample block otherwise\n\nFor project conventions, see (Read on demand):\n  classes/AGENTS.md, AGENTS.md\n\nRelated ADRs:\n  docs/adr/0001-clickhouse-as-primary-warehouse.md"
  }
}
```

**Format invariants:**

- First line is `[claude-leverage:context-surface]` — single grep-able marker so users can audit what the hook surfaced.
- Sections appear only if they have content (no empty "Related ADRs: (none)" noise).
- Total emit capped at **4096 chars** (well under Claude Code's 10K limit). If `anchors_in_dir` is too large, truncate with a `(+N more, run /refresh-context-map to see all)` indicator.
- If nothing relevant found → emit nothing, exit 0 silently.

---

## Performance budget

| Metric | Budget | Why |
|---|---|---|
| Hook cold start | < 80ms p99 | Fires on every Read/Edit/Write; budget keeps interactive latency invisible |
| Manifest size | < 2 MB for 10K-file repo | Hand-tunable; flat JSON, easy to keep under |
| Builder runtime | < 5s on 10K-file repo | Once-per-rebuild, not interactive — looser budget |
| Hook lookup | < 20ms p99 | jq path lookup on cached JSON — should be well under |

---

## Phase 1 — Manifest builder (TDD)

### Task 1: Create test directory + skeleton test file

**Files:**
- Create: `tests/test_context_surfacing.py`

- [ ] **Step 1: Create the test file with imports + the marker pattern existing tests use**

```python
"""Unit tests for scripts/build-context-map.py and behavioral tests for
scripts/hooks/context-surface.sh.

Builder tests are pure stdlib pytest. Hook tests use the same subprocess
pattern as tests/test_hook_behavior.py — driving the shell script with
crafted stdin JSON in a tmp working dir, asserting on stdout/stderr/exit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDER = REPO_ROOT / "scripts" / "build-context-map.py"
HOOK = REPO_ROOT / "scripts" / "hooks" / "context-surface.sh"

BASH = shutil.which("bash")
PYTHON = sys.executable

hook_pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="bash not on PATH — hook behavior tests need a POSIX shell",
)
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): add empty test module skeleton"
```

### Task 2: Test — builder writes a valid manifest on an empty repo

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add the test**

```python
def test_builder_writes_valid_manifest_on_empty_repo(tmp_path: Path) -> None:
    """Even an empty git repo should produce a syntactically valid manifest
    with the _meta block and an empty files map — never crash."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)

    result = subprocess.run(
        [PYTHON, str(BUILDER)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"builder exit {result.returncode}; stderr={result.stderr!r}"

    manifest_path = tmp_path / ".claude-leverage-context-map.json"
    assert manifest_path.exists(), "manifest file not created"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["_meta"]["schema_version"] == 1
    assert manifest["_meta"]["generator"] == "scripts/build-context-map.py"
    assert manifest["files"] == {}
    assert manifest["_meta"]["anchor_count"] == 0
```

- [ ] **Step 2: Run test, confirm FAIL with `FileNotFoundError` (builder doesn't exist)**

```bash
pytest tests/test_context_surfacing.py::test_builder_writes_valid_manifest_on_empty_repo -v
```

### Task 3: Implement builder skeleton

**Files:**
- Create: `scripts/build-context-map.py`

- [ ] **Step 1: Write the minimal builder that passes Task 2**

```python
#!/usr/bin/env python3
"""Build .claude-leverage-context-map.json — a per-file index of AIDEV
anchors, per-dir AGENTS.md chain, and ADR cross-references.

Used by scripts/hooks/context-surface.sh (PreToolUse hook) to surface
context relevant to the specific file the agent is about to read or edit,
instead of forcing the agent to consume the full leverage-doc surface
upfront. See docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md.

Usage:
    python scripts/build-context-map.py              # writes manifest at repo root
    python scripts/build-context-map.py --check      # exit 1 if regen would diff committed file
    python scripts/build-context-map.py --quiet      # suppress summary stdout

Stdlib-only — runs anywhere Python 3.8+ runs.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1
BUILDER_VERSION = "1.8.0"  # bump on schema or anchor-extraction semantic changes
MANIFEST_NAME = ".claude-leverage-context-map.json"
GENERATOR = "scripts/build-context-map.py"

# AIDEV-NOTE: regex matches `AIDEV-NOTE:`, `AIDEV-TODO(by: 2026-08-01):`,
# `AIDEV-QUESTION:` — case-sensitive, all-caps prefix per convention in
# AGENTS.md. Deadline-bearing variant captures the date in group 2.
ANCHOR_RE = re.compile(
    r"AIDEV-(NOTE|TODO|QUESTION)(?:\(by:\s*(\d{4}-\d{2}-\d{2})\))?:\s*(.*)"
)


def find_repo_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def list_tracked_files(repo_root: Path) -> list[Path]:
    """Use git to enumerate files — skips .gitignored content for free."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return [repo_root / p for p in out.stdout.splitlines() if p]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []


def build(repo_root: Path) -> dict:
    """Walk repo, extract anchors, return manifest dict."""
    return {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "builder_version": BUILDER_VERSION,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "generator": GENERATOR,
            "file_count": 0,
            "anchor_count": 0,
            "repo_root": ".",
        },
        "files": {},
    }


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically — write to `.tmp` sibling then
    os.replace into place. Prevents the hook from observing a half-written
    manifest if a builder run races with a tool call."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if regen would differ from on-disk manifest")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    repo_root = find_repo_root(Path.cwd())
    if repo_root is None:
        print("ERROR: not inside a git repo", file=sys.stderr)
        return 2

    manifest = build(repo_root)
    out_path = repo_root / MANIFEST_NAME
    new_json = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check:
        old_json = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        if old_json != new_json:
            print(f"DRIFT: {out_path} differs from regen — run "
                  f"`python scripts/build-context-map.py` to update", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"OK: {out_path} is up to date")
        return 0

    _atomic_write(out_path, new_json)
    if not args.quiet:
        print(f"Wrote {out_path} "
              f"({manifest['_meta']['file_count']} files, "
              f"{manifest['_meta']['anchor_count']} anchors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test, confirm PASS**

```bash
pytest tests/test_context_surfacing.py::test_builder_writes_valid_manifest_on_empty_repo -v
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-surface): manifest builder skeleton with empty-repo test"
```

### Task 4: Test — builder extracts AIDEV anchors from files

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add the test**

```python
def _init_repo_with_files(tmp_path: Path, files: dict[str, str]) -> None:
    """Initialize a git repo and stage all named files. Files must be
    listed in `git ls-files` for the builder to find them."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)


def test_builder_extracts_aidev_note(tmp_path: Path) -> None:
    """A file with a single AIDEV-NOTE should appear in the manifest with
    one anchor at the correct line and text."""
    _init_repo_with_files(tmp_path, {
        "src/api.py": (
            "def query(params):\n"
            "    # AIDEV-NOTE: never include 'limit' key — CH 25.4 LIMIT override bug\n"
            "    return run(params)\n"
        ),
    })

    subprocess.run(
        [PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
        capture_output=True, text=True, check=True, timeout=30,
    )

    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert "src/api.py" in manifest["files"], manifest["files"]
    entry = manifest["files"]["src/api.py"]
    assert len(entry["anchors_in_file"]) == 1
    a = entry["anchors_in_file"][0]
    assert a["line"] == 2
    assert a["type"] == "AIDEV-NOTE"
    assert "limit" in a["text"]
    assert "CH 25.4" in a["text"]
    assert manifest["_meta"]["anchor_count"] == 1


def test_builder_extracts_multiple_anchor_types(tmp_path: Path) -> None:
    """NOTE / TODO / QUESTION with and without deadlines all parse."""
    _init_repo_with_files(tmp_path, {
        "src/foo.py": (
            "# AIDEV-NOTE: load-bearing invariant\n"
            "# AIDEV-TODO(by: 2026-08-01): migrate to webhooks\n"
            "# AIDEV-QUESTION(by: 2026-07-15): is encoding always UTF-8?\n"
            "x = 1\n"
        ),
    })

    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    anchors = manifest["files"]["src/foo.py"]["anchors_in_file"]
    assert len(anchors) == 3
    types = [a["type"] for a in anchors]
    assert types == ["AIDEV-NOTE", "AIDEV-TODO", "AIDEV-QUESTION"]
    # deadline parsed for the second + third
    assert anchors[1].get("deadline") == "2026-08-01"
    assert anchors[2].get("deadline") == "2026-07-15"
```

- [ ] **Step 2: Run tests, confirm FAIL (builder still returns empty files)**

```bash
pytest tests/test_context_surfacing.py -v -k "extracts"
```

### Task 5: Implement anchor extraction

**Files:**
- Modify: `scripts/build-context-map.py`

- [ ] **Step 1: Replace `build()` body**

```python
def _scan_anchors(file_path: Path) -> list[dict]:
    """Return list of anchor dicts for the file. Skips:
      - Files >1 MiB (too large to be meaningful source)
      - Binary files (NUL byte in first 8 KiB sniff)
      - Files with unreadable bytes
    Detection by NUL-byte sniff is the same heuristic git uses internally —
    keeps PNGs, parquet, zips, etc. out of the manifest without an extension
    allowlist that would miss legitimate non-standard source files."""
    try:
        if file_path.stat().st_size > 1_048_576:
            return []
        # NUL-byte sniff: any \0 in the first 8 KiB → binary, skip.
        with file_path.open("rb") as fh:
            head = fh.read(8192)
        if b"\x00" in head:
            return []
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return []

    anchors: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = ANCHOR_RE.search(line)
        if not m:
            continue
        a = {
            "line": i,
            "type": f"AIDEV-{m.group(1)}",
            "text": m.group(3).strip(),
        }
        if m.group(2):
            a["deadline"] = m.group(2)
        anchors.append(a)
    return anchors


def build(repo_root: Path) -> dict:
    """Walk repo, extract anchors, return manifest dict."""
    files_map: dict[str, dict] = {}
    total_anchors = 0
    tracked = list_tracked_files(repo_root)
    file_count = 0

    for abs_path in tracked:
        if not abs_path.is_file():
            continue
        anchors = _scan_anchors(abs_path)
        if not anchors:
            continue
        rel = abs_path.relative_to(repo_root).as_posix()
        files_map[rel] = {
            "anchors_in_file": anchors,
            "anchors_in_dir": [],  # filled in Task 7
            "agents_md": [],       # filled in Task 9
            "adrs": [],            # filled in Task 11
        }
        total_anchors += len(anchors)
        file_count += 1

    return {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "builder_version": BUILDER_VERSION,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "generator": GENERATOR,
            "file_count": file_count,
            "anchor_count": total_anchors,
            "repo_root": ".",
        },
        "files": files_map,
    }
```

- [ ] **Step 2: Run tests, confirm PASS**

```bash
pytest tests/test_context_surfacing.py -v -k "extracts"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-surface): extract AIDEV anchors into manifest"
```

### Task 6: Test — anchors_in_dir cross-populates from siblings

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
def test_builder_populates_anchors_in_dir_from_siblings(tmp_path: Path) -> None:
    """When two files in the same dir both have anchors, each file's
    entry should reference the other's anchors under `anchors_in_dir`.
    A file in a sibling sub-dir should NOT pollute either entry."""
    _init_repo_with_files(tmp_path, {
        "src/db/reader.py": "# AIDEV-NOTE: never use 'limit' as a param key\n",
        "src/db/writer.py": "# AIDEV-NOTE: all columns required in row dict\n",
        "src/api.py":      "# AIDEV-NOTE: routes are grouped by tag\n",
    })

    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())

    reader = manifest["files"]["src/db/reader.py"]
    assert len(reader["anchors_in_dir"]) == 1
    sibling = reader["anchors_in_dir"][0]
    assert sibling["file"] == "src/db/writer.py"
    assert "row dict" in sibling["text"]

    api = manifest["files"]["src/api.py"]
    # api.py is in src/ — no sibling has anchors at that level
    assert api["anchors_in_dir"] == []
```

- [ ] **Step 2: Run test, confirm FAIL**

### Task 7: Implement anchors_in_dir cross-population

**Files:**
- Modify: `scripts/build-context-map.py`

- [ ] **Step 1: Add a second pass after the file-walk loop in `build()`**

Insert just before `return { ... }`:

```python
    # Second pass: cross-populate anchors_in_dir from siblings.
    by_dir: dict[str, list[tuple[str, dict]]] = {}
    for rel, entry in files_map.items():
        d = str(Path(rel).parent.as_posix())
        for a in entry["anchors_in_file"]:
            by_dir.setdefault(d, []).append((rel, a))

    for rel, entry in files_map.items():
        d = str(Path(rel).parent.as_posix())
        for sibling_rel, a in by_dir.get(d, []):
            if sibling_rel == rel:
                continue
            entry["anchors_in_dir"].append({
                "file": sibling_rel,
                "line": a["line"],
                "type": a["type"],
                "text": a["text"],
            })
```

- [ ] **Step 2: Run test, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-surface): cross-populate anchors_in_dir from siblings"
```

### Task 8: Test — agents_md walks parent chain

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
def test_builder_walks_agents_md_chain(tmp_path: Path) -> None:
    """For a file at src/db/reader.py, agents_md should list every
    AGENTS.md on the walk from src/db/ up to the repo root that
    actually exists, in dirname-first order."""
    _init_repo_with_files(tmp_path, {
        "AGENTS.md":              "# top-level\n",
        "src/AGENTS.md":          "# src-level\n",
        "src/db/reader.py":       "# AIDEV-NOTE: x\n",
        # no src/db/AGENTS.md — should be skipped
    })

    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())

    entry = manifest["files"]["src/db/reader.py"]
    assert entry["agents_md"] == ["src/AGENTS.md", "AGENTS.md"]


def test_builder_skips_files_in_dirs_without_anchors_from_agents_walk(tmp_path: Path) -> None:
    """If a file has no anchors itself, it's not in the manifest at all —
    so agents_md walking only happens for files with anchors."""
    _init_repo_with_files(tmp_path, {
        "AGENTS.md":           "# top\n",
        "src/no_anchors.py":   "x = 1\n",
    })

    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"] == {}
```

- [ ] **Step 2: Run, confirm first test FAIL, second test PASS**

### Task 9: Implement AGENTS.md chain walk

**Files:**
- Modify: `scripts/build-context-map.py`

- [ ] **Step 1: Add helper + integrate into second pass**

Add after `_scan_anchors`:

```python
def _agents_md_chain(file_rel: Path, repo_root: Path) -> list[str]:
    """Walk from dirname(file) up to repo_root, listing every AGENTS.md
    that exists, dirname-first.

    Tolerant of symlinks pointing outside the repo: if `.resolve()` lands
    outside `repo_root`, return whatever chain we built so far rather than
    crashing on `relative_to`."""
    chain: list[str] = []
    try:
        cur = (repo_root / file_rel).parent.resolve()
        root_resolved = repo_root.resolve()
    except (OSError, RuntimeError):
        return chain
    while True:
        candidate = cur / "AGENTS.md"
        if candidate.is_file():
            try:
                chain.append(candidate.relative_to(root_resolved).as_posix())
            except ValueError:
                # Symlink escapes repo_root. Skip and stop walking up.
                return chain
        if cur == root_resolved:
            break
        parent = cur.parent
        if parent == cur:
            break  # filesystem root reached
        cur = parent
    return chain
```

In `build()`, inside the second pass after the `anchors_in_dir` block:

```python
    # Third pass: walk agents_md chain for each entry.
    for rel, entry in files_map.items():
        entry["agents_md"] = _agents_md_chain(Path(rel), repo_root)
```

- [ ] **Step 2: Run all builder tests, confirm PASS**

```bash
pytest tests/test_context_surfacing.py -v -k "builder"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-surface): walk AGENTS.md chain per file"
```

### Task 10: Test — ADR cross-reference

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
def test_builder_cross_refs_adrs_that_mention_file(tmp_path: Path) -> None:
    """An ADR file under docs/adr/ that mentions a relative file path in
    its body should appear in that file's `adrs` list."""
    _init_repo_with_files(tmp_path, {
        "src/db/reader.py": "# AIDEV-NOTE: x\n",
        "docs/adr/0001-clickhouse.md": (
            "# 0001 ClickHouse as warehouse\n\n"
            "Affects `src/db/reader.py` and `src/db/writer.py`.\n"
        ),
        "docs/adr/0002-unrelated.md": "# 0002 — not relevant\n",
    })

    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"]["src/db/reader.py"]["adrs"] == [
        "docs/adr/0001-clickhouse.md"
    ]
```

- [ ] **Step 2: Run, confirm FAIL**

### Task 11: Implement ADR cross-reference

**Files:**
- Modify: `scripts/build-context-map.py`

- [ ] **Step 1: Add helper + fourth pass**

Add after `_agents_md_chain`:

```python
def _adr_index(repo_root: Path) -> list[tuple[str, str]]:
    """Return list of (relpath, body_text) for every docs/adr/*.md
    except README and template files. Read once, queried per file."""
    adr_dir = repo_root / "docs" / "adr"
    if not adr_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for p in sorted(adr_dir.glob("*.md")):
        name = p.name.lower()
        if name in {"readme.md"} or name.startswith("0000-"):
            continue  # skip index + template
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.append((p.relative_to(repo_root).as_posix(), body))
    return out
```

In `build()`, replace the third pass with a combined third+fourth pass:

```python
    adrs = _adr_index(repo_root)
    for rel, entry in files_map.items():
        entry["agents_md"] = _agents_md_chain(Path(rel), repo_root)
        # ADR cross-ref: ADR body must mention the file path with a word-boundary
        # before and a non-extension-continuation character after, so `src/api.py`
        # in the ADR matches `src/api.py` but NOT `src/api.pyc` or `src/api.py.bak`.
        # Pattern: optional `[\s\`(<\[]` before, optional `[\s\`)>\]:.,]` (or EOF) after.
        entry["adrs"] = [
            adr_rel for adr_rel, body in adrs
            if re.search(
                r"(?<![A-Za-z0-9_./-])" + re.escape(rel) + r"(?![A-Za-z0-9_/-])",
                body,
            )
        ]
```

- [ ] **Step 2: Run all builder tests, confirm PASS**

```bash
pytest tests/test_context_surfacing.py -v -k "builder"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-surface): cross-reference ADRs that mention each file"
```

### Task 12: Test — `--check` mode catches drift

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
def test_builder_check_mode_exits_1_on_drift(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {"src/x.py": "# AIDEV-NOTE: hi\n"})
    # First run: write the manifest
    subprocess.run([PYTHON, str(BUILDER), "--quiet"], cwd=str(tmp_path),
                   check=True, timeout=30, capture_output=True)

    # Mutate source so regen would differ
    (tmp_path / "src/x.py").write_text("# AIDEV-NOTE: changed!\n", encoding="utf-8")

    result = subprocess.run([PYTHON, str(BUILDER), "--check"],
                             cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, f"expected drift exit 1, got {result.returncode}"
    assert "DRIFT" in result.stderr
```

- [ ] **Step 2: Run, confirm PASS (`--check` already implemented in skeleton)**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): regression for builder --check drift detection"
```

---

## Phase 2 — PreToolUse hook (TDD)

### Task 13: Test — hook is silent when manifest is missing

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add helpers + first test**

```python
def _run_hook(stdin_payload: dict, *, cwd: Path, timeout: int = 10):
    env = os.environ.copy()
    env.pop("XDG_STATE_HOME", None)
    return subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=timeout,
    )


def _read_payload(file_path: str) -> dict:
    return {"tool_name": "Read", "tool_input": {"file_path": file_path}}


@hook_pytestmark
def test_hook_silent_when_manifest_missing(tmp_path: Path) -> None:
    """A repo without .claude-leverage-context-map.json must produce
    zero stdout (no JSON) and exit 0 — the hook never breaks anyone
    who has not opted in."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"expected silent, got {result.stdout!r}"
```

- [ ] **Step 2: Run, confirm FAIL (hook doesn't exist)**

```bash
pytest tests/test_context_surfacing.py::test_hook_silent_when_manifest_missing -v
```

### Task 14: Implement hook skeleton (manifest-missing path only)

**Files:**
- Create: `scripts/hooks/context-surface.sh`

- [ ] **Step 1: Write the hook**

```bash
#!/usr/bin/env bash
# context-surface.sh
#
# Claude Code / Codex PreToolUse hook (Read|Edit|Write|MultiEdit matcher).
#
# Surfaces just-in-time context for the file the agent is about to read
# or edit: AIDEV anchors in the file + sibling files, parent AGENTS.md
# chain, related ADRs. Reads a pre-built manifest at
# .claude-leverage-context-map.json (built by scripts/build-context-map.py).
#
# Design goal: reduce per-session token tax from leverage docs by NOT
# preemptively loading them — surface only what's relevant per tool call.
#
# Graceful no-op behavior:
#   - manifest missing            → silent, exit 0
#   - file not in manifest        → silent, exit 0
#   - file in manifest, no items  → silent, exit 0
#   - manifest corrupt JSON       → silent, exit 0 (warn to stderr once per session)
#   - no JSON parser on PATH      → silent, exit 0
#   - cwd outside git repo        → silent, exit 0
#
# Output (when context found):
#   stdout: JSON {hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:"..."}}
#   exit:   0
#
# Tunables (env vars):
#   CLAUDE_LEVERAGE_CTX_MAX_CHARS=4096       cap on additionalContext size
#   CLAUDE_LEVERAGE_CTX_MAX_SIBLINGS=5       cap on anchors_in_dir lines
#   CLAUDE_LEVERAGE_CTX_DISABLE=1            opt-out entirely
#
# See docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md.

set -euo pipefail

# Opt-out kill switch.
if [ "${CLAUDE_LEVERAGE_CTX_DISABLE:-0}" = "1" ]; then
  exit 0
fi

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/json_parse.sh"

has_parser || exit 0

# canon_path: normalize a path so paths from different sources (Claude Code's
# tool_input.file_path, git rev-parse output, cygpath, raw env vars) compare
# equal. Identical logic to scripts/hooks/ai-first-nudge.sh — duplicated for
# isolation; if a THIRD hook needs it, promote to json_parse.sh.
#
# Handles: backslash → forward slash, Windows drive-letter case (cygpath -m),
# relative → absolute (Python abspath fallback).
canon_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m -- "$p" 2>/dev/null && return
  fi
  local PY
  PY=$(command -v python3 || command -v python || true)
  if [ -n "$PY" ]; then
    printf '%s' "$p" | "$PY" -c '
import os, sys
print(os.path.abspath(sys.stdin.read()).replace("\\", "/"), end="")
' 2>/dev/null && return
  fi
  printf '%s' "$p"
}

read_stdin

# We only care about a few tools; on anything else, exit silently.
tool=$(get_field '.tool_name' 2>/dev/null) || exit 0
case "$tool" in
  Read|Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

# Resolve repo root.
cwd_hook=$(get_field '.cwd' 2>/dev/null)
[ -n "$cwd_hook" ] || cwd_hook=$(pwd 2>/dev/null) || exit 0
repo_root=$(git -C "$cwd_hook" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$repo_root" ] || exit 0

manifest="$repo_root/.claude-leverage-context-map.json"
[ -f "$manifest" ] || exit 0

exit 0  # rest of the implementation lands in later tasks
```

- [ ] **Step 2: Mark executable + run test, confirm PASS**

```bash
chmod +x scripts/hooks/context-surface.sh
git update-index --add --chmod=+x scripts/hooks/context-surface.sh
pytest tests/test_context_surfacing.py::test_hook_silent_when_manifest_missing -v
```

- [ ] **Step 3: Commit**

```bash
git add scripts/hooks/context-surface.sh tests/test_context_surfacing.py
git commit -m "feat(context-surface): PreToolUse hook skeleton with manifest-missing path"
```

### Task 15: Test — hook emits additionalContext when manifest has the file

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add helper + test**

```python
def _make_manifest(files_map: dict) -> dict:
    return {
        "_meta": {
            "schema_version": 1,
            "generated_at": "2026-05-26T00:00:00+00:00",
            "generator": "scripts/build-context-map.py",
            "file_count": len(files_map),
            "anchor_count": sum(len(v.get("anchors_in_file", [])) for v in files_map.values()),
            "repo_root": ".",
        },
        "files": files_map,
    }


def _seed_manifest(repo: Path, files_map: dict) -> None:
    (repo / ".claude-leverage-context-map.json").write_text(
        json.dumps(_make_manifest(files_map), indent=2), encoding="utf-8",
    )


@hook_pytestmark
def test_hook_emits_context_for_file_in_manifest(tmp_path: Path) -> None:
    """When the agent Reads a file that has anchors in the manifest, the
    hook emits hookSpecificOutput.additionalContext containing the
    anchors with file:line prefixes."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/db/reader.py": {
            "anchors_in_file": [
                {"line": 29, "type": "AIDEV-NOTE", "text": "never use 'limit' as a param key"}
            ],
            "anchors_in_dir": [],
            "agents_md": [],
            "adrs": [],
        },
    })

    payload = _read_payload(str(tmp_path / "src/db/reader.py"))
    result = _run_hook(payload, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "expected JSON, got empty"
    payload_out = json.loads(result.stdout)
    hso = payload_out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    ctx = hso["additionalContext"]
    assert "[claude-leverage:context-surface]" in ctx
    assert "src/db/reader.py" in ctx
    assert "L29" in ctx
    assert "limit" in ctx
```

- [ ] **Step 2: Run, confirm FAIL**

### Task 16: Implement core lookup + emit

**Files:**
- Modify: `scripts/hooks/context-surface.sh`

- [ ] **Step 1: Replace the trailing `exit 0` with real implementation**

Replace the last `exit 0` line with:

```bash
# Extract file_path from tool_input. Path may be absolute or relative;
# canon_path normalizes backslashes, drive-letter case, and absolute form.
file_raw=$(get_field '.tool_input.file_path' 2>/dev/null)
[ -n "$file_raw" ] || exit 0

file_canon=$(canon_path "$file_raw")
repo_canon=$(canon_path "$repo_root")

# Make file path relative to repo_root for manifest lookup. If file is
# outside the repo (rare but possible — agent reads a file under $HOME),
# pass it through verbatim; manifest lookup will miss and the hook will
# exit silently.
case "$file_canon" in
  "$repo_canon"/*) file_rel=${file_canon#"$repo_canon"/} ;;
  *)               file_rel="$file_canon" ;;
esac

# Single Python subprocess does manifest load + lookup + formatting +
# JSON encoding all in one process. Two subprocesses cost 300-500ms p99
# on Windows Python cold start; merging halves the budget.
python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi
[ -n "$python_bin" ] || exit 0

MAX_CHARS="${CLAUDE_LEVERAGE_CTX_MAX_CHARS:-4096}"
MAX_SIBLINGS="${CLAUDE_LEVERAGE_CTX_MAX_SIBLINGS:-5}"
VERBOSE="${CLAUDE_LEVERAGE_CTX_VERBOSE:-0}"
EXPECTED_BUILDER="1.8.0"

# Single heredoc: load manifest → look up file → format additionalContext
# → emit hookSpecificOutput JSON. Exits silently (no stdout) when there is
# nothing to surface, so the bash caller can blindly forward stdout.
MANIFEST_PATH="$manifest" FILE_REL="$file_rel" \
  MAX_CHARS="$MAX_CHARS" MAX_SIBLINGS="$MAX_SIBLINGS" \
  VERBOSE="$VERBOSE" EXPECTED_BUILDER="$EXPECTED_BUILDER" \
  "$python_bin" - <<'PY'
import json, os, sys

manifest_path = os.environ["MANIFEST_PATH"]
file_rel = os.environ["FILE_REL"]
max_chars = int(os.environ.get("MAX_CHARS", "4096"))
max_siblings = int(os.environ.get("MAX_SIBLINGS", "5"))
verbose = os.environ.get("VERBOSE", "0") not in ("", "0", "false", "False")
expected_builder = os.environ.get("EXPECTED_BUILDER", "")

try:
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

# Graceful degradation on schema mismatch: if the manifest was built by a
# materially older builder, skip rather than risk emitting nonsense fields.
meta = manifest.get("_meta", {})
if expected_builder and meta.get("schema_version") not in (None, 1):
    sys.exit(0)

entry = manifest.get("files", {}).get(file_rel)
if not entry:
    sys.exit(0)

parts = ["[claude-leverage:context-surface]"]

anchors_in_file = entry.get("anchors_in_file") or []
if anchors_in_file:
    parts.append(f"AIDEV anchors in {file_rel}:")
    for a in anchors_in_file:
        kind = a.get("type", "AIDEV-NOTE").replace("AIDEV-", "")
        deadline = f"(by:{a['deadline']})" if a.get("deadline") else ""
        parts.append(f"  L{a['line']} {kind}{deadline}: {a.get('text','')}")

anchors_in_dir = entry.get("anchors_in_dir") or []
if anchors_in_dir:
    parts.append("")
    parts.append("Anchors in same directory:")
    shown = anchors_in_dir[:max_siblings]
    for a in shown:
        kind = a.get("type", "AIDEV-NOTE").replace("AIDEV-", "")
        parts.append(f"  {a.get('file','?')}:{a.get('line','?')} {kind}: {a.get('text','')}")
    if len(anchors_in_dir) > max_siblings:
        parts.append(f"  (+{len(anchors_in_dir) - max_siblings} more — see manifest)")

# AGENTS.md and ADR refs are gated behind VERBOSE because the Run-3
# experiment showed that even surfacing "see X" is wasted tax when the
# task has no specific trap. The two anchor sections above carry the
# load-bearing trap-catch value; the rest is supplementary.
if verbose:
    agents_md = entry.get("agents_md") or []
    if agents_md:
        parts.append("")
        parts.append("For project conventions, see (Read on demand):")
        parts.append(f"  {', '.join(agents_md)}")

    adrs = entry.get("adrs") or []
    if adrs:
        parts.append("")
        parts.append("Related ADRs:")
        for a in adrs:
            parts.append(f"  {a}")

# If only the marker line is present (no actual content), suppress entirely.
if len(parts) <= 1:
    sys.exit(0)

out = "\n".join(parts)
if len(out) > max_chars:
    out = out[: max_chars - 50].rstrip() + f"\n... (truncated; cap={max_chars})"

# Emit the full hookSpecificOutput JSON in the same process — saves a
# second Python cold-start.
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": out,
    }
}))
PY
exit 0
```

- [ ] **Step 2: Run the test, confirm PASS**

```bash
pytest tests/test_context_surfacing.py::test_hook_emits_context_for_file_in_manifest -v
```

- [ ] **Step 3: Commit**

```bash
git add scripts/hooks/context-surface.sh tests/test_context_surfacing.py
git commit -m "feat(context-surface): emit additionalContext from manifest lookup"
```

### Task 17: Test — hook handles Edit / Write / MultiEdit tools

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add parametrized test**

```python
@hook_pytestmark
@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
def test_hook_fires_for_edit_family_tools(tmp_path: Path, tool: str) -> None:
    """Edit/Write/MultiEdit all carry file_path the same way as Read."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "watch out"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    payload = {"tool_name": tool, "tool_input": {"file_path": str(tmp_path / "src/x.py")}}
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    assert "watch out" in result.stdout


@hook_pytestmark
@pytest.mark.parametrize("tool", ["Bash", "Grep", "Glob", "Agent", "Skill"])
def test_hook_skips_non_file_tools(tmp_path: Path, tool: str) -> None:
    """Non-file-targeting tools never trigger the surface."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "x"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    # Even with manifest present, wrong tool → silent
    payload = {"tool_name": tool, "tool_input": {"command": "ls"}}
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
```

- [ ] **Step 2: Run, confirm PASS (already implemented)**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): cover Edit/Write/MultiEdit fire + non-file tools silent"
```

### Task 18: Test — Windows backslash path normalization

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_normalizes_windows_backslash_path(tmp_path: Path) -> None:
    """Claude Code on Git Bash for Windows may deliver paths with
    backslashes. Hook must normalize before manifest lookup."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/db/reader.py": {
            "anchors_in_file": [{"line": 29, "type": "AIDEV-NOTE", "text": "limit trap"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })

    # Simulate Windows-style absolute path
    win_path = str(tmp_path).replace("/", "\\") + r"\src\db\reader.py"
    result = _run_hook({"tool_name": "Read", "tool_input": {"file_path": win_path}}, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip(), f"expected emission, got {result.stdout!r}"
    assert "limit trap" in result.stdout
```

- [ ] **Step 2: Run, confirm PASS (skeleton already normalizes)**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): regression for Windows backslash path normalization"
```

### Task 19: Test — corrupt manifest is silent

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_silent_on_corrupt_manifest(tmp_path: Path) -> None:
    """Manifest file exists but is unparseable JSON — never crash, never
    block, just no-op silently. This is the safety-critical degradation
    path."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    (tmp_path / ".claude-leverage-context-map.json").write_text(
        "{ this is not valid json", encoding="utf-8",
    )
    payload = _read_payload(str(tmp_path / "src/x.py"))
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
```

- [ ] **Step 2: Run, confirm PASS (Python `json.JSONDecodeError` caught in heredoc → `sys.exit(0)`)**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): regression for corrupt manifest silent fallback"
```

### Task 20: Test — opt-out kill switch

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_opt_out_via_env_var(tmp_path: Path) -> None:
    """CLAUDE_LEVERAGE_CTX_DISABLE=1 makes the hook a no-op regardless
    of manifest state — escape hatch for users who want it off."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "important"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    payload = _read_payload(str(tmp_path / "src/x.py"))

    env = os.environ.copy()
    env["CLAUDE_LEVERAGE_CTX_DISABLE"] = "1"
    env.pop("XDG_STATE_HOME", None)
    result = subprocess.run(
        [BASH, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
```

- [ ] **Step 2: Run, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): regression for CLAUDE_LEVERAGE_CTX_DISABLE opt-out"
```

### Task 21: Test — output capped at MAX_CHARS

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_truncates_at_cap(tmp_path: Path) -> None:
    """A file with many huge anchors should be truncated, never emit
    >10K chars (Claude Code's hard limit)."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    big_anchors = [
        {"line": i, "type": "AIDEV-NOTE", "text": "x" * 200}
        for i in range(1, 101)
    ]
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": big_anchors,
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    payload = _read_payload(str(tmp_path / "src/x.py"))
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 4096 + 100, f"context size {len(ctx)} exceeds budget"
    assert "truncated" in ctx
```

- [ ] **Step 2: Run, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): regression for output cap + truncation marker"
```

### Task 21a: Test — file in manifest with all-empty arrays = silent

Reviewer feedback: the hook's "suppress if only marker line" branch was implemented but never tested. Critical for the no-tax case where a file appears in the manifest because anchors were deleted (entry stale) — should silently no-op, not emit a marker-only system reminder.

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_silent_when_all_arrays_empty(tmp_path: Path) -> None:
    """File is in manifest but every list is empty — agent gets nothing.
    Prevents emitting a useless `[claude-leverage:context-surface]` marker
    with no content."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [],
            "anchors_in_dir": [],
            "agents_md": [],
            "adrs": [],
        },
    })
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"expected silent, got {result.stdout!r}"
```

- [ ] **Step 2: Run, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): silent when manifest entry is all-empty"
```

### Task 21b: Test — verbose mode surfaces agents_md and adrs

The hook defaults to anchors-only (the value-bearing content per the Run-3 finding); verbose mode adds the supplementary refs. Make sure the env var actually toggles behavior.

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_verbose_mode_includes_agents_md_and_adrs(tmp_path: Path) -> None:
    """CLAUDE_LEVERAGE_CTX_VERBOSE=1 → emit project-conventions reminder
    and Related ADRs sections. Default (off) suppresses them even when
    the manifest entry contains them, per Run-3 token-tax finding."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "stay sharp"}],
            "anchors_in_dir": [],
            "agents_md": ["src/AGENTS.md", "AGENTS.md"],
            "adrs": ["docs/adr/0001-foo.md"],
        },
    })
    payload = _read_payload(str(tmp_path / "src/x.py"))

    # Default (verbose off): anchors only, NO agents_md / adrs sections
    result = _run_hook(payload, cwd=tmp_path)
    ctx_default = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "stay sharp" in ctx_default
    assert "src/AGENTS.md" not in ctx_default
    assert "0001-foo.md" not in ctx_default

    # Verbose on: both sections present
    env = os.environ.copy()
    env["CLAUDE_LEVERAGE_CTX_VERBOSE"] = "1"
    env.pop("XDG_STATE_HOME", None)
    result = subprocess.run(
        [BASH, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=10,
    )
    ctx_verbose = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "src/AGENTS.md" in ctx_verbose
    assert "AGENTS.md" in ctx_verbose
    assert "docs/adr/0001-foo.md" in ctx_verbose
```

- [ ] **Step 2: Run, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): CLAUDE_LEVERAGE_CTX_VERBOSE gates agents_md and adrs"
```

### Task 21c: Test — partially-flushed manifest does not crash hook

Reviewer flagged: the `os.replace()` atomic write closes the partial-flush window, but the hook must still degrade gracefully if a third party (or older builder pre-atomic-write) leaves a half-written manifest behind. A truncated-mid-array file is still detectable JSON-corruption — should silently no-op.

**Files:**
- Modify: `tests/test_context_surfacing.py`

- [ ] **Step 1: Add test**

```python
@hook_pytestmark
def test_hook_silent_on_truncated_manifest(tmp_path: Path) -> None:
    """Manifest exists but was truncated mid-array (simulates a non-atomic
    write race or partial-disk-write). Hook must not raise, must not
    block, must not emit; just silently exit 0."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    # Valid-looking start but truncated inside the "files" object — json.load
    # will raise JSONDecodeError on this, which the hook must catch.
    (tmp_path / ".claude-leverage-context-map.json").write_text(
        '{"_meta":{"schema_version":1},"files":{"src/x.py":{"anchors_in_file":[{"line":1,',
        encoding="utf-8",
    )
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
```

- [ ] **Step 2: Run, confirm PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): silent on partially-flushed manifest"
```

---

## Phase 3 — Wire the hook into both runtimes

### Task 22: Register in hooks/hooks.json (Claude Code)

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Add new PreToolUse matcher block**

In the `"PreToolUse"` array, add a new entry alongside the existing `"Bash"` matcher block:

```json
{
  "matcher": "Read|Edit|Write|MultiEdit",
  "hooks": [
    {
      "type": "command",
      "command": "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/context-surface.sh",
      "timeout": 5
    }
  ]
}
```

The full `PreToolUse` array after the edit should look like:

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/block-secrets-precommit.sh" },
      { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/block-dangerous-git.sh" }
    ]
  },
  {
    "matcher": "Read|Edit|Write|MultiEdit",
    "hooks": [
      { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/context-surface.sh", "timeout": 5 }
    ]
  }
]
```

- [ ] **Step 2: Validate JSON parses**

```bash
python -c "import json; json.load(open('hooks/hooks.json'))" && echo OK
```

### Task 23: Register in .codex/hooks.json (Codex)

**Files:**
- Modify: `.codex/hooks.json`

- [ ] **Step 1: Add the parallel block** (using `^X$|^Y$` regex style consistent with other Codex matchers in this file)

```json
{
  "matcher": "^Read$|^Edit$|^Write$|^MultiEdit$",
  "hooks": [
    {
      "type": "command",
      "command": "__CLAUDE_LEVERAGE_DIR__/scripts/hooks/context-surface.sh",
      "statusMessage": "Surfacing context for file",
      "timeout": 5
    }
  ]
}
```

Insert as a second block inside the `"PreToolUse"` array, after the existing `^Bash$` block.

- [ ] **Step 2: Validate JSON**

```bash
python -c "import json; json.load(open('.codex/hooks.json'))" && echo OK
```

- [ ] **Step 3: Commit (registration in both runtimes is a single logical change)**

```bash
git add hooks/hooks.json .codex/hooks.json
git commit -m "feat(context-surface): wire hook into Claude Code + Codex PreToolUse"
```

### Task 23a: Add `.gitattributes` for committed manifest

Reviewer feedback: a 234-entry sorted-JSON manifest committed to the repo will conflict on every branch that touches anchors. `merge=union` is the standard workaround for line-based JSON that just appends sections, but for our deeply-nested manifest the right call is `merge=ours` — pick the local version on conflict, then `/refresh-context-map` regenerates. Either way: do not let merge conflicts on this file become a friction.

**Files:**
- Create or Modify: `.gitattributes`

- [ ] **Step 1: Append the rule**

```bash
echo ".claude-leverage-context-map.json merge=ours" >> .gitattributes
```

If the repo already has `.gitattributes` with rules for other files, add the new line alongside them.

- [ ] **Step 2: Confirm git knows about the strategy**

```bash
git check-attr merge .claude-leverage-context-map.json
# Expected: .claude-leverage-context-map.json: merge: ours
```

- [ ] **Step 3: Commit**

```bash
git add .gitattributes
git commit -m "chore(context-surface): merge=ours for context-map to reduce conflicts"
```

---

## Phase 4 — Smoke test in a real repo

### Task 24: Build manifest in coinsense after/ and verify shape

**Note:** This phase verifies the implementation against the real-world coinsense `after/` tree from the A/B experiment harness. Read-only validation — does NOT commit anything in coinsense.

- [ ] **Step 1: Build the manifest in coinsense-ab/after/**

```bash
cd /c/Users/filip/Desktop/Python/coinsense-ab/after
python /c/Users/filip/Desktop/Python/claude-leverage/scripts/build-context-map.py
```

Expected output: a single line `Wrote ./.claude-leverage-context-map.json (<N> files, <M> anchors)` where N>0 and M>0.

- [ ] **Step 2: Sanity-check the manifest content**

```bash
python -c "
import json
with open('.claude-leverage-context-map.json') as f:
    m = json.load(f)
print('files:', m['_meta']['file_count'])
print('anchors:', m['_meta']['anchor_count'])
# Spot check the limit-trap anchor
for path, entry in m['files'].items():
    for a in entry['anchors_in_file']:
        if 'limit' in a['text'].lower() and 'CH 25.4' in a['text']:
            print('FOUND limit-trap anchor:', path, 'L', a['line'])
            break
"
```

Expected: prints the file count, anchor count, and confirms the limit-trap anchor is in the manifest at the right location.

- [ ] **Step 3: Drive the hook manually with a real file path**

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":"'$(pwd)'/classes/db/clickhouse_reader.py"}}' \
  | /c/Users/filip/Desktop/Python/claude-leverage/scripts/hooks/context-surface.sh
```

Expected: JSON on stdout containing `additionalContext` with the limit-trap anchor surfaced.

- [ ] **Step 4: Clean up the manifest from coinsense-ab/after/ (so it doesn't pollute the A/B harness)**

```bash
rm .claude-leverage-context-map.json
```

(No commit — this phase is read-only validation.)

### Task 25: Performance benchmark

- [ ] **Step 1: Time the hook on a populated manifest**

In the claude-leverage repo (after building its own manifest):

```bash
cd /c/Users/filip/Desktop/Python/claude-leverage
python scripts/build-context-map.py
time (for i in $(seq 1 50); do
  echo '{"tool_name":"Read","tool_input":{"file_path":"'$(pwd)'/scripts/hooks/context-surface.sh"}}' \
    | scripts/hooks/context-surface.sh > /dev/null
done)
```

Expected: total wall time under 5 seconds for 50 invocations = under 100ms per call on average. If it exceeds, profile with `python -X cprofile` and optimize.

- [ ] **Step 2: Verify manifest size is sane**

```bash
ls -lh .claude-leverage-context-map.json
```

Expected: well under 2 MB.

- [ ] **Step 3: Clean up the temporary manifest before continuing** (or keep it if it makes sense for this repo — see Task 32)

---

## Phase 5 — User-facing skill to rebuild the manifest

### Task 26: Create `/refresh-context-map` skill

**Files:**
- Create: `skills/refresh-context-map/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: refresh-context-map
description: USE WHEN AIDEV anchors / per-dir AGENTS.md / ADRs have changed in this repo and the smart-context-surfacing hook needs an updated manifest. Rebuilds `.claude-leverage-context-map.json` at the repo root by running `scripts/build-context-map.py`. Read-only on source — only writes the manifest.
---

# refresh-context-map

Rebuild the smart-context-surface manifest used by the PreToolUse hook
(`scripts/hooks/context-surface.sh`). See
`docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md` for the
design rationale.

## When to invoke

- After adding / moving / deleting AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION anchors.
- After adding / removing per-directory AGENTS.md files.
- After adding new ADRs that reference specific source files.
- When the agent notices stale context being surfaced (`/stack-check` also
  flags this).
- Once per significant refactor that moved a lot of files.

## When NOT to invoke

- On every commit — pre-commit hook (opt-in via `.githooks/`) does it
  automatically.
- When you do not have the smart-context-surfacing stack adopted (no
  `.claude-leverage-context-map.json` present means nothing breaks).

## What it does

Runs:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/build-context-map.py
```

from the repo root. The script:

1. Walks every git-tracked file, scanning for `AIDEV-NOTE` / `AIDEV-TODO` / `AIDEV-QUESTION` anchors.
2. For each file with anchors, indexes:
   - Anchors inside the file
   - Anchors in sibling files (same directory)
   - The chain of `AGENTS.md` from `dirname(file)` to repo root
   - ADR files (`docs/adr/*.md`) that mention this file path verbatim
3. Writes `.claude-leverage-context-map.json` at the repo root.

The PreToolUse hook then reads this manifest on every `Read/Edit/Write/MultiEdit`
and injects a per-file context slice via `hookSpecificOutput.additionalContext`.

## Verifying the rebuild

After running, the script prints a summary line:

```
Wrote ./.claude-leverage-context-map.json (234 files, 89 anchors)
```

Higher numbers than last time → you've added anchors / ADR references.
Lower numbers → anchors were deleted or files removed from `git ls-files`.

## Opting out per-session

Set `CLAUDE_LEVERAGE_CTX_DISABLE=1` in the environment to disable the
hook entirely without removing the manifest. Useful for one-off
diagnostic sessions where the context injection is noise.

## Verbose mode

By default the hook surfaces only AIDEV anchors (the trap-catching
content per the Run-3 token-tax finding). Set
`CLAUDE_LEVERAGE_CTX_VERBOSE=1` to also include per-dir `AGENTS.md`
references and related ADR paths in every injection. Useful in repos
where the per-dir AGENTS.md surface is dense and worth the extra
tokens; off by default to keep the tax minimal in the common case.

## Resolving merge conflicts on the manifest

The manifest is committed to the repo so every session sees a fresh
copy without a build step. `.gitattributes` declares
`merge=ours`, so a merge automatically keeps the local version on
conflict — **but the local version may be stale relative to the merged
codebase**. After any `git merge` that touched files with AIDEV
anchors, run:

```
/refresh-context-map
```

(or `python ${CLAUDE_PLUGIN_ROOT}/scripts/build-context-map.py`).
Commit the regenerated manifest alongside the merge commit. If a
pre-commit hook auto-rebuilds on commit, this is automatic.
```

- [ ] **Step 2: Commit**

```bash
git add skills/refresh-context-map/SKILL.md
git commit -m "feat(context-surface): /refresh-context-map skill"
```

---

## Phase 6 — Docs, ADR, version, CHANGELOG

### Task 27: Write ADR

**Files:**
- Create: `docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md`

- [ ] **Step 1: Run `ls docs/adr/` to confirm 0008 is the next number** (in case the user added more between this plan being written and execution)

```bash
ls docs/adr/
```

If 0008 is taken, bump to 0009 and substitute throughout. Otherwise proceed.

- [ ] **Step 2: Write the ADR using the project's MADR template**

```markdown
---
status: accepted
date: 2026-05-26
deciders: Filip Podstavec
consulted: claude-leverage's own A/B test harness
informed: stack users
---

# 0008. Smart context surfacing via PreToolUse hook

## Context and Problem Statement

The leverage stack's per-session token tax — measured at 116% increase in
Sonnet 4.6 cost on a small helper-add task in the coinsense A/B run3
experiment — comes primarily from the agent dutifully reading every
leverage artifact (root `AGENTS.md`, per-dir `AGENTS.md`, AIDEV-anchor-
bearing files) **preemptively** at orientation time, regardless of
whether those artifacts are relevant to the current task.

Run 1+2 (endpoint task with `limit` parameter trap) showed the tax is
worth paying when there's a documented gotcha to catch. Run 3 (helper
task without a specific trap) showed the tax is pure overhead when there
isn't.

How do we reduce the tax for non-trap tasks without losing the catch on
trap-bearing ones?

## Decision Drivers

- Tax should approach zero when no relevant context exists for a task.
- Catch rate for documented gotchas (the original value prop) must not
  drop — ideally rises because surfacing is *forced* at the moment of
  edit, not contingent on the agent choosing to read the right doc.
- Plugin must remain a graceful no-op for users who haven't adopted the
  anchor / AGENTS.md / ADR conventions.
- Must work cross-tool (Claude Code + Codex) without separate
  implementations of the actual logic.
- Adding latency on every `Read`/`Edit`/`Write` is dangerous — the
  agentic loop must not feel slower.

## Considered Options

1. **Slim root `AGENTS.md`** — fewer always-on tokens, but loses the catches that depend on the agent reading conventions before editing.
2. **Skill-based on-demand loading** — agent invokes a skill to surface context. Friction; depends on agent volunteering.
3. **PreToolUse hook with manifest-backed lookup** — surface a per-file slice of context only when the agent actually touches a relevant file. Selected.
4. **Real-time grep in the hook** — same as 3 but without a manifest. Rejected on latency grounds: `grep -rn 'AIDEV-' .` on a 10K-file repo per tool call exceeds the latency budget.

## Decision Outcome

**Chosen: Option 3.**

A new `scripts/build-context-map.py` walks `git ls-files`, extracts every
`AIDEV-NOTE/TODO/QUESTION` anchor, and writes
`.claude-leverage-context-map.json` at the repo root. The file maps each
source path to:

- Anchors in the file
- Anchors in sibling files
- The walking chain of `AGENTS.md` from `dirname(file)` to repo root
- ADR files that mention the path verbatim

A new `scripts/hooks/context-surface.sh` (`PreToolUse` on
`Read|Edit|Write|MultiEdit`) does an O(1) JSON lookup and emits a system
reminder via `hookSpecificOutput.additionalContext`. The hook is silent
when the manifest is missing or the file is unknown — repos that haven't
adopted the convention pay zero cost.

A `/refresh-context-map` skill lets the agent rebuild the manifest when
anchors / ADRs / per-dir docs change.

### Consequences

**Positive:**
- Per-session token tax for non-trap tasks should drop substantially
  because the agent no longer reads `AGENTS.md` preemptively for files
  it never touches.
- Trap-catch rate stays high — anchors are *forced* into context at the
  moment the agent reads the relevant file. No longer contingent on
  agent recall of `AGENTS.md`.
- Graceful no-op preserves backward compatibility — installing the v1.8.0
  plugin doesn't change behavior in repos without a manifest.
- One shell script serves both Claude Code and Codex thanks to identical
  `hookSpecificOutput.additionalContext` schema in both runtimes.
- AIDEV-NOTE convention gains real teeth — anchors are now load-bearing
  for the in-conversation surfacing, not just for grep.

**Negative:**
- Manifest must be rebuilt when anchors change. Pre-commit hook is the
  natural place; users without one will see stale context until they
  invoke `/refresh-context-map`.
- One more file in the repo root (`.claude-leverage-context-map.json`)
  for users to understand and not git-merge-conflict on.
- Per-tool-call latency ~50-80ms on top of normal tool overhead. Below
  perceptible threshold in interactive use but real.
- ADR cross-ref is verbatim path match — substring `src/foo.py` in an
  ADR body marks the file as related. False positives possible
  (e.g. ADR text "see src/foo.py for an example"). Acceptable for v1.

## Validation

- The hook must catch the `limit` parameter trap from the coinsense
  experiment (Run 4 of the eval harness).
- Per-session token cost on the helper task (Run 3 analog) should drop
  by at least 30% with no degradation in artifact quality.
- `pytest tests/test_context_surfacing.py` must remain green; new
  manifest + hook tests count as the regression net.

## References

- `docs/specs/2026-05-26-smart-context-surfacing/PLAN.md` — full plan.
- `coinsense-ab/results/run1/` and `coinsense-ab/results/run2/` — Opus
  endpoint-task A/B data showing the `limit`-trap catch is reproducible
  with the leverage stack on. Run-3 evidence (the Sonnet helper-task
  result with the 116% cost overhead that motivated *this* design) lives
  in the user's Claude Code transcript history at
  `~/.claude/projects/C--Users-filip-Desktop-Python-coinsense-ab-{before,after}/`
  — not committed because Run-3 task spec / `_RUN_NOTES.md` were captured
  out-of-band. Comparison numbers documented in
  `docs/specs/2026-05-26-smart-context-surfacing/PLAN.md` and reviewable
  via `coinsense-ab/analyze-runs.py` against either transcript.
- Claude Code PreToolUse hook spec — `https://code.claude.com/docs/en/hooks`
- Codex PreToolUse hook spec — `https://developers.openai.com/codex/hooks`
```

- [ ] **Step 3: Update `docs/adr/README.md` index if it exists** (check first with `cat docs/adr/README.md`)

If there's an ADR index table, add the row:

```markdown
| 0008 | Smart context surfacing via PreToolUse hook | accepted | 2026-05-26 |
```

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md docs/adr/README.md
git commit -m "docs(adr): 0008 — smart context surfacing via PreToolUse hook"
```

### Task 28: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Locate the "Commands available in this stack" table** (search for `## Commands available in this stack` heading)

Add a new row in alphabetical order:

```markdown
| `/refresh-context-map` | Rebuild `.claude-leverage-context-map.json` after anchor / per-dir AGENTS.md / ADR changes |
```

- [ ] **Step 2: Locate the "What's in it" section** (near the top) AND verify current counts BEFORE editing.

The exact wording has changed across versions. Run grep first to see what's actually there now:

```bash
grep -nE "(hooks|cross-tool skills|skills)" AGENTS.md | head -20
```

Then bump the hook count by 1 (was N → becomes N+1) and the skills count by 1, using whatever phrasing the current file uses. Add this entry in the hook bullet list:

```
- `context-surface` (PreToolUse) — emits AIDEV anchors relevant to the file being touched, via a pre-built manifest. Graceful no-op if `.claude-leverage-context-map.json` is missing. Verbose mode (`CLAUDE_LEVERAGE_CTX_VERBOSE=1`) also surfaces per-dir AGENTS.md + ADR refs.
```

- [ ] **Step 3: Add a new short section under "Security guardrails" called "Smart context surfacing"**

```markdown
### Smart context surfacing

Optional opt-in mechanism that surfaces just-in-time context for the file
the agent is about to read or edit, via the `context-surface` PreToolUse
hook. Activated by running `/refresh-context-map` (or `python
scripts/build-context-map.py`) once; the resulting
`.claude-leverage-context-map.json` is committed to the repo so every
session sees a fresh-enough copy.

The hook surfaces:
- AIDEV-NOTE / TODO / QUESTION anchors inside the file
- Anchors in sibling files in the same directory
- Chain of per-directory `AGENTS.md` from the file's dir to repo root
- ADR files that mention the file path verbatim

Per-tool-call latency: ~50-80ms. Opt-out per session via
`CLAUDE_LEVERAGE_CTX_DISABLE=1`. Graceful no-op in repos without a
manifest (zero impact on users who don't adopt). See
[ADR 0008](docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md).
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): document smart context surfacing + /refresh-context-map"
```

### Task 29: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Search for hook count mentions** (`grep -n "5 hooks\|hooks (security" README.md`)

Update every mention from 5 → 6 hooks.

- [ ] **Step 2: Update the "what's inside" table** (look for the table of components)

Add a row for `/refresh-context-map` if there's a skills table; add `context-surface` if there's a hooks table.

- [ ] **Step 3: If there's a "Recent additions" or "v1.8.0" section, append**

Brief 1-2 sentence note about smart context surfacing pointing at ADR 0008.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): smart context surfacing in v1.8.0"
```

### Task 30: Update hooks/README.md

**Files:**
- Modify: `hooks/README.md`

- [ ] **Step 1: Add the `context-surface` hook entry** in the same format as existing hooks (event, matcher, purpose, opt-out env var)

- [ ] **Step 2: Commit**

```bash
git add hooks/README.md
git commit -m "docs(hooks): document context-surface PreToolUse hook"
```

### Task 31: Bump version

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Inspect current versions** (`grep version .claude-plugin/plugin.json .claude-plugin/marketplace.json`) — they must match per CI invariant.

- [ ] **Step 2: Bump both from 1.7.0 to 1.8.0** using Edit tool on each file.

- [ ] **Step 3: Run version-sync check**

```bash
python scripts/check_version_sync.py
```

Expected: prints OK / matches.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(v1.8.0): version bump"
```

### Task 32: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add entry under a new `## v1.8.0 — 2026-05-26` section**

```markdown
## v1.8.0 — 2026-05-26

**New: smart context surfacing.**

- Added `scripts/build-context-map.py` — walks `git ls-files`, indexes
  AIDEV-NOTE / TODO / QUESTION anchors + per-dir AGENTS.md chain +
  ADR cross-references into `.claude-leverage-context-map.json`.
- Added `scripts/hooks/context-surface.sh` — PreToolUse hook on
  `Read|Edit|Write|MultiEdit`. O(1) manifest lookup, emits a per-file
  context slice via `hookSpecificOutput.additionalContext`. Graceful
  no-op when manifest is missing.
- Added `/refresh-context-map` skill for rebuilding the manifest.
- Cross-tool: same hook script and JSON schema works on Claude Code and
  Codex (both runtimes accept `hookSpecificOutput.additionalContext` per
  their PreToolUse specs).
- Opt-out: set `CLAUDE_LEVERAGE_CTX_DISABLE=1` per session.
- See [ADR 0008](docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md)
  for the design rationale, motivated by the coinsense A/B Run 3 result
  (helper-add task without a specific trap showed 116% Sonnet cost
  overhead vs. baseline — pure tax with no catch).
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): v1.8.0 — smart context surfacing"
```

---

## Phase 7 — Final verification

### Task 33: Run smoke-plugin.sh

- [ ] **Step 1: Run the full pre-push gate**

```bash
cd /c/Users/filip/Desktop/Python/claude-leverage
bash scripts/smoke-plugin.sh
```

- [ ] **Step 2: If anything fails, fix it and re-run.** Do NOT use `--no-verify` or skip the gate. Most-likely failure modes:

| Failure | Cause | Fix |
|---|---|---|
| `pytest` exits 1 | a new test broken | re-read the test, fix the code or test |
| `version sync` fails | bumped only one of plugin.json / marketplace.json | bump both to 1.8.0 |
| `codex agents parity` fails | unrelated drift — should not be touched by this branch | investigate via `git diff` |
| `shellcheck` warns on context-surface.sh | shell quirks in the script | fix per shellcheck advice |
| `pytest tests/test_plugin_integrity.py` fails | new files lack required structure | check that test's assertions |

- [ ] **Step 3: Wire `build-context-map.py --check` into smoke-plugin**

Add a new gate to `scripts/smoke-plugin.sh` so a forgotten manifest-rebuild surfaces in CI exactly the way version-sync drift does today. Insert after the existing `codex agents parity` block:

```bash
# ----------------------------------------------------------------------
# 5. context-map manifest is up to date
# ----------------------------------------------------------------------
say "5. .claude-leverage-context-map.json matches git ls-files"
if python scripts/build-context-map.py --check --quiet >$SCRATCH/ctxmap.log 2>&1; then
  say_pass "manifest in sync"
else
  say_fail "manifest drift — run: python scripts/build-context-map.py"
  cat $SCRATCH/ctxmap.log >&2
  failed=$((failed + 1))
fi
```

(Renumber subsequent `say` calls if there are any.)

- [ ] **Step 4: Rebuild manifest and verify smoke-plugin passes**

```bash
python scripts/build-context-map.py
git add .claude-leverage-context-map.json
bash scripts/smoke-plugin.sh
```

- [ ] **Step 5: Commit the manifest + smoke-plugin update + manifest itself**

```bash
git add scripts/smoke-plugin.sh .claude-leverage-context-map.json
git commit -m "chore(context-surface): wire --check into smoke-plugin + seed manifest"
```

- [ ] **Step 6: When all gates pass, no further commit** — gates are checks, not changes.

### Task 34: Final review of the feature branch

- [ ] **Step 1: Inspect the diff against main**

```bash
git log --oneline main..feat/smart-context-surfacing
git diff --stat main..feat/smart-context-surfacing
```

- [ ] **Step 2: Confirm all 10 tasks from the original TodoWrite list are accounted for** in commits.

- [ ] **Step 3: Confirm we did NOT push** (`git status` should show "Your branch is ahead of 'origin/main' by N commits.")

- [ ] **Step 4: Report back to the user** with the branch name + a 5-bullet summary of what was shipped, what's pending, and the next recommended action (e.g., re-run the coinsense A/B harness with this branch's hook active as Run 4 to validate the cost-vs-catch claim).

---

## Review feedback applied (2026-05-26)

After the initial plan was written, a critical-review subagent flagged
issues. The following are now incorporated into the relevant tasks (no
separate appendix — the fixes are inline):

| Reviewer issue | Where addressed |
|---|---|
| Path normalization (lowercase drive letter, mixed slash) | Task 14 — inlined `canon_path` helper from `ai-first-nudge.sh`; Task 16 — uses `canon_path` for both file and repo paths |
| Two Python heredocs blew Windows latency budget | Task 16 — merged into one heredoc (lookup + format + JSON emit in one process) |
| Cross-tool claim un-verified for Codex | Research stage confirmed Codex `developers.openai.com/codex/hooks` accepts identical `hookSpecificOutput.additionalContext` schema; documented in cross-tool section of this plan |
| Builder didn't gate binary files | Task 5 — added 8-KiB NUL-byte sniff |
| Symlinks could crash `.resolve()` / `.relative_to()` | Task 9 — wrapped in try/except, gracefully truncates chain |
| ADR substring match too loose | Task 11 — switched to word-boundary regex with `re.escape` |
| Manifest merge-conflict ergonomics undocumented | Task 23a — added `.gitattributes merge=ours`; skill (Task 26) documents the post-merge `/refresh-context-map` workflow |
| Race during rebuild → partial-write window | Task 3 — `_atomic_write` helper (write to `.tmp` then `os.replace`) |
| No CI gate for `--check` drift | Task 33 — wired `python scripts/build-context-map.py --check` into `smoke-plugin.sh` |
| Missing test: all-empty entry silent | Task 21a (new) |
| Missing test: partially-flushed manifest | Task 21c (new) |
| Verbose-vs-default mode for AGENTS.md/ADR refs | Task 16 — added `CLAUDE_LEVERAGE_CTX_VERBOSE` env var; Task 21b (new) tests both modes |
| Missing `_meta.builder_version` field | Manifest schema section; Task 3 + Task 5 inject; Task 16 gracefully degrades on mismatch |
| AGENTS.md hook count drift (verify before bumping) | Task 28 Step 2 — added explicit `grep -nE` invocation before edit |
| Run-3 evidence path inaccurate in ADR | Task 27 ADR text — corrected to point at transcripts location and `analyze-runs.py` instead of a non-existent `run3/` evidence dir |

## Self-review checklist

After writing the plan, I verified:

- **Spec coverage**: every requirement from the brainstorm (manifest, hook, cross-tool, opt-out, tests, docs, version bump, ADR, commit) is mapped to a Task.
- **No placeholders**: all "TBD"/"add appropriate"/"similar to Task N" patterns avoided. Each step has executable content.
- **Type consistency**: `MANIFEST_NAME = ".claude-leverage-context-map.json"`, `ANCHOR_RE`, helper function names (`_scan_anchors`, `_agents_md_chain`, `_adr_index`) match between Tasks 5/7/9/11.
- **Manifest schema**: documented in one place (top of plan); referenced consistently in builder + hook + test seed helpers.
- **TDD discipline**: every feature task pairs failing test → minimal impl → passing test → commit.
- **Frequent commits**: 25 separate commits across the plan, one per logical change.

## What's NOT in this plan (deferred)

- **Pre-commit hook to auto-rebuild manifest** — out of scope; user invokes manually or via `/refresh-context-map`. Add later if friction emerges.
- **Codex `apply_patch` handling** — file path extraction from patch text is fragile; deferred to a v1.9.x iteration once we measure how often Codex users hit this.
- **Glossary / architecture.yml integration** — these exist (`/glossary-init`, `/arch-map` skills shipped in v1.6.x) and are good candidates for v2 of the manifest schema; out of scope for v1.8.0.
- **Hook eval mode in `/stack-check`** — proposed in the brainstorm response; defer to a separate ADR + plan.
