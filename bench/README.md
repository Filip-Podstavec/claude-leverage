# bench/ — synthetic benchmark for claude-leverage

Compares **baseline Claude Code** vs **claude-leverage plugin** on a fixed set of
representative development tasks. Real headless `claude -p` invocations, token
counts and equivalent USD cost pulled straight from stream-json. Honest about
what is measured, what is not, and where the plugin hurts.

Design doc: [`../docs/superpowers/specs/2026-05-21-synthetic-benchmark-design.md`](../docs/superpowers/specs/2026-05-21-synthetic-benchmark-design.md)

## What it measures

- **Total tokens** per session, broken down by `input / output / cache_read / cache_creation`
- **Equivalent USD cost** (from `stream-json` `result.total_cost_usd`)
- **Per-model usage** breakdown from `result.modelUsage` (Opus / Sonnet / Haiku)
- **Per-agent token cost** for `claude-leverage` delegations (read from `~/.claude/claude-leverage-stats.jsonl` between session snapshots)
- **Deterministic quality check** per task — regex on output and/or git state. A leveraged run only counts toward the savings claim if its check passes.

## What it does NOT measure

- Wall-clock end-user latency (logged but not headlined)
- Statistical significance — N=3 per cell is too small to make confidence claims
- Realistic-suite coverage — 4 tasks is a mini-suite, expanded in v2
- Multi-language fixtures — Python only in v1
- Routing heuristic correctness — T3/T4 use explicit `/commit-smart`; routing under natural prompts is v2

## Mini-suite tasks

| ID | Path | What it tests |
|---|---|---|
| T1 | code-review | Reviewer must find a seeded SQL-injection-style bug in a 3-file staged diff |
| T2 | context-gather | Context gatherer must surface the 3 key files for a new endpoint |
| T3 | commit-trivial | 1-file 4-line typo fix should route to Haiku in leveraged condition |
| T4 | commit-nontrivial | 3-file ~80 LOC mixed diff should route to Sonnet |

Fixtures are git-initialized directories under [`fixtures/`](fixtures/). Each is
copied to `$TMPDIR/leverage-bench-<runid>/<cell>/` before each run, then deleted.

## How to run

Requires:
- Claude Code 2.1.x on your `PATH`, logged into a subscription (Max / Pro)
- Python 3.10+ with `pyyaml`, `matplotlib`, `numpy`
- Local git

```bash
# 1. (re)build fixtures - idempotent
python bench/fixtures/build_fixtures.py

# 2. Run the suite (24 sessions = 4 tasks x 2 conditions x N=3)
python bench/harness/run.py --n 3

# 3. Render reports + charts
python bench/harness/report.py
python bench/harness/per_agent_report.py
```

Resumable: `python bench/harness/run.py --resume` skips completed cells.

Subset run:
```bash
python bench/harness/run.py --tasks T1,T2 --conditions leveraged --n 1
```

Dry-run plan:
```bash
python bench/harness/run.py --dry-run
```

## Output layout

```
bench/results/YYYY-MM-DD_vX.Y.Z/
├── manifest.json              plugin version, claude-code version, N, models resolved, total cost
├── raw/                       per-cell artifacts
│   ├── <cell>.jsonl           full stream-json transcript
│   ├── <cell>.hooks.log       captured stderr (rarely useful; hook writes to central log instead)
│   ├── <cell>.session.json    parsed summary: tokens, cost, quality, delegations
│   └── <cell>.quality.json    quality-check pass/fail + reasons
├── report.md                  human-readable summary (used by README)
├── hero.png                   per-task savings chart (README hero)
├── per-task.png               2x2 grid: tier breakdown per task
├── per-agent-report.md        INTERNAL: per-agent verdicts (GREAT / GOOD / MARGINAL / DELETE)
└── per-agent-scatter.png      scatter: savings vs invocation count
```

Each run dir is immutable. The top-level README points to `bench/latest/`
(a junction on Windows; on Unix a symlink). Updates of the symlink are manual
to force a human review of each release's numbers.

## How baseline isolation works

We do NOT override `CLAUDE_CONFIG_DIR` — that breaks subscription auth (no
keychain in a fresh dir). Instead:

- Run from `$TMPDIR/leverage-bench-<runid>/<cell>/work/`, outside the repo, so `CLAUDE.md` from the parent tree does not leak in
- `--setting-sources project` skips user-scope settings (verified empirically: `plugins: []` and only built-in agents present)
- `--no-session-persistence` keeps history out of `~/.claude/projects/`
- Each fixture is freshly copied before each run; the working tree is hash-verified equivalent before the session starts

Leveraged condition only differs by `--plugin-dir <repo>`, which loads
`claude-leverage`'s 10 agents and 9 commands inline for that session.

## Reading the per-agent verdicts

The per-agent report is **internal**, not for README. Use it to decide which
agents to keep, improve, or drop.

| Verdict | Threshold |
|---|---|
| GREAT | savings > 50% AND quality ≥ 90% AND max < 2× median |
| GOOD | savings 20-50% AND quality ≥ 90% |
| MARGINAL | savings 5-20%, OR savings > 20% with quality 70-90% |
| NEEDS IMPROVEMENT | savings 0-5%, OR quality < 70% |
| DELETE CANDIDATE | savings ≤ 0 AND n ≥ 5 invocations |
| INSUFFICIENT DATA | n < 3 invocations (default in mini-suite — each agent fires ≤ N times) |

## Known limitations

- **Cold cache penalty.** Every cell uses a fresh `CLAUDE_CONFIG_DIR`-equivalent state, so every session pays system-prompt cache creation. Leveraged sessions pay more because the plugin adds ~10 agents to the system prompt. In real long-running sessions the plugin overhead amortizes; in mini-suite it is fully charged on every run. We disclose this in `report.md`.
- **N=3 is small.** Variance can be substantial run-to-run. We show min-max whiskers explicitly and refuse statistical significance claims at this N.
- **Quality checks are deterministic but narrow.** They catch obvious regressions (missed seeded bug, wrong commit message format) — not subtle quality drops.
- **Model drift.** Claude Code may upgrade the underlying model silently. We capture the resolved model into `manifest.json` and refuse cross-version comparisons.
- **Plugin paths are local.** The harness passes `--plugin-dir <this repo>`; results pin to the exact code present at run time, not the published plugin version.
