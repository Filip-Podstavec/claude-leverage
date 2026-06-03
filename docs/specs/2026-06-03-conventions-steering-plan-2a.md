# Phase 2a — Conventions Steering Delivery Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deliver the repo's `conventions.yml` into the agent's pre-edit context for source files, via the existing context-map manifest + `context-surface` hook.

**Architecture:** New stdlib `scripts/conventions.py` parses `conventions.yml` (PyYAML if present, minimal block parser otherwise). `build-context-map.py` folds the parsed profile into `_meta.conventions`. `context-surface.sh` emits a compact conventions block for source-file edits, computing the directory role at runtime from `_meta.conventions.structure_roots`. Spec: `docs/specs/2026-06-03-conventions-steering-phase2-design.md`.

**Tech Stack:** Python 3.8+ stdlib (optional PyYAML), bash hook with embedded Python, pytest.

---

## File Structure

- **Create `scripts/conventions.py`** — `parse_conventions(text) -> dict | None` and `match_role(file_rel, roots) -> str | None`. Importable, the one home for conventions parsing/role logic, used by the builder and tested directly.
- **Modify `scripts/build-context-map.py`** — read `conventions.yml`, attach `_meta.conventions`, bump `BUILDER_VERSION`.
- **Modify `scripts/hooks/context-surface.sh`** — emit conventions block for source files (the embedded Python heredoc).
- **Create `tests/test_conventions.py`** — parser + role-match unit tests.
- **Modify `tests/test_context_surfacing.py`** — builder `_meta.conventions` test + hook delivery/negative tests + one integration test.
- **Create `conventions.yml`** (repo root, dogfood) and regenerate the manifest.
- **Create `templates/conventions.yml.example`**.

The documented `conventions.yml` is **block-style only** (no inline `{}`/`[]`) so the stdlib fallback parser stays simple and reliable.

---

## Task 1: `scripts/conventions.py` — parser + role matcher

**Files:**
- Create: `scripts/conventions.py`
- Test: `tests/test_conventions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_conventions.py
from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "conventions", REPO_ROOT / "scripts" / "conventions.py"
)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

SAMPLE = """\
schema_version: 1
naming:
  casing:
    functions: snake_case
    types: PascalCase
  vague_denylist:
    - data
    - result
structure:
  roots:
    "scripts/hooks/": "shell hooks; fail-open"
    "skills/": "one SKILL.md per dir"
  file_loc_ceiling: 400
consistency:
  - "Hooks must fail-open and exit 0 when a parser is absent."
  - "AIDEV anchors: all-caps, <=120 chars."
"""


def test_parse_conventions_extracts_normalized_profile():
    prof = conv.parse_conventions(SAMPLE)
    assert prof["casing"] == {"functions": "snake_case", "types": "PascalCase"}
    assert prof["vague_denylist"] == ["data", "result"]
    assert prof["structure_roots"]["skills/"] == "one SKILL.md per dir"
    assert prof["consistency"][0].startswith("Hooks must fail-open")
    assert len(prof["consistency"]) == 2


def test_parse_conventions_empty_or_garbage_returns_none():
    assert conv.parse_conventions("") is None
    assert conv.parse_conventions("not: [valid") is None or isinstance(
        conv.parse_conventions("not: [valid"), dict
    )


def test_match_role_longest_prefix():
    roots = {"scripts/": "scripts root", "scripts/hooks/": "hook scripts"}
    assert conv.match_role("scripts/hooks/context-surface.sh", roots) == "hook scripts"
    assert conv.match_role("scripts/build.py", roots) == "scripts root"
    assert conv.match_role("docs/x.md", roots) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_conventions.py -v`
Expected: FAIL — `scripts/conventions.py` missing.

- [ ] **Step 3: Write the implementation**

