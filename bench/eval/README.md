# A/B evaluation harness

How the numbers in the top-level [README](../../README.md#benchmark-results-does-claude-leverage-actually-pay-off)
benchmark section were produced.

## Setup

Two trees of an anonymised real client codebase (~30k LOC Python web service):

- **`before/`** — historical commit from before claude-leverage adoption.
  No `AGENTS.md`, no AIDEV anchors, no per-directory docs, monolithic API
  surface. Remote removed so the agent cannot see future commits.
- **`after/`** — current HEAD with the full claude-leverage in-repo
  artifact set: root `AGENTS.md`, per-directory `AGENTS.md`, AIDEV
  anchors throughout the source, ADRs under `docs/adr/`, `GLOSSARY.md`,
  `architecture.yml`, per-domain router split, structured-logging spec,
  `.claude-leverage-context-map.json` manifest (powering the
  `context-surface` PreToolUse hook).

Task: implement a new paginated HTTP endpoint following the conventions
documented in each tree.

## Configurations

- **Pure A/B**: plugin OFF in `before/`, ON in `after/`. Measures the
  total effect of claude-leverage (plugin features + in-repo artifacts).
- **Artifact-only**: plugin ON in both. Isolates the value of the
  in-repo enrichment (the manifest in `before/` is absent, so the
  `context-surface` hook gracefully no-ops in that arm; per-dir
  `AGENTS.md` chain and AIDEV anchors are also absent).

Both arms run as separate `claude` invocations in the same calendar
day, with no carry-over context.

## Reported runs

Canonical dataset (numbered as shown in the chart):

| Run | Configuration   | BEFORE  | AFTER   | Δ        |
|-----|-----------------|--------:|--------:|---------:|
| 1   | Pure A/B        | $23.35  | $21.21  | −9.1 %   |
| 2   | Artifact-only   | $29.98  | $12.97  | −56.7 %  |
| 3   | Artifact-only   | $18.42  | $11.78  | −36.1 %  |
| 4   | Artifact-only   | $20.09  | $18.18  | −9.5 %   |
| 5   | Pure A/B        | $17.83  | $16.36  | −8.2 %   |

Plus one Sonnet 4.6 run on a different task type (structured-logging
migration) for cross-model sanity: **−40 % cost** (not in the chart;
different model and task, listed separately in the top-level README).

Two additional runs were executed but excluded from the canonical
dataset due to **network instability mid-run** (the operator was on
an intermittent connection); they produced contaminated transcripts
and are not surfaced in summaries.

Earlier exploratory runs used pre-v1.8.3 plugin versions where the
`context-surface` PreToolUse hook was either absent or unreliable due
to plugin-install state ambiguity; they are not part of the canonical
dataset. Plugin v1.8.3 was the first reliably-working version of the
hook.

## Metrics

- **Total run cost (USD)** — from the JSONL transcript token counts
  multiplied by the model's pricing.
- **Active runtime (minutes)** — wall-clock time minus user-idle
  pauses. Computed as the sum of inter-event gaps in the JSONL
  transcript with gaps longer than 60 s dropped. Raw wall-clock is
  meaningless across these runs because some operator pauses
  (other-window context-switching, AFK breaks) ran into the tens of
  minutes; the 60 s cutoff cleanly separates "agent working" from
  "operator away". The 120 s cutoff produces near-identical means
  (within 0.2 minutes), so the metric is not sensitive to the
  threshold choice.
- **Files read before first edit** — proxy for orientation cost.
- **Load-bearing AIDEV-NOTE trap caught** — a single documented
  database-driver gotcha in the target codebase (the most natural
  parameter naming would silently produce wrong query results in
  production). Binary per-run flag based on inspecting the generated
  SQL in each run's output.

## Reproducer

The two worktrees (`before/` and `after/`) and the task spec are not
committed here — they belong to the client codebase. The shape of the
harness is reproducible by anyone with sufficiently complex
before/after trees of their own:

1. Two trees of the same codebase, one with the claude-leverage
   artifacts (root + per-dir `AGENTS.md`, AIDEV anchors, ADRs, manifest)
   and one without.
2. Identical task prompt, fresh `claude` invocations in separate
   shells, same calendar day.
3. After both finish, parse the JSONL transcripts to extract cost,
   tool-call counts, file-read counts; read `_RUN_NOTES.md` in each
   tree for qualitative findings.

## Regenerating the chart

After adding a new run to the `RUNS` list in `plot.py`:

```bash
python bench/eval/plot.py
```

Writes `bench/eval/results.png`, which is committed and embedded in
the top-level README.
