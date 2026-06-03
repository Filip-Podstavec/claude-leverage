# Phase 2 — Conventions steering

> **Status:** Design v2 (approved 2026-06-03, revised after subagent design
> review). Next: plan, then implementation via subagent-driven loop.

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
*one* falsifiable thing a unit test can assert: when an agent edits a **source**
file in a repo that has a `conventions.yml`, the plugin surfaces the relevant
conventions into the agent's context.

## Non-goals

- No blocking gate (steer-first; nudges stay advisory).
- No model on the critical path (consistent with ADR 0003 / 0008).
- No adherence-delta success metric (rejected — see above).
- No auto-merge of an existing hand-edited `conventions.yml` (comment loss risk).

## Architecture

```
conventions.yml (root)  ──read──>  build-context-map.py  ──>  manifest (+ conventions)
   (drafted by /conventions-init)                                    │
                                                       context-surface hook ──> agent (pre-edit)
                                                                     +
                       ai-first-nudge ──score edit blob──> advisory on casing/vague drift
```

`conventions.yml` is the source of truth; `build-context-map.py` folds it into the
pre-built manifest (no per-edit runtime cost, per ADR 0008); the hook emits the
slice for source files; the nudge is an independent advisory backstop.

## Phasing (per design review N1)

Build in two stages, same end state:

- **Phase 2a — delivery loop (low risk, build first):** `conventions.yml` schema +
  `templates/conventions.yml.example` + `build-context-map.py` extension +
  `context-surface` hook extension + delivery/integration tests + dogfood this
  repo. This alone satisfies the narrowed verification goal.
- **Phase 2b — after 2a is green:** `ai-first-nudge` extension (needs the
  blob-scoring mechanism below) + `/conventions-init` skill.

## Component 1 — `conventions.yml` (repo root)

```yaml
# claude-leverage conventions profile. Drafted by /conventions-init, hand-confirmed.
# schema_version 1 is "1.x": additive optional fields may appear; consumers ignore
# unknown keys. Unknown TOP-LEVEL keys are logged as a warning by the builder.
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

A `templates/conventions.yml.example` ships with the documented schema and the
`schema_version` semantics comment. Missing file → every downstream consumer
no-ops.

## Component 2 — `/conventions-init` skill (Phase 2b)

Scans the repo and **drafts** `conventions.yml`, then the user confirms (same
pattern as `glossary-init` / `arch-map`). Inference:
- `naming.casing`: dominant style per identifier kind from a sample of source
  files, using `score_adherence.classify_casing`. **Python-first**: if the repo is
  predominantly non-Python (no `.py` files, or a language with no lang-pack), leave
  `casing` values blank with a comment for the user to fill — never guess from an
  unsupported language.
- `structure.roots`: top-level + recognized source dirs, with blank role strings
  for the user to fill.
- `vague_denylist`: seed from `score_adherence.DEFAULT_VAGUE`.
- `consistency`: a commented template — house rules cannot be auto-detected and
  must be written by a human.

**Idempotency / no comment loss:** if `conventions.yml` is **absent**, write it.
If it **exists**, do NOT parse-and-rewrite it (stdlib YAML loses the human-written
`consistency` comments). Instead print the suggested draft (or only the
top-level sections that are missing) to stdout for the user to merge by hand. No
`ruamel.yaml` dependency. Read-only on code.

## Component 3 — `build-context-map.py` extension (Phase 2a)

If `conventions.yml` exists at repo root, parse it (reuse the existing YAML-or-regex
fallback parser already used for `architecture.yml`) and attach to the manifest:
- `_meta.conventions`: the global block — `casing`, a short `vague_denylist`
  preview, and the `consistency` rules (stored once, not per file).
- per file entry: `conventions_role` = the role string of the longest-prefix match
  in `structure.roots` for that file's path, or omitted if none.

Additive only; manifest `schema_version` stays `1`. **Bump `BUILDER_VERSION`** (it
gates `--check`): adding conventions changes manifest content, so `--check` will
report drift until the manifest is regenerated and committed — expected during the
rollout window; bumping the version makes the cause legible. Unknown top-level keys
in `conventions.yml` → log a warning (not error). Absent/unparseable
`conventions.yml` → manifest built exactly as today.

## Component 4 — `context-surface` hook extension (Phase 2a)

After the anchor sections, when the manifest carries conventions **and the edited
file is a source file** (extension in `score_adherence.LANG_PACKS`, mirrored as a
small list in the hook), append a compact block (always for source files — not
behind `VERBOSE`; conventions are short and load-bearing). For non-source files
(Markdown, YAML, JSON, images, configs) skip the block entirely — surfacing naming
conventions on a doc edit is exactly the wasted tax ADR 0008 warns against.

```
Conventions (this repo):
  casing: functions=snake_case types=PascalCase constants=UPPER_SNAKE
  avoid vague names: data, result, tmp, ...
  house rules: Hooks must fail-open …; AIDEV anchors all-caps <=120 …
  this dir: shell hooks shared by both tools; fail-open …   (if conventions_role present)
