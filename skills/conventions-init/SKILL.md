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
the house rules — it never invents a convention the repo does not actually hold.

## When to invoke

- Setting up an AI-first repo, after `/init-repo`.
- When you want the plugin to start steering on this repo (no `conventions.yml`
  yet means the whole steering loop is a no-op).

Do NOT invoke for: per-function docs (those are docstrings), or to auto-write
house rules the team has not agreed on.

## Workflow

1. **Resolve repo root** (`git rev-parse --show-toplevel`); if not a repo, STOP
   and suggest `git init` / `/init-repo`.
2. **Detect mode.** If `conventions.yml` is absent, bootstrap. If it exists, do
   NOT rewrite it (stdlib YAML loses the human-written `consistency` comments);
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
   to write (same "never invent" rule as `glossary-init`).
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
- **Block-style YAML only** (no inline braces or brackets) — keeps the stdlib
  fallback parser reliable.
- **Python-first casing.** Do not infer casing from unsupported languages; leave
  it blank for the user.

## Tunables

- `--noninteractive` — write the inferred skeleton with blank roles and a
  commented `consistency` block, no prompts.

## What this skill does NOT do

- Auto-write house rules or invent conventions the repo does not hold.
- Rebuild the context-map manifest — that is `/refresh-context-map`.
- Score or lint code — that is `score_adherence.py` / `/repo-doctor`.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. No tool-specific
divergence.
