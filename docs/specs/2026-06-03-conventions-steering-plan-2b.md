# Phase 2b — Conventions Steering: /conventions-init + nudge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the conventions loop usable on any repo (`/conventions-init` drafts `conventions.yml`) and add an advisory nudge when an edit *introduces* a casing/vague-name violation.

**Architecture:** A new importable `flag_blob_violations` in `score_adherence.py` scores an edit BLOB (not `--diff`, so it only flags what the edit adds). `ai-first-nudge.sh` calls it (gated on `conventions.yml` + `.py`) for a non-blocking advisory. `/conventions-init` is a pure SKILL.md following the `glossary-init` pattern, seeding casing from `score_adherence --repo`. Spec: `docs/specs/2026-06-03-conventions-steering-phase2-design.md` (Components 2 + 5).

**Tech Stack:** Python stdlib, bash hook, pytest, agentskills.io SKILL.md.

---

## Task 1: `flag_blob_violations` — the nudge's detection core

**Files:**
- Modify: `scripts/score_adherence.py` (append)
- Test: `tests/test_score_adherence.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_flag_blob_violations_flags_new_vague_and_casing():
    blob = (
        "def fetch_user(uid):\n"
        "    result = uid\n"          # 'result' vague (denylist)
        "    return result\n"
        "def DoThing():\n"            # function casing != snake_case
        "    return 1\n"
    )
    flags = sa.flag_blob_violations(blob, casing={"functions": "snake_case"},
                                    denylist=["result"])
    names = {f["name"] for f in flags}
    assert "result" in names
    assert "DoThing" in names
    assert "fetch_user" not in names   # clean


def test_flag_blob_violations_clean_blob_is_empty():
    blob = "def fetch_user(uid):\n    return uid\n"
    assert sa.flag_blob_violations(blob, casing={"functions": "snake_case"}) == []
```

Run `python -m pytest tests/test_score_adherence.py -k flag_blob -v` → FAIL.

- [ ] **Step 2: Implement** (append to `scripts/score_adherence.py`)

```python
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
```

- [ ] **Step 3: Run** `python -m pytest tests/test_score_adherence.py -k flag_blob -v` → PASS, then the whole file → green.

- [ ] **Step 4: Commit**
```bash
git add scripts/score_adherence.py tests/test_score_adherence.py
git commit -m "feat(scorer): flag_blob_violations for the conventions nudge"
```

---

## Task 2: `ai-first-nudge` convention-violation advisory

**Files:**
- Modify: `scripts/hooks/ai-first-nudge.sh`
- Test: `tests/test_hook_behavior.py`

Read `ai-first-nudge.sh` first. It already: sources `json_parse.sh`, resolves `tool`/`file_path`, applies ignore patterns, and has `per_dir_agents_md_nudge` (an independent function called near the end) and the LOC/anchor check. Add a THIRD independent check, `convention_violation_nudge`, called right after `per_dir_agents_md_nudge`.

