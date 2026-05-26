---
name: arch-map
description: >
  USE WHEN setting up a repo for AI-first work, after a major directory
  restructure, or when an agent needs structured answers like "which
  modules are stable?" / "what's the public surface of X?" that the
  prose AGENTS.md doesn't give cheaply. Bootstraps or refreshes
  `architecture.yml` at repo root — machine-readable module metadata
  (path / role / stability / public_surface / depends_on / paired_with /
  owners). Hand-curated; the skill drafts, the user confirms. See ADR
  0005 for why this file lives at root and why YAML over JSON.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git rev-parse:*)
  - Bash(git ls-files:*)
  - Bash(test:*)
  - Bash(ls:*)
  - Bash(find:*)
  - Bash(python:*)
  - Bash(python3:*)
argument-hint: "[--depth N] [--validate] [--target path] [--noninteractive]"
---

# /arch-map

## What it does

Maintains `architecture.yml` at the repo root — a hand-curated,
machine-readable map of top-level modules. Complements
[`/repo-map`](../repo-map/SKILL.md), which generates a *human-readable*
mermaid diagram; this skill produces the *structured-metadata* layer an
agent can load and query in one parse.

The point: agents proposing refactors regularly ask "is this module
stable or experimental?" / "what's the public surface I shouldn't
silently rename?" / "what module does this pair with?". Re-deriving the
answer from prose AGENTS.md + directory tree walks is wasted tokens
every session. `architecture.yml` answers in one YAML load.

This skill **drafts the file** (from directory walk + AGENTS.md hints).
The user **confirms `role` and `stability`** per module. Auto-generated
guesses get a `<TODO>` placeholder until the user fills them.

See ADR 0005 for the rationale (why YAML over JSON, why root over
`docs/`, why not per-folder).

## When to invoke

- First setup of an AI-first repo (after `/init-repo` and ideally
  after `/repo-map`).
- After major directory restructuring (modules added, renamed,
  removed).
- When an agent is about to propose a refactor and you'd rather it
  read `architecture.yml` first than guess at module roles.

Do NOT invoke for:

- Per-file documentation (use AGENTS.md per directory, or docstrings
  in the code).
- Auto-generated dep graphs from imports (that's `/repo-map`'s
  `madge`/`pydeps` block).
- Tracking current commit / branch / version (this file is
  *architectural*, not point-in-time).

## File format

```yaml
# claude-leverage:architecture-map v1
# Hand-curated structured architecture metadata. Update via /arch-map
# or by hand-editing this file. Schema: claude-leverage v1.
# See: https://github.com/Filip-Podstavec/claude-leverage/blob/main/skills/arch-map/SKILL.md

repo:
  name: "<repo-name>"
  primary_lang: "<lang or lang+lang+lang>"
  one_line: "<one-sentence concrete description: what + for whom>"

modules:
  - path: "<dir-or-file>/"
    role: "<one-line purpose>"
    stability: stable | evolving | experimental | deprecated
    public_surface:
      - "<name agents must not silently rename>"
      - "<another>"
    depends_on:
      - "<other module path>"
    paired_with: "<module that mirrors this one>"
    owners:
      - "<name or @handle>"
```

### Required fields

- `repo.name`, `repo.primary_lang`, `repo.one_line`
- Each module: `path`, `role`, `stability`

### Optional fields

- `modules[].public_surface` — names/files agents must not casually
  rename (the rename will break callers outside the module). Strings.
- `modules[].depends_on` — array of other module `path` values this
  module depends on at the architectural level (not import-level).
- `modules[].paired_with` — single module path that mirrors this one,
  e.g. `agents/` paired with `.codex/agents/`.
- `modules[].owners` — array of names or @handles.

### Stability levels

| Value | Meaning |
|-------|---------|
| `stable` | Public surface is load-bearing; renames need an ADR + caller migration. |
| `evolving` | Public surface may change; callers should pin imports. |
| `experimental` | May be deleted entirely. Don't depend on this module from outside. |
| `deprecated` | Scheduled for removal. New code should not reference it. |

