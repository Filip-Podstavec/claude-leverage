# Conventions adherence: steer-first, measured

> **Status:** Design (approved in brainstorm 2026-06-02). Next step:
> implementation plan via writing-plans.

**Goal:** Make the stack actively steer AI agents toward code that *conforms to
this repo's own evolving norm* — clear intent-revealing names, consistent
patterns, reasonable structure — and **measure** that the steering works,
instead of relying on advisory nudges the agent can ignore and whose effect is
unproven.

## Motivation

The stack's property #2 ("self-maintaining as the repo grows") currently leans
entirely on advisory `stderr` nudges (`ai-first-nudge`) and prose conventions in
`AGENTS.md`. Two problems:

1. **Unmeasured.** We disproved the v0.x token-savings thesis *with data*. The
   current value proposition — that anchors/nudges/conventions improve
   maintainability — has no equivalent evidence. We risk repeating the
   build-blind-then-discover mistake.
2. **One root, four symptoms.** The user's pain — vague names, cross-repo
   inconsistency, ad-hoc structure, doc/context drift — is a single root cause:
   *the agent has no cheap, current, enforced picture of "how this repo does
   things," and nothing checks its output against it.* These are **semantic**
   judgments (unlike secret detection, which is a regex), so a shell hook cannot
   grade "is this name clear." The intelligence must live in a deterministic
   proxy (cheap, repeatable) plus, occasionally, a model (ground truth).

## Decisions locked in brainstorm

- **Friction ceiling: steer-first.** Invest in pre-write guidance so the agent
  writes it right the first time; keep post-write feedback advisory. Introduce a
  blocking gate *only* if the eval proves it helps. This avoids two failure
  modes of aggressive blocking on semantic judgments: false-blocks and
  "slop-ticking" (agent emits a junk rename/anchor just to silence the hook).
- **Success signal: combo.** A cheap **deterministic adherence score** for fast
  iteration, plus occasional **ground truth** (LLM-judge rubric and/or
  next-agent task success) to confirm the proxy isn't being gamed.
