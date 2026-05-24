# Archive: token-savings thesis (claude-leverage v0.x)

This directory is the **frozen evidence** of an experiment that did not work
out, kept verbatim because the honest pivot is part of the project's story.
Do not delete.

## What was the thesis?

`claude-leverage` v0.x argued that routing development work across model
tiers (Sonnet/Haiku subagents for execution, Opus main session for
orchestration) would reduce token costs versus vanilla Claude Code, while
preserving output quality.

We built 12 subagents (`code-reviewer`, `test-runner`, `context-gatherer`,
`git-committer{,-quick}`, `repo-explorer`, `research-agent`, `docs-updater`,
`flaky-test-isolator`, `output-digester`, `impact-mapper`, `focused-reviewer`),
five wrapper commands (`/code-review`, `/test`, `/gather-context`,
`/docs-sync`, `/flaky-test`), CLAUDE.md routing snippets to auto-delegate
based on scope, and a benchmark harness to verify the savings claim against
real headless `claude -p` runs.

## What did the data show?

**Every subagent we shipped lost its isolated audit on Opus 4.7**, regardless
of model tier or output schema. The full per-cell evidence is in
[`results/`](results/); the audit summaries are in the directories named
`audit-*`. Headline numbers (most recent run, 2026-05-24):

| Stage | Baseline | Leveraged | Delta |
|---|---:|---:|---:|
| Cold cache, 4 tasks                 | $0.37 | $0.64 | **+73 %** |
| Warm cache, 4-turn workflow         | $0.24 | $0.39 | **+63 %** |
| Warm cache, 12-turn day-in-the-life | $0.51 | $1.11 | **+117 %** |

The mechanism: vanilla Claude Code already orchestrates via built-in
`Explore` (Haiku) and `general-purpose` agents that the main session calls
for free. Adding `claude-leverage` introduced a parallel orchestration layer
where every `Task`-tool dispatch paid its own `cache_creation` in a cold
subagent session — a per-invocation tax that exceeded the per-token savings
from running the work on Sonnet/Haiku.

Prompt caching on Opus 4.7 makes "read large, emit small" cheap inline; a
cold subagent dispatch can't beat a warm main-session cache. This isn't a
tuning problem; it's structural to how the plugin model interacts with the
model-call cost curve.

## Why keep the archive?

1. **Credibility.** Disproving your own headline claim on the public record
   is rare; deleting the evidence would erase the reason to trust subsequent
   design decisions (which are conservative as a direct result of these
   findings).
2. **Reproducibility.** Anyone reading the v1.0.0 design specs can run the
   exact same harness against any future Claude Code version and verify the
   structural finding still holds (or, more interestingly, no longer holds).
3. **Component salvage.** Two subagents survived non-cost-based scrutiny and
   were promoted back to the top-level:
   - `agents/flaky-test-isolator.md` — produces deterministic statistical
     signal across N runs; the work is naturally isolated from the main
     session.
   - `agents/security-reviewer.md` (added in v1.0.0, see
     [`docs/specs/2026-05-24-pivot/02-security-first.md`](../../docs/specs/2026-05-24-pivot/02-security-first.md))
     — read-only Sonnet, deterministic Critical/Important/Nice schema.

Everything else (11 agents + 4 wrapper commands + 5 routing snippets) lives
here, frozen at the version it shipped at retirement. The path was previously
`extras/`; the move into `bench/archive-token-savings-thesis/` is what makes
"this is archived, not opt-in" explicit.

## Layout

```
archive-token-savings-thesis/
├── HOWTO.md                       Original bench/README.md (how to run)
├── extras-README.md               Original extras/README.md (per-agent verdicts)
├── agents/                        11 retired subagents
├── commands/                      4 retired wrapper commands
├── claude-md-snippets/            5 retired routing snippets
├── fixtures/                      Task fixtures used by the harness
├── harness/                       run.py, audit_*.py, report.py, ...
└── results/                       Per-run results, charts, raw stream-json
```

## Reproducing today

`HOWTO.md` documents the original commands. The harness still works against
the current Claude Code version; you just need to point it at this archive's
`fixtures/` and `harness/` instead of the original top-level `bench/`. Read
the file before running — the per-cell session count, model resolution, and
CC version assumptions matter for honest comparison.