The new function must:
1. Return early unless `file_path` ends in `.py`.
2. Resolve `repo_root` via `git -C "$(dirname "$file_path")" rev-parse --show-toplevel` (mirror the existing per-dir logic's probe for a non-existent dir); return if not in a repo or if `$repo_root/conventions.yml` does not exist.
3. Extract the edit blob the same way the existing LOC check does: `content` (Write), `new_string` (Edit), or the `edits[*].new_string` joined (MultiEdit). Reuse/duplicate that extraction.
4. Run a Python heredoc that imports `score_adherence` and `conventions` from the script's sibling `scripts/` dir is NOT possible (the hook lives in `scripts/hooks/`); use `scripts/` = `$(dirname "$0")/..`. Pass the blob via env var and `conventions.yml` path via env var; the Python:
   ```python
   import os, sys
   sys.path.insert(0, os.environ["SCRIPTS_DIR"])
   from conventions import parse_conventions
   from score_adherence import flag_blob_violations
   prof = parse_conventions(open(os.environ["CONV_PATH"], encoding="utf-8", errors="replace").read()) or {}
   flags = flag_blob_violations(os.environ.get("BLOB", ""),
                                casing=prof.get("casing"), denylist=prof.get("vague_denylist"))
   names = sorted({f["name"] for f in flags})
   print(",".join(names))
   ```
   where `SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`.
5. If the Python prints a non-empty list, emit a non-blocking advisory to stderr:
   `(claude-leverage: edit introduces names that drift from conventions.yml — <names>; prefer intent-revealing, repo-cased names)`
6. Frequency-cap per file per day using a SEPARATE cap file (e.g. `conv-nudges-$TODAY.txt`) so it doesn't collide with the anchor-nudge cap. Always `exit 0` / `return 0` — never block.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_hook_behavior.py`; it has `_run_hook`, `GIT`/`requires_git`, and writes payloads). Each writes a `conventions.yml` + runs the hook with an Edit payload in a tmp git repo.

```python
@requires_git
def test_nudge_fires_on_convention_violation_in_edit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")        # reuse the _git helper if present, else subprocess
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n"
        "  vague_denylist:\n    - result\n", encoding="utf-8")
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(repo / "svc.py"),
        "new_string": "def DoThing():\n    result = 1\n    return result\n"}}
    res = _run_hook(AI_FIRST_NUDGE, payload, cwd=repo, state_dir=tmp_path / "_state")
    assert res.returncode == 0
    assert "conventions.yml" in res.stderr
    assert "DoThing" in res.stderr or "result" in res.stderr


@requires_git
def test_nudge_silent_on_clean_edit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n", encoding="utf-8")
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(repo / "svc.py"),
        "new_string": "def fetch_user(uid):\n    return uid\n"}}
    res = _run_hook(AI_FIRST_NUDGE, payload, cwd=repo, state_dir=tmp_path / "_state")
    assert res.returncode == 0
    assert "conventions.yml" not in res.stderr


@requires_git
def test_nudge_silent_when_no_conventions_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(repo / "svc.py"),
        "new_string": "def DoThing():\n    result = 1\n    return result\n"}}
    res = _run_hook(AI_FIRST_NUDGE, payload, cwd=repo, state_dir=tmp_path / "_state")
    assert res.returncode == 0
    assert "conventions.yml" not in res.stderr
```

`AI_FIRST_NUDGE` is already a module constant. `_git` exists in `test_hook_behavior.py` (from the block-secrets tests) — reuse it; if its signature differs, call `subprocess.run(["git","init","-q"], cwd=repo, ...)` directly. Confirm the new violation tests FAIL first (no nudge yet).

- [ ] **Step 2: Implement** the `convention_violation_nudge` function and its call.

- [ ] **Step 3: Run** `python -m pytest tests/test_hook_behavior.py -k "nudge and (convention or clean or no_conventions)" -v` → PASS (skip without bash). Full file → green. `shellcheck scripts/hooks/ai-first-nudge.sh` → no new warnings.

- [ ] **Step 4: Commit**
```bash
git add scripts/hooks/ai-first-nudge.sh tests/test_hook_behavior.py
git commit -m "feat(ai-first-nudge): advisory on conventions drift in an edit blob"
```

---

## Task 3: `/conventions-init` skill

**Files:**
- Create: `skills/conventions-init/SKILL.md`
- Modify: `README.md` (skill count 14 → 15, four spots)

- [ ] **Step 1: Author `skills/conventions-init/SKILL.md`**

Follow the `skills/glossary-init/SKILL.md` shape exactly (frontmatter with `name`, `description` (USE WHEN…), `allowed-tools`, `argument-hint`; then What it does / When to invoke / Workflow / Hard rules / Tunables / What it does NOT do / Codex parity). Content:

```markdown
---
name: conventions-init
description: >
  USE WHEN setting up a repo for AI-first work (after /init-repo), or when the
  context-surface hook should start feeding repo conventions to agents before
  edits. Drafts `conventions.yml` at repo root: per-kind casing (inferred from
  the code), a vague-name denylist seed, directory roles, and a hand-filled
  house-rules block. Idempotent — never overwrites a populated file; re-running
  prints suggested additions for manual merge. Read-only on code; never invents
  house rules. After writing, run /refresh-context-map so the hook picks it up.
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(git rev-parse:*)
  - Bash(git ls-files:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(test:*)
argument-hint: "[--noninteractive]"
---

# /conventions-init

## What it does

Bootstraps `conventions.yml` at the repo root — the profile the `context-surface`
hook surfaces to an agent before it edits a source file (casing rules, a
vague-name denylist, directory roles, and divergent house rules the model cannot
infer). Block-style YAML only, so the stdlib fallback parser stays reliable.

It **infers** the mechanical parts (casing, structure) and **asks the user** for
the house rules — it never invents a convention the repo doesn't actually hold.

## When to invoke

- Setting up an AI-first repo, after `/init-repo`.
- When you want the plugin to start steering on this repo (no `conventions.yml`
  yet → the whole steering loop is a no-op).

Do NOT invoke for: per-function docs (docstrings), or to auto-write house rules
the team hasn't agreed on.

## Workflow

1. **Resolve repo root** (`git rev-parse --show-toplevel`); if not a repo, STOP
   and suggest `git init` / `/init-repo`.
2. **Detect mode.** If `conventions.yml` is absent → bootstrap. If it exists →
   do NOT rewrite it (stdlib YAML loses the human-written `consistency` comments);
   instead print the suggested draft below and tell the user to merge by hand.
3. **Infer casing.** Run `python scripts/score_adherence.py --repo .` if the
   plugin's scorer is available, and read `metrics.casing_consistency.by_kind[*]
   .dominant` for `functions` / `types` / `constants`. Python-first: if there are
   no `.py` files (or the scorer is absent), leave `casing` values blank with a
   comment for the user — never guess from an unsupported language.
4. **Seed structure roots.** List top-level + recognized source dirs (`src/`,
   `lib/`, `app/`, `scripts/`, `tests/`, …) that exist; write each as a root key
   with a blank role string for the user to fill.
5. **Seed the denylist** from the documented defaults (`data`, `result`, `tmp`,
   `handle`, `process`); the user can extend.
6. **Leave `consistency` as a commented template** — house rules are the user's
   to write. (Same "never invent" rule as `glossary-init`.)
7. **Write `conventions.yml`** (bootstrap mode) with the `schema_version` "1.x"
   comment, block-style. In existing-file mode, print the draft instead.
8. **Remind** the user to run `/refresh-context-map` so the manifest (and thus the
   hook) picks up the new conventions, and offer a one-line `AGENTS.md` pointer.
9. **Report** the path and which fields were inferred vs left for the user.

## Hard rules

- **Never invent house rules.** The `consistency` block is the user's; the skill
  only scaffolds it.
- **Never overwrite a populated `conventions.yml`.** Existing-file mode prints
  suggestions for manual merge (preserves the user's comments).
- **Never block.** Discoverability skill; advisory if the user declines.
- **Block-style YAML only** (no inline `{}`/`[]`) — keeps the stdlib fallback
  parser reliable.
- **Python-first casing.** Don't infer casing from unsupported languages; leave
  it blank for the user.

## Tunables

- `--noninteractive` — write the inferred skeleton with blank roles + a commented
  `consistency` block, no prompts.

## What this skill does NOT do

- Auto-write house rules or invent conventions the repo doesn't hold.
- Rebuild the context-map manifest — that's `/refresh-context-map`.
- Score or lint code — that's `score_adherence.py` / `/repo-doctor`.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. No tool-specific
divergence.
```

- [ ] **Step 2: Bump the skill count 14 → 15 in `README.md`** at: the `![Skills]` badge (line ~17), "pick up all 14 skills" (~128), "Copies all 14 skills" (~156), "confirm 14 skills appear" (~617). Use `15` in each.

- [ ] **Step 3: Run the suite + integrity checks**

Run: `python -m pytest tests/ -v` (the skill-frontmatter integrity test in `test_plugin_integrity.py` must accept the new skill; if it asserts a hardcoded skill count, update that number too). Then `python scripts/check_version_sync.py` (unaffected) and confirm no count assertion fails.

- [ ] **Step 4: Commit**
```bash
git add skills/conventions-init/SKILL.md README.md
git commit -m "feat(conventions-init): skill to draft conventions.yml + bump skill count"
```

---

## Self-Review

**Spec coverage (Phase 2b):** nudge blob-scoring (C1 fix) → Tasks 1-2; `/conventions-init` (Python-first casing, no-overwrite, never-invent) → Task 3. Both spec components done.

**Placeholder scan:** Task 1 has complete code; Tasks 2-3 give exact integration points + full SKILL.md content + test contracts (the hook/test files must be read and integrated into).

**Type consistency:** `flag_blob_violations(blob, casing, denylist)` returns `[{name, kind, reason}]`; the hook's Python reads `f["name"]`; `parse_conventions` returns `{casing, vague_denylist, …}` consumed as `prof.get("casing")` / `prof.get("vague_denylist")` — matches Phase 2a's shape. `_CASING_KEY` maps identifier kinds to `conventions.yml` casing keys consistently.

**Risk note:** the nudge must NEVER block (always exit 0) and must be silent when `conventions.yml` is absent or the file is non-Python — the three Task-2 tests pin exactly these. The C1 trap (scoring the file vs the edit) is avoided by scoring the blob only.