- **`consistency` is hand-curated**, not auto-detected (lib/pattern-per-concern
  can't be reliably inferred; auto-detection would add noise).
- **Sequencing A+C: measurement first.** Build the scorer + eval harness before
  the new steering mechanism, baseline it, then add steering and measure the
  *delta*.

## Non-goals

- No blocking commit gate in this iteration (revisit only if eval justifies it).
- No model call on the steering/scoring critical path (keeps it cheap,
  deterministic, and consistent with [ADR 0003](../adr/0003-no-embedding-rag-hybrid-manifest-and-grep.md)).
- **No client code, name, or task description in the repo.** The maintainability
  eval runs on a synthetic fixture authored and committed here. The private
  client repo that motivates this work is never referenced by name, code, or
  identifying description anywhere in version control.

## Architecture

```
conventions.yml  ──surfaces──>  context-surface hook  ──>  agent writes right first time
  (source of truth)               (PreToolUse)                      │
      │                                                             ▼
      └──read──>  score-adherence.py  <──scores diff──  ai-first-nudge (PostToolUse, advisory)
                   (deterministic)                                  │
                       │                                            ▼
                       ├──> repo-doctor dimension (audit)     eval harness (synthetic A/B)
                       └──> eval signal (baseline + delta)
```

One artifact (`conventions.yml`) is the source of truth; three consumers read
it (steering hook, scorer, audit). No model on the critical path → reproducible.

## Component 1 — `scripts/score-adherence.py` (built first)

Deterministic, no network, no model. Same input → same output (this is what
makes it a trustworthy eval signal).

**Modes:**
- `--repo <path>` — whole-tree baseline score.
- `--diff <range>` — score only the identifiers/lines changed in a git range
  (powers per-change nudges and the eval delta).

**Output:** JSON — each sub-metric as a 0–1 score plus raw counts, and an
overall. Stable key order.

**Sub-metrics:**
1. **naming_clarity** — over identifiers extracted from declarations (regex per
   language; not a full parse), the fraction that are *not* on the vague-name
   denylist (`data`, `tmp`, `handle`, `process`, `util`, `manager`, `doStuff`,
   …) and within length bounds.
2. **casing_consistency** — per identifier kind (functions / variables / types /
   constants / files), infer the dominant style and report the fraction
   deviating.
3. **structure** — file-LOC and function-LOC ceiling violations, files outside
   recognized directory roles, god-file flags.
4. **context_freshness** — overdue `AIDEV-` anchors, `architecture.yml`↔disk
   drift, glossary coverage. Reuses `repo-doctor` Sync-dimension logic (extract
   shared helpers rather than duplicate).

**Language packs:** identifier extraction is per-language, pluggable by file
extension → a regex/heuristic table. **The scorer core is language-agnostic; a
Python reference pack ships first** (the motivating repos are Python and it's
the most common). TypeScript/Go/etc. are added as packs without touching the
core.

**Error handling:** missing `conventions.yml` → run on language-agnostic
metrics only (casing/structure) and use the built-in denylist for naming; never
crash, just degrade. Unknown language (no pack) → skip naming/casing for those
files, still score structure/freshness, and note coverage in the output.

**Testing:** golden mini-repos (a "clean" tree and a deliberately "dirty" tree)
with asserts on the resulting scores; same behavioral style as the hook tests in
`tests/test_hook_behavior.py`.

## Component 2 — Profile + steering (built after the scorer)

**`conventions.yml`** at repo root (sibling of `architecture.yml`), bootstrapped
by a new `/conventions-init` skill (the skill drafts from a scan, the user
confirms — same pattern as `glossary-init` / `arch-map`; idempotent via
markers).

```yaml
naming:
  casing: {functions: snake_case, types: PascalCase, constants: UPPER_SNAKE}
  vague_denylist: [data, tmp, handle, process, util, manager]  # repo-extensible
  min_len: 3
structure:
  roots: {services/: "domain logic", api/: "http surface"}
  file_loc_ceiling: 400
  func_loc_ceiling: 60
consistency:                       # hand-curated — not auto-detected
  http_client: httpx
  logging: structlog
```

The scanner proposes `naming.casing`, `structure`, and a starting denylist from
repo statistics; the `consistency` block is filled in by the user.

**Steering (the steer-first core):** extend the existing `context-surface`
PreToolUse hook. It already surfaces `AIDEV-` anchors for the file about to be
edited; add the relevant slice of `conventions.yml` — the casing rule, the
directory role for that path, and the top denylist entries. Cheap, no model,
graceful no-op when no profile exists.

**Advisory (unchanged ceiling):** extend `ai-first-nudge` PostToolUse to run the
scorer in `--diff` mode on the change; on a naming/casing regression, emit a
non-blocking, frequency-capped nudge ("introduced `data`, `tmp` — this repo
favors intent-revealing names"). Never blocks.

## Component 3 — Eval harness (synthetic A/B)

Reuses the `bench/` pattern. New `bench/conventions-eval/`, fully self-contained
and committed — **no client dependency**.

- **Fixture:** a synthetic ~small Python service authored in two trees — `dirty/`
  (vague names, mixed casing, god-file, no profile) and `clean/` (intent names,
  consistent, profile present). Both committed; no external/client code.
- **Arms:** identical task prompt, fresh `claude` invocations — one with the
  profile surfaced + nudges on, one without.
- **Cheap signal:** `score-adherence --diff` on each arm's produced change →
  **adherence delta**.
- **Ground truth (run less often):** an LLM-judge rubric (clarity / consistency
  / structure) on blind A/B outputs, and optionally a next-agent task-success
  measure. Confirms the cheap proxy isn't being gamed.
- **Output:** a report in the style of the archived `per-agent-report.md` —
  adherence delta + judge scores, with honest `n` and noise caveats.

## Measurement plan (sequencing C)

1. Ship Component 1; add it as a `repo-doctor` dimension (immediately useful).
2. Build Component 3's fixture + harness; **baseline** the dirty/clean trees and
   confirm the scorer separates them as expected (sanity check on the proxy).
3. Ship Component 2 (profile + steering + nudge).
4. Run the A/B; report adherence delta + a ground-truth pass.
5. Only if the delta is real *and* survives the ground-truth check do we
   consider raising the friction ceiling (e.g. a commit gate).

## Cross-tool notes

All components are cross-tool by construction: `conventions.yml` (YAML, like
`architecture.yml`), scorer (Python, already a stack dependency), steering via
the existing shell `context-surface` hook + `AGENTS.md`. Codex and Claude Code
see the same artifacts.

## Risks & open questions

- **Profile drift.** `conventions.yml` can go stale like any artifact; it rides
  the existing refresh discipline (`/stack-check`, `repo-doctor` Sync, the
  context-map manifest refresh) and should be a `repo-doctor` drift check.
- **Slop-ticking.** Even advisory nudges can train the agent to game the metric.
  The ground-truth pass exists specifically to catch a rising cheap-score with
  flat/declining judged quality.
- **Cross-language coverage.** Only the Python pack ships first; the scorer must
  `log` (not silently skip) files in unsupported languages so coverage gaps are
  visible.
- **Judge noise / small n.** The ground-truth signal is noisy; report it with
  caveats and never headline a delta the n can't support (per the eval-baseline
  discipline already in use).

## Affected / new files

- New: `scripts/score-adherence.py`, `scripts/lang/python.py` (pack),
  `skills/conventions-init/SKILL.md`, `conventions.yml` (in consuming repos, via
  the skill — not committed to this repo except as a template/example),
  `templates/conventions.yml.example`, `bench/conventions-eval/` (fixture +
  harness + README), `tests/test_score_adherence.py`.
- Modified: `scripts/hooks/context-surface.sh` (surface profile slice),
  `scripts/hooks/ai-first-nudge.sh` (scorer-driven naming/casing nudge),
  `skills/repo-doctor/SKILL.md` (new adherence dimension), `README.md` +
  per-dir docs (catalogue the new skill/script), version + marketplace sync.