## Workflow

1. **Resolve repo root.** `git rev-parse --show-toplevel`. If not in a
   git repo, STOP and report.

2. **Detect mode.**
   - `--validate` → parse existing `architecture.yml`, check required
     fields, check `path` values exist, report findings, write
     nothing.
   - No existing file → **bootstrap mode**.
   - Existing file + no `--validate` → **extend / refresh mode**:
     re-walk directories, suggest entries for new modules; preserve
     existing module entries unchanged.

3. **Walk top-level directories** (depth 1 by default; pass
   `--depth N` for 1–3). Skip:
   - Dotfiles except `.codex` / `.claude*` (those are tooling).
   - Standard noise: `node_modules`, `__pycache__`, `dist`, `build`,
     `.next`, `.pytest_cache`, `target`, `vendor`, `bench/archive-*`.
   - Empty directories.

4. **For each non-trivial directory, infer:**
   - `path` — the directory path relative to repo root, with trailing
     slash.
   - `role` (draft) — read the directory's `AGENTS.md` if present;
     extract the first H1 heading + first paragraph. If no AGENTS.md,
     emit `"<TODO: one-line purpose>"`.
   - `stability` (draft) — emit `<TODO: stable|evolving|experimental|deprecated>`.
     The skill won't guess this; the user knows.
   - `public_surface` (draft) — best-effort: list top-level filenames
     without leading `_`, plus any obvious exports (Python `__all__`,
     TS named exports, Go exported identifiers). Cap at 10 entries.
     If unclear, omit the field.
   - `depends_on` (draft) — omit; the user fills if architecturally
     meaningful.
   - `paired_with` (draft) — heuristic: if there's a `.codex/<name>/`
     mirror of `<name>/`, propose that pairing.
   - `owners` (draft) — omit by default. The user can fill or skip.

5. **Read existing `architecture.yml`** if present. Parse YAML
   (stdlib-only via `python -c 'import yaml'` if available, else a
   conservative line-based parser — see "Parser fallback" below).
   Compute set of `modules[].path` values already documented.
   New module entries proposed only for paths not in that set.

6. **Show the user the draft (interactive mode):**

   ```
   I'll write architecture.yml at <repo-root>/. Confirm or edit:

   repo:
     name: "claude-leverage"
     primary_lang: "shell+python+markdown"
     one_line: "<TODO: one-sentence concrete description: what + for whom>"

   modules (proposed):
     - path: "scripts/hooks/"
       role: "<TODO: one-line purpose>"       <-- AGENTS.md present at this path? no
       stability: <TODO>
     - path: "skills/"
       role: "Cross-tool on-demand skills (agentskills.io spec)"  <-- from skills/README.md
       stability: <TODO>
     - path: "agents/"
       role: "Claude Code subagents"          <-- from agents/README.md
       stability: <TODO>
       paired_with: ".codex/agents/"
   ...

   Proceed? (y / n / edit-each)
   ```

   With `edit-each`, walk modules and prompt for `role` + `stability`
   per module. With `y`, write as-shown (`<TODO>` placeholders intact).
   In `--noninteractive`, write as-shown without prompting.

7. **Write the YAML.** Use a deterministic key order (the order in the
   schema above). Quote strings that contain `:` or start with `-`.
   Use 2-space indentation. End with a single newline.

8. **Validate the written file.** Run the YAML parser on it; check:
   - Top marker comment is exactly
     `# claude-leverage:architecture-map v1`.
   - `repo.name`, `repo.primary_lang`, `repo.one_line` are present
     and non-empty (a `<TODO>` placeholder counts as "present").
   - `modules` is a non-empty list.
   - Each module has `path`, `role`, `stability`.
   - Each `path` value exists on disk (warn if not — could be an
     intentional placeholder for a planned module).
   - `stability` is one of the four valid values OR a `<TODO>`
     placeholder.
   If validation fails, print the error with line number and stop
   before writing the final version.