```

Anchors take precedence under the existing `MAX_CHARS` cap; conventions are
appended and, if the budget is tight, truncated with a **specific** marker
`... (conventions truncated; cap=N)` so the agent can tell conventions were cut
(distinct from anchor truncation). All existing graceful no-op paths unchanged.

## Component 5 — `ai-first-nudge` extension (Phase 2b)

After a `Write|Edit|MultiEdit`, **only if `conventions.yml` exists and the file is
Python** (the only lang-pack today), check the **edit blob itself** — not the file
via `--diff`, which scores the whole current file and would false-fire on
pre-existing names. The hook already isolates the added content (`new_string` for
`Edit`, `content` for `Write`, the `edits[*].new_string` for `MultiEdit`) for its
LOC count; reuse that blob. Run the importable `score_adherence` functions on the
blob directly: `extract_python_identifiers(blob)` then, per identifier, flag if it
is `_is_unclear(...)` against the repo's `vague_denylist`, or its `classify_casing`
for its kind ≠ the `conventions.yml` casing. If the **edit introduces** ≥1 such
identifier, print a non-blocking advisory naming them. Frequency-capped per file
per day (existing cap machinery). Honest scope: catches casing / vague-name drift
the edit *adds* — the legacy-repo mimicry case — not semantic house-rule
violations, and only for Python.

## Error handling

Every consumer degrades silently: no `conventions.yml` → hook/nudge behave as
today; unparseable YAML → skip conventions, keep anchors; no Python/parser →
existing no-op paths; non-source / non-Python file → conventions block / nudge
skipped. No new failure can block a tool call.

## Testing

- **Primary (the narrowed goal) — delivery, with negative paths:**
  - Positive: build a manifest from a fixture repo with a `conventions.yml`, run
    `context-surface` for an edit to a source file under a known role; assert the
    emitted `additionalContext` contains the casing line, a house rule, and the
    directory role.
  - Negative: no `conventions.yml` → no conventions block (anchors still emit);
    edit to a non-source file (`.md`) → no conventions block; unparseable
    `conventions.yml` → hook still emits anchors, does not crash; budget exhausted
    by anchors → specific `(conventions truncated; cap=N)` marker appears.
- **Integration (end-to-end):** one test that runs the real pipeline —
  `conventions.yml` → `build-context-map.py` → manifest → `context-surface` hook —
  on a fixture and greps the output for the conventions. Catches contract drift
  between builder and hook that isolated unit tests miss.
- **`build-context-map.py`:** unit test that `_meta.conventions` and per-file
  `conventions_role` are computed (longest-prefix role match; file under no root →
  no role).
- **`ai-first-nudge` (2b):** behavioral test that an edit blob introducing a vague
  name / wrong casing nudges, and a clean blob does not, and a pre-existing vague
  name NOT in the edit blob does not nudge (the C1 regression guard).
- **`/conventions-init` (2b):** absent-file creates; existing-file emits suggestions
  to stdout and does not rewrite the file (comment-preservation guard).
- All hook tests skip cleanly without bash (existing pattern) and run on the
  Windows CI job added earlier.

## Dogfood (validate FIRST, per review N3)

Hand-author `conventions.yml` for this repo early (real house rules: hooks
fail-open; AIDEV anchor rules; AGENTS.md lean ~8 KiB budget; `scripts/hooks/`
never edits the plugin-root-substituted absolute paths), regenerate + commit the
context-map manifest, and confirm the hook surfaces them on a real source edit
before trusting the fixture tests. If the pipeline doesn't work on this repo's real
rules, the fixture tests are testing an unrepresentative case.

## Maintenance artifacts to update

README "What's inside" + skills count, `docs/maintaining.md` for the new skill /
template, `/repo-doctor` (optional new "conventions.yml present/stale" check),
plugin/marketplace version bump, Codex agent parity if applicable.