```python
# scripts/conventions.py
"""Parse a repo's conventions.yml into a normalized profile, and match a file
path to its directory role. Stdlib-only: uses PyYAML when importable, else a
minimal block-YAML parser for the documented (block-style) schema.
"""
from __future__ import annotations

try:
    import yaml as _yaml  # optional; the fallback parser handles its absence
except Exception:  # ImportError or a broken install
    _yaml = None


def _strip_comment(line: str) -> str:
    # Remove a trailing ` #...` comment but not a '#' inside quotes.
    out, in_q = [], ""
    for ch in line:
        if in_q:
            out.append(ch)
            if ch == in_q:
                in_q = ""
        elif ch in ('"', "'"):
            in_q = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _minimal_parse(text: str):
    """Indentation-based parser for the documented block schema. Returns nested
    dict/list. Not a general YAML parser — handles `key:`, `key: value`,
    `- item`, two-space nesting, quoted keys/values, and # comments."""
    root: dict = {}
    # stack of (indent, container); container is dict or list
    stack = [(-1, root)]
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if body.startswith("- "):
            item = _unquote(body[2:])
            if not isinstance(parent, list):
                continue
            parent.append(item)
            continue
        # key: or key: value  (split on the first ': ' or trailing ':')
        if body.endswith(":"):
            key = _unquote(body[:-1])
            child: dict = {}
            if isinstance(parent, dict):
                parent[key] = child
            stack.append((indent, child))
        else:
            # find the ':' that separates key from value (respect quotes)
            depth_q = ""
            split_at = -1
            for i, ch in enumerate(body):
                if depth_q:
                    if ch == depth_q:
                        depth_q = ""
                elif ch in ('"', "'"):
                    depth_q = ch
                elif ch == ":":
                    split_at = i
                    break
            if split_at < 0:
                continue
            key = _unquote(body[:split_at])
            val_raw = body[split_at + 1 :].strip()
            if val_raw == "":
                # could be a list-or-map block following; create list lazily as
                # dict, but the next '- ' line needs a list. Use a marker list.
                child_list: list = []
                if isinstance(parent, dict):
                    parent[key] = child_list
                stack.append((indent, child_list))
            else:
                if isinstance(parent, dict):
                    parent[key] = _unquote(val_raw)
    return root


def _normalize(data) -> dict | None:
    if not isinstance(data, dict) or not data:
        return None
    naming = data.get("naming") or {}
    structure = data.get("structure") or {}
    prof = {
        "casing": dict(naming.get("casing") or {}),
        "vague_denylist": list(naming.get("vague_denylist") or []),
        "structure_roots": dict(structure.get("roots") or {}),
        "consistency": list(data.get("consistency") or []),
    }
    if not any(prof.values()):
        return None
    return prof


def parse_conventions(text: str) -> dict | None:
    """Return a normalized profile dict or None if absent/empty/unparseable."""
    if not text or not text.strip():
        return None
    if _yaml is not None:
        try:
            return _normalize(_yaml.safe_load(text))
        except Exception:
            pass  # fall through to the minimal parser
    try:
        return _normalize(_minimal_parse(text))
    except Exception:
        return None


def match_role(file_rel: str, roots: dict) -> str | None:
    """Longest-prefix match of file_rel against the structure.roots keys."""
    best_key = None
    for key in roots:
        if file_rel.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return roots.get(best_key) if best_key is not None else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_conventions.py -v`
Expected: PASS (works whether or not PyYAML is installed — CI has it via pip, the fallback covers absence).

- [ ] **Step 5: Commit**

```bash
git add scripts/conventions.py tests/test_conventions.py
git commit -m "feat(conventions): conventions.yml parser + role matcher"
```

---

## Task 2: fold conventions into the manifest

**Files:**
- Modify: `scripts/build-context-map.py` (the `build()` function's `_meta`, and `BUILDER_VERSION`)
- Test: `tests/test_context_surfacing.py`

- [ ] **Step 1: Write the failing test**

Read `tests/test_context_surfacing.py` for its existing builder-test helpers (it already imports `build-context-map.py` and builds manifests from `tmp_path` git repos). Append:

```python
def test_builder_includes_meta_conventions_when_present(tmp_path):
    # uses the module's existing helper to init a git repo + build; if the
    # file lacks a reusable helper, init via subprocess like the other tests.
    repo = _make_git_repo(tmp_path)          # reuse existing helper name
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n"
        "  vague_denylist:\n    - data\n"
        "structure:\n  roots:\n    \"scripts/\": \"scripts root\"\n"
        "consistency:\n  - \"Hooks must fail-open.\"\n",
        encoding="utf-8",
    )
    manifest = _build_manifest(repo)         # reuse existing helper name
    conv = manifest["_meta"]["conventions"]
    assert conv["casing"]["functions"] == "snake_case"
    assert "data" in conv["vague_denylist"]
    assert conv["structure_roots"]["scripts/"] == "scripts root"
    assert conv["consistency"] == ["Hooks must fail-open."]


