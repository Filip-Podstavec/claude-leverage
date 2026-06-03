# Phase 2 — Conventions steering

> **Status:** Design (approved 2026-06-03). Next: subagent feedback, then plan,
> then implementation via subagent-driven loop.

**Goal:** Surface a repo's own conventions to the agent *before it writes*, so the
plugin actively feeds its recommendations into the working context instead of
hoping the agent reads `AGENTS.md`. Verified by one thing: **does the plugin
actually deliver the conventions into context during real work?** — a
deterministic delivery check, not an adherence A/B.

## Motivation & scope of verification

The plugin's value (navigation, anti-bloat in legacy repos, applying
repo-specific conventions) is real but is **not** measured by a synthetic
single-file adherence score — that is the full-repo `bench/eval` A/B's job, and a
capable model writes clean generic code regardless. So Phase 2 does **not** try to
prove "steering raises a score." It builds the steering mechanism and verifies the
*one* falsifiable thing a unit test can assert: when an agent edits a file in a
repo that has a `conventions.yml`, the plugin surfaces the relevant conventions
into the agent's context.

## Non-goals

- No blocking gate (steer-first; nudges stay advisory).
- No model on the critical path (consistent with ADR 0003 / 0008).
- No adherence-delta success metric (rejected — see above).
- No `conventions.yml` schema bump of the context-map manifest: additions are
  optional fields, so old hooks ignore them and keep working.

## Architecture

```
conventions.yml (root)  ──read──>  build-context-map.py  ──>  manifest (+ conventions)
   (drafted by /conventions-init)                                    │
                                                       context-surface hook ──> agent (pre-edit)
                                                                     +
                       ai-first-nudge ──score_adherence --diff──> advisory on casing/vague drift
```

`conventions.yml` is the source of truth; `build-context-map.py` folds it into the
pre-built manifest (no per-edit runtime cost, per ADR 0008); the hook emits the
slice; the nudge is an independent advisory backstop.

## Component 1 — `conventions.yml` (repo root)

```yaml
# claude-leverage conventions profile. Drafted by /conventions-init, hand-confirmed.
schema_version: 1
naming:
  casing: {functions: snake_case, types: PascalCase, constants: UPPER_SNAKE, files: snake_case}
  vague_denylist: [data, result, tmp, handle, process]   # extends the built-in default
structure:
  roots:
    "scripts/hooks/": "shell hooks shared by both tools; fail-open, never block on infra absence"
    "skills/": "one SKILL.md per dir (agentskills.io spec)"
  file_loc_ceiling: 400
  func_loc_ceiling: 60
consistency:                       # divergent house rules the model cannot infer
  - "Hooks must fail-open and exit 0 when a JSON parser / git is absent."
  - "AIDEV anchors: all-caps prefix, <=120 chars; don't remove without noting it in the commit."
```

A `templates/conventions.yml.example` ships with the documented schema. Missing
file → every downstream consumer no-ops.

## Component 2 — `/conventions-init` skill

Scans the repo and **drafts** `conventions.yml`, then the user confirms (same
pattern as `glossary-init` / `arch-map`). Inference:
- `naming.casing`: dominant style per identifier kind from a sample of source
  files (reuse `score_adherence.classify_casing`).
- `structure.roots`: top-level + recognized source dirs, with blank role strings
  for the user to fill.
- `vague_denylist`: seed from `score_adherence.DEFAULT_VAGUE`.
- `consistency`: left as a commented template — house rules cannot be auto-detected
  and must be written by a human.
Read-only on code; idempotent (re-run augments, never overwrites a populated file
without the user's confirmation). Writes `conventions.yml` at repo root.

## Component 3 — `build-context-map.py` extension

If `conventions.yml` exists at repo root, parse it (reuse the existing YAML-or-regex
fallback parser already used for `architecture.yml`) and attach to the manifest:
- `_meta.conventions`: the global block — `casing`, a short `vague_denylist`
  preview, and the `consistency` rules (stored once, not per file).
- per file entry: `conventions_role` = the role string of the longest-prefix match
  in `structure.roots` for that file's path, or omitted if none.

Additive only; `schema_version` stays `1`. If `conventions.yml` is absent or
unparseable, the manifest is built exactly as today.

## Component 4 — `context-surface` hook extension

After the anchor sections, when the manifest carries conventions, append a compact
block (always, not behind `VERBOSE` — conventions are short and load-bearing,
unlike the "see X" refs ADR 0008 found wasteful):

```
Conventions (this repo):
  casing: functions=snake_case types=PascalCase constants=UPPER_SNAKE
  avoid vague names: data, result, tmp, ...
  house rules: Hooks must fail-open …; AIDEV anchors all-caps <=120 …
  this dir: shell hooks shared by both tools; fail-open …   (if conventions_role present)
```

Subject to the existing `MAX_CHARS` cap (anchors take precedence; conventions are
appended and truncated if the budget is tight). All existing graceful no-op paths
unchanged. The new hook reads the optional fields if present; absence → behaves as
today.

## Component 5 — `ai-first-nudge` extension

After a `Write|Edit|MultiEdit`, **only if `conventions.yml` exists**, run
`python scripts/score_adherence.py --diff` scoped to the changed file and, if the
change introduces a casing deviation or a denylisted vague name, print a
non-blocking advisory (frequency-capped per file per day, reusing the existing cap
machinery). Honest scope: catches casing / vague-name drift — the legacy-repo
mimicry case — not semantic house-rule violations. Never blocks; cheap (gated on
the file existing, scores one file).

## Error handling

Every consumer degrades silently: no `conventions.yml` → hook/nudge behave as
today; unparseable YAML → skip conventions, keep anchors; no Python/parser →
existing no-op paths. No new failure can block a tool call.

## Testing

- **Primary (the narrowed goal):** a delivery test — build a manifest from a
  fixture repo with a `conventions.yml`, run the `context-surface` hook for an edit
  to a file under a known role, assert the emitted `additionalContext` contains the
  casing line, a house rule, and the directory role. (Mirrors `tests/test_context_surfacing.py`.)
- `build-context-map.py`: unit test that `_meta.conventions` and per-file
  `conventions_role` are computed (longest-prefix role match; absent file → no role).
- `/conventions-init`: idempotency + draft-shape test.
- `ai-first-nudge`: behavioral test that a casing/vague regression nudges and a
  clean change does not (extends `tests/test_hook_behavior.py`).
- All hook tests skip cleanly without bash (existing pattern) and run on the
  Windows CI job added earlier.

## Dogfood

Hand-author `conventions.yml` for this repo (real house rules: hooks fail-open;
AIDEV anchor rules; AGENTS.md lean ~8 KiB budget; `scripts/hooks/` never edits the
plugin-root-substituted absolute paths). Confirms the loop end-to-end on a real
repo.

## Maintenance artifacts to update

README "What's inside" + skills count, `docs/maintaining.md` if a new skill/
template is added, `/repo-doctor` (optional new "conventions.yml present" check),
plugin/marketplace version bump, Codex agent parity if applicable.