9. **Update AGENTS.md** (idempotent, ask before write). If `AGENTS.md`
   exists and doesn't already mention `architecture.yml`, offer to
   append:

   ```markdown
   ### Architecture metadata

   Machine-readable module map: [`architecture.yml`](architecture.yml).
   When proposing refactors that cross module boundaries, **read this
   first** for `stability` and `public_surface` constraints.
   ```

   Skip if `--no-update-agents-md` is passed.

10. **Report.** Print path, count of modules total, count of `<TODO>`
    placeholders remaining, suggested next step (`/arch-map --validate`
    after filling).

## Validate mode (`--validate`)

Read `architecture.yml`, run the same checks as step 8, exit. Useful in
CI: a future job can run `claude /skill arch-map --validate` to fail
the build if the file drifts. Output is a structured report:

```markdown
# architecture.yml validation — <YYYY-MM-DD>

Schema version: v1 ✓
Required fields: ✓

| Module | Status | Notes |
|--------|--------|-------|
| scripts/hooks/ | ok | — |
| skills/ | ok | — |
| agents/ | **TODO** | role + stability still placeholders |
| legacy/ | **missing** | path declared but not on disk |
```

## Parser fallback

If neither `python` nor `python3` is on PATH, or PyYAML isn't
installed, fall back to a conservative regex line parser inside the
skill body:

- Recognize top-level keys, two-space-indented children.
- Recognize lists via `- ` prefix.
- Reject multi-line scalars, anchors, aliases, merge keys, flow style.
  The schema is intentionally flat enough that this is fine.

If even that fails (file structure is too foreign), print the parse
error and STOP. Don't try to "fix" the file — that's the user's job.

## Hard rules

- **Never overwrite existing module entries.** Re-running in extend
  mode preserves them byte-for-byte. If the user wants to revise a
  module, they edit the file by hand.
- **Never invent `role` or `stability`.** Both are user-supplied or
  `<TODO>` placeholders. The skill drafts, the user confirms.
- **Never auto-generate `depends_on` from imports.** Import-level deps
  belong in `/repo-map`'s `madge`/`pydeps` block. `depends_on` here is
  *architectural* (user-decided), not derived.
- **Preserve the schema marker line.** The top
  `# claude-leverage:architecture-map v1` comment is load-bearing.
- **Stop on parse error.** A corrupted `architecture.yml` is the
  user's call to fix; the skill never rewrites a file it can't parse.

## Tunables

- `--depth N` — directory walk depth (1–3, default 1).
- `--validate` — schema-only mode; write nothing, exit non-zero on
  failure.
- `--target <path>` — non-default file location (default
  `<repo-root>/architecture.yml`).
- `--no-update-agents-md` — skip the AGENTS.md pointer step.
- `--noninteractive` — write the draft as-shown without per-module
  prompts.

## What this skill does NOT do

- **Auto-generate a dependency graph from code.** That's
  `/repo-map`'s madge/pydeps block. This skill captures the
  *architectural* dependency the user names, not the import graph.
- **Replace AGENTS.md per directory.** Per-directory AGENTS.md
  remains the primary prose layer for module-internal conventions and
  gotchas. `architecture.yml` is structured metadata about the
  module's *role* in the system, not its internal workings.
- **Track current commit / branch.** This file is architectural and
  changes when the architecture changes — not on every code commit.
- **Validate `depends_on` is acyclic.** Cycle detection is future
  work for `/stack-check` integration.
- **Auto-fire on directory changes.** Per ADR 0004's philosophy:
  user/agent-invoked, no auto-fire hook. The agent recognizes the
  moment.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. Codex
host writes the same YAML; the format is tool-agnostic.

## Future / not in scope here

- `/stack-check` could validate `architecture.yml` schema as part of
  its repo-walk, flag `<TODO>` placeholders > 30 days old, and warn
  on `depends_on` cycles. Tracked as a future enhancement.
- `/repo-map` could read `architecture.yml` to color-code mermaid
  nodes by `stability`. Future enhancement.
- A JSON-schema sidecar (`architecture.schema.json`) for IDE
  validation in editors that support it. Out of scope for v1.