def test_builder_omits_conventions_when_absent(tmp_path):
    repo = _make_git_repo(tmp_path)
    manifest = _build_manifest(repo)
    assert "conventions" not in manifest["_meta"]
```

If the test file's helper names differ, adapt the two `_make_git_repo` / `_build_manifest` calls to whatever the file already uses to (a) create a git repo and (b) invoke `build()`; do not invent new infrastructure.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_context_surfacing.py -k conventions -v`
Expected: FAIL — `_meta` has no `conventions` key.

- [ ] **Step 3: Implement**

In `scripts/build-context-map.py`:
1. Bump `BUILDER_VERSION` to `"1.9.0"` (its comment says bump on schema/semantic changes; folding conventions is one). Add a one-line note that `--check` drift is expected until the manifest is regenerated + committed.
2. Import the new module: at top, after the stdlib imports, add
   `sys.path.insert(0, str(Path(__file__).resolve().parent))` then
   `from conventions import parse_conventions` (guard with try/except ImportError → `parse_conventions = lambda _t: None`).
3. In `build()`, before the `return {...}`, read the conventions file:
   ```python
   conv_path = repo_root / "conventions.yml"
   conventions = None
   if conv_path.is_file():
       try:
           conventions = parse_conventions(conv_path.read_text(encoding="utf-8", errors="replace"))
       except OSError:
           conventions = None
   ```
4. In the returned `_meta` dict, add the key **only when present** so absent-file manifests are byte-identical to today:
   build the `_meta` dict first as a variable, then `if conventions: meta["conventions"] = conventions`, and return `{"_meta": meta, "files": files_map}`.

Keep everything else unchanged. Conventions live once in `_meta`, never per file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_context_surfacing.py -k conventions -v`
Expected: PASS. Also run the whole file to confirm no regression: `python -m pytest tests/test_context_surfacing.py -v`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-context-map.py tests/test_context_surfacing.py
git commit -m "feat(context-map): fold conventions.yml into _meta.conventions"
```

---

## Task 3: surface conventions in the hook (source files, role at runtime)

**Files:**
- Modify: `scripts/hooks/context-surface.sh` (BOTH embedded Python heredocs — debug + production — keep them in sync, as the file already does)
- Test: `tests/test_context_surfacing.py`

Read the production heredoc (lines ~254-338) first. The change, in the Python:

1. After loading `manifest`, read conventions once:
   ```python
   conv = (manifest.get("_meta", {}) or {}).get("conventions")
   ```
2. The current early-exit `if not entry: sys.exit(0)` must NOT fire when conventions could still be surfaced. Restructure: get `entry = manifest.get("files", {}).get(file_rel)` (may be None). Build `parts` from anchors only if `entry`. Then, independently, if `conv` and the file is a source file, append the conventions block.
3. Source-file gate: `SRC_EXTS = {".py"}` (mirror of `score_adherence.LANG_PACKS`); compute `import os; ext = os.path.splitext(file_rel)[1].lower()`. Only append conventions if `ext in SRC_EXTS`.
4. Conventions block (compact), appended after anchors:
   ```python
   if conv and ext in SRC_EXTS:
       cparts = ["", "Conventions (this repo):"]
       casing = conv.get("casing") or {}
       if casing:
           cparts.append("  casing: " + " ".join(f"{k}={v}" for k, v in casing.items()))
       deny = conv.get("vague_denylist") or []
       if deny:
           cparts.append("  avoid vague names: " + ", ".join(deny[:8]))
       rules = conv.get("consistency") or []
       if rules:
           cparts.append("  house rules: " + "; ".join(rules[:4]))
       # directory role: longest-prefix match against structure_roots
       roots = conv.get("structure_roots") or {}
       best = None
       for k in roots:
           if file_rel.startswith(k) and (best is None or len(k) > len(best)):
               best = k
       if best is not None:
           cparts.append(f"  this dir: {roots[best]}")
       if len(cparts) > 2:
           parts.extend(cparts)
   ```
5. The existing `if len(parts) <= 1: sys.exit(0)` stays — it now correctly suppresses only when neither anchors nor conventions produced content.
6. Truncation: where the code truncates on `max_chars`, when the conventions block is what overflows, use a conventions-specific marker. Simplest robust approach that satisfies the test: if truncation happens AND `"Conventions (this repo):"` is in `out`, append `\n... (conventions truncated; cap={max_chars})` instead of the generic marker. Keep the generic marker otherwise.

Mirror the identical change into the debug heredoc above it.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_context_surfacing.py`; reuse the file's existing hook-invocation helper — it already runs the hook with crafted stdin and a manifest):

```python
def test_hook_surfaces_conventions_for_source_file(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n"
        "  vague_denylist:\n    - data\n"
        "structure:\n  roots:\n    \"scripts/\": \"scripts root\"\n"
        "consistency:\n  - \"Hooks must fail-open.\"\n", encoding="utf-8")
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    _build_manifest_on_disk(repo)            # reuse helper that writes the manifest file
    out = _run_ctx_hook(repo, repo / "scripts" / "thing.py")   # reuse hook-run helper
    assert "Conventions (this repo):" in out
    assert "functions=snake_case" in out
    assert "Hooks must fail-open." in out
    assert "this dir: scripts root" in out


def test_hook_no_conventions_for_markdown(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n", encoding="utf-8")
    (repo / "notes.md").write_text("# hi\n", encoding="utf-8")
    _build_manifest_on_disk(repo)
    out = _run_ctx_hook(repo, repo / "notes.md")
    assert "Conventions (this repo):" not in out


def test_hook_no_conventions_when_file_absent(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    _build_manifest_on_disk(repo)            # no conventions.yml
    out = _run_ctx_hook(repo, repo / "scripts" / "thing.py")
    assert "Conventions (this repo):" not in out
```

Adapt `_make_git_repo` / `_build_manifest_on_disk` / `_run_ctx_hook` to the file's actual helper names; the file already has equivalents for the anchor tests.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_context_surfacing.py -k "conventions or markdown or file_absent" -v`
Expected: FAIL — hook emits no conventions yet. These tests skip if `bash` is absent (existing module pattern).

- [ ] **Step 3: Implement** the hook change above (both heredocs).

- [ ] **Step 4: Run to verify pass + no regression**

Run: `python -m pytest tests/test_context_surfacing.py -v`
Expected: all PASS (or skip without bash). Then `shellcheck scripts/hooks/context-surface.sh` — expect no new warnings.

- [ ] **Step 5: Commit**

```bash
git add scripts/hooks/context-surface.sh tests/test_context_surfacing.py
git commit -m "feat(context-surface): surface conventions for source-file edits"
```

---

## Task 4: end-to-end integration test

**Files:**
- Test: `tests/test_context_surfacing.py`

- [ ] **Step 1: Write the test** (real pipeline: conventions.yml → builder writes manifest → hook reads it → output)

```python
def test_conventions_pipeline_end_to_end(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "conventions.yml").write_text(
        "naming:\n  casing:\n    functions: snake_case\n"
        "structure:\n  roots:\n    \"src/\": \"application code\"\n"
        "consistency:\n  - \"No bare except.\"\n", encoding="utf-8")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "app.py").write_text("y = 2\n", encoding="utf-8")
    _build_manifest_on_disk(repo)            # runs the real builder
    out = _run_ctx_hook(repo, repo / "src" / "app.py")   # runs the real hook
    assert "Conventions (this repo):" in out
    assert "this dir: application code" in out
    assert "No bare except." in out
```

- [ ] **Step 2: Run** — `python -m pytest tests/test_context_surfacing.py -k end_to_end -v` — expect PASS (Tasks 2-3 make it pass; this guards builder↔hook contract drift).

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_surfacing.py
git commit -m "test(context-surface): end-to-end conventions pipeline"
```

---

## Task 5: dogfood + template + catalogue

**Files:**
- Create: `conventions.yml` (repo root), `templates/conventions.yml.example`
- Modify: `.claude-leverage-context-map.json` (regenerated), `README.md`

- [ ] **Step 1: Author `templates/conventions.yml.example`** — the documented block-style schema with the `schema_version` "1.x additive" comment and a filled example (the schema block from the spec's Component 1, block-style, no inline `{}`/`[]`).

- [ ] **Step 2: Author `conventions.yml`** at repo root with this repo's real rules:

```yaml
schema_version: 1
naming:
  casing:
    functions: snake_case
    types: PascalCase
    constants: UPPER_SNAKE
  vague_denylist:
    - data
    - tmp
    - result
    - handle
    - process
structure:
  roots:
    "scripts/hooks/": "shell hooks shared by Claude Code + Codex; fail-open, exit 0 on missing parser/git; never edit the plugin-root-substituted paths"
    "skills/": "one SKILL.md per dir (agentskills.io spec)"
    "scripts/": "stdlib-only Python helpers + installers"
    "tests/": "pytest; hook tests skip cleanly without bash"
  file_loc_ceiling: 400
  func_loc_ceiling: 60
consistency:
  - "Hooks fail-open: exit 0 (never block) when jq/python/git is absent."
  - "AIDEV anchors: all-caps prefix, <=120 chars; don't remove without noting it in the commit."
  - "AGENTS.md stays lean (~8 KiB working ceiling; 32 KiB hard cap for Codex)."
```

- [ ] **Step 3: Regenerate the manifest**

Run: `python scripts/build-context-map.py`
Expected: writes `.claude-leverage-context-map.json` now containing `_meta.conventions`.

- [ ] **Step 4: Verify the hook surfaces it on a real file** (manual smoke — confirm the loop works on THIS repo)

Run: `printf '{"tool_name":"Edit","cwd":"%s","tool_input":{"file_path":"%s/scripts/hooks/context-surface.sh"}}' "$PWD" "$PWD" | bash scripts/hooks/context-surface.sh`
Expected: output JSON whose `additionalContext` contains `Conventions (this repo):` and `this dir: shell hooks shared by ...`.

- [ ] **Step 5: Add `conventions.yml` to the README "What's inside" catalogue** (one row in the directory table, same format as neighbours: root artifacts like `architecture.yml`/`GLOSSARY.md` if listed, else the most analogous spot).

- [ ] **Step 6: Commit**

```bash
git add conventions.yml templates/conventions.yml.example .claude-leverage-context-map.json README.md
git commit -m "feat(conventions): dogfood conventions.yml + template + regen manifest"
```

---

## Self-Review

**Spec coverage (Phase 2a):** conventions.yml schema + template → Task 5; parser → Task 1; `_meta.conventions` + BUILDER_VERSION bump → Task 2; hook source-gated surfacing + runtime role + truncation marker → Task 3; delivery + negative + integration tests → Tasks 3-4; dogfood-first validation → Task 5. **Deferred to 2b (not gaps):** `/conventions-init`, `ai-first-nudge` extension.

**Placeholder scan:** new code (parser) is complete; modifications give exact integration points + test contracts because the target files (`build-context-map.py`, `context-surface.sh`, `test_context_surfacing.py`) must be read and integrated into, not blank-slate written. Helper names (`_make_git_repo` etc.) are flagged as "reuse the file's actual helper" — the implementer reads the file.

**Type consistency:** `parse_conventions` returns `{casing, vague_denylist, structure_roots, consistency}`; the builder stores that dict verbatim at `_meta.conventions`; the hook reads exactly those keys. `match_role`/the hook's inline longest-prefix use the same `structure_roots` shape. Consistent across Tasks 1-3.

**Risk note for the implementer:** Task 3 edits TWO heredocs in `context-surface.sh` (debug + production) — they must stay identical or the debug path drifts. The file already maintains both; keep that discipline.
