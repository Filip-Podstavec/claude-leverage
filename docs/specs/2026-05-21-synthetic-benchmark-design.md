# Synthetic benchmark for claude-leverage — design

**Date:** 2026-05-21
**Plugin version targeted:** 0.10.0
**Status:** approved (brainstormed in conversation, finalized after Plan-agent consultation)

## Purpose

`claude-leverage`'s README claims **30–70% token savings on typical development work, with no compromise on code quality**. The claim today is supported only by the `/leverage-stats` heuristic, which counts tokens delegated to Sonnet/Haiku and multiplies by a fixed cost ratio. That is a *projection*, not a *measurement*. This benchmark replaces the projection with real comparative numbers, honest about what they include, what they exclude, and where the plugin actually hurts.

Secondary goal: **per-agent verdicts**. The benchmark surfaces which agents save the most tokens, which add overhead, and which are candidates for deletion. The verdict report is internal; the README only carries the headline cost numbers.

## Scope

In scope:
- Token-cost comparison: baseline (no leverage) vs leveraged (plugin loaded) on 4 representative tasks
- Deterministic quality check per task (regex on output / git plumbing) — a leveraged run only counts toward the savings claim if its quality check passes
- Per-agent breakdown derived from `track-delegations.sh` logs
- Hero chart + per-task chart for README; per-agent report for internal use
- Versioned, immutable result artifacts in `bench/results/YYYY-MM-DD_vX.Y.Z/`

Out of scope (deferred):
- Adaptive-N expansion (N=3 fixed for first run; logic stubbed for v2)
- Full realistic suite (10–15 tasks); mini-suite of 4 is v1
- Wall-clock benchmarking (token cost only — duration is logged but not headlined)
- Statistical significance claims in README (N=3 is too small to make them honestly)
- CI automation (subscription auth not available in CI runners)
- LLM-as-judge quality checks
- Per-PR regression gating

## Architecture

```
bench/
├── README.md                          how to run / how to read / what it does and does not measure
├── harness/
│   ├── run.py                         orchestrator: tasks × conditions × N runs, claude -p subprocess
│   ├── score.py                       parses stream-json result, runs quality checks
│   ├── report.py                      generates markdown + hero.png + per-task.png
│   ├── per_agent_report.py            per-agent verdicts (GREAT/GOOD/MARGINAL/NEEDS-IMPROVEMENT/DELETE)
│   ├── style.py                       shared matplotlib style (colors, fonts, rcParams)
│   ├── tasks.yaml                     4 task definitions: prompt, fixture, quality check
│   └── _state/                        checkpoint state for resumable runs (gitignored)
├── fixtures/
│   ├── code-review-medium/            T1: ~6-file Python repo with staged diff containing seeded SQL injection
│   ├── context-gather-feature/        T2: same repo template, no staged diff, prompt asks for context for new endpoint
│   ├── commit-trivial/                T3: 1-file 4-line README typo fix, staged
│   └── commit-nontrivial/             T4: 3-file ~80 LOC mixed-concerns change, staged
└── results/
    ├── 2026-05-21_v0.10.0/            first run
    │   ├── manifest.json              plugin version, claude-code version, models resolved, N, timestamp
    │   ├── raw/                       per-run JSONL: stream-json + delegations + quality result
    │   ├── report.md                  human-readable summary
    │   ├── per-agent-report.md        internal verdicts
    │   ├── hero.png                   for README hero
    │   └── per-task.png               for README Benchmarks section
    └── latest -> 2026-05-21_v0.10.0/  symlink, README points here
```

## Decisions

### 1. Execution mode
- Headless `claude -p` subprocess, one session per (task × condition × run).
- Profile isolation: each session uses a fresh empty `CLAUDE_CONFIG_DIR` under `$TMPDIR`. Baseline has no plugin. Leveraged uses `--plugin-dir <repo>` to load `claude-leverage`. Empirically verified: `--plugin-dir` loads all 10 agents + 9 slash commands; without it, only Claude Code built-ins (`Explore`, `general-purpose`, `Plan`, `statusline-setup`) are present.
- `--setting-sources project` to skip user-scope settings (prevents the developer's own `~/.claude/` plugins from leaking in).
- Fixtures executed in `$TMPDIR/leverage-bench-<runid>/<task>/`, **outside the repo**, so `CLAUDE.md` from the parent tree does not leak into baseline.
- `--no-session-persistence` keeps the conversation history out of `~/.claude/projects/`.
- `--output-format stream-json --verbose` — `--verbose` is required with `--print + stream-json`.
- `--dangerously-skip-permissions` — required for non-interactive bash/edit operations.
- Model is left at session default (resolves to `claude-opus-4-7[1m]` today). The resolved model ID is captured into `manifest.json` from the `system.init` event. Comparing across two result directories with different model IDs is refused by the harness.

### 2. Mini-suite tasks

| ID | Path | Prompt | Fixture | Expected leverage |
|---|---|---|---|---|
| T1 | code-review | "Review the staged changes for bugs, security issues, and quality problems. Report findings clearly with severity." | 6-file Python service, ~120 LOC staged diff across 3 files, **seeded SQL-injection in `routes/users.py`** (f-string into raw query), one realistic refactor as noise. | `code-reviewer` (Sonnet) |
| T2 | context-gather | "I want to add a /healthz endpoint that returns the same uptime+version JSON as /status but without authentication. Gather the implementation context I'll need before I start coding. Do not write code." | Same Python repo template, `/status` endpoint with auth decorator, version constant in `__init__.py`, existing tests for `/status`. | `context-gatherer` (Sonnet) |
| T3 | commit-trivial | "Commit the staged changes using /commit-smart." (baseline omits the `/commit-smart` part — see below) | 1-file 4-line README typo fix, staged, clean otherwise, fake `origin` remote (local bare repo). | `git-committer-quick` (Haiku) |
| T4 | commit-nontrivial | "Commit the staged changes using /commit-smart." | 3-file ~80 LOC mixed diff (new function + caller + new test), staged. | `git-committer` (Sonnet) |

**Routing strategy — explicit slash commands, not natural prompts.** First-pass benchmark uses explicit invocations (`/commit-smart`) in the leveraged condition so we know exactly which agent fires. Baseline uses the same prompt but with the slash command stripped (no `/commit-smart` available without the plugin). This tests **agent execution**, not the routing heuristic. Routing heuristic testing is v2.

**Why these 4:** code-reviewer and context-gatherer are the two highest-traffic agents in normal use. T3 and T4 paired test both branches of the commit-routing decision, which is the most distinctive structural claim of the plugin (Haiku for trivial, Sonnet for non-trivial). docs-sync, flaky-test, research, repo-explorer all excluded — low frequency / overlap with context-gatherer / hard to fixture deterministically.

### 3. Quality checks

One deterministic check per task, runs in Python against the final transcript and/or repo state.

| Task | Quality check |
|---|---|
| T1 code-review | Output (case-insensitive) contains all of: `users.py` AND at least one of `{sql, injection, raw query, f-string, concat}`. Score = 1 if pass, 0 if fail. |
| T2 context-gather | Output contains all three substrings: the status-route filename, the auth-decorator name, the version-constant name. All three required. |
| T3 commit-trivial | After session: `git log -1 --format=%s` matches `^(docs|chore|fix)(\([a-z0-9_-]+\))?: `, exactly 1 commit was created during the session, exactly 1 file changed in that commit. |
| T4 commit-nontrivial | After session: `git log -1 --format=%s` matches `^(feat|fix|refactor|chore|test)(\([a-z0-9_-]+\))?: `, exactly 1 commit was created, at least 2 files changed, AND (leveraged only) the track-delegations log shows the commit was made by tier `sonnet` (not `haiku`). |

LLM-as-judge is explicitly avoided: slow, non-deterministic, expensive, undermines benchmark credibility.

### 4. Variance and reporting

- **First run: N=3 per (task × condition).** 4 × 2 × 3 = 24 sessions. Adaptive N (expand to 10 on CV > 0.2) is implemented as a stub in `score.py` but not enabled — deferred to v2 to keep first benchmark under one rate-limit window.
- Report **median**, **min**, **max** across the 3 runs per cell. With N=3 there is no honest IQR — we report the range and note N explicitly. This is a known limitation, called out in the report and README caption.
- **No statistical significance claim** in README. The internal per-agent report uses bootstrap CIs on median differences once N ≥ 10 (not in v1).

### 5. Hero chart

- Horizontal grouped bar, 4 tasks on Y-axis, total tokens (median across N=3) on X-axis.
- Two bars per task: `baseline` (slate `#4A5568`) and `leveraged` (muted blue `#2B6CB0`).
- Thin range whiskers (min–max) capped, same color as bar.
- Annotation at end of leveraged bar: `−42%` (green if savings, red `#C53030` if regression).
- Quality marker inside leveraged bar: `✓` if quality check passed in the median-tokens run, `✗` if failed.
- Title: `claude-leverage v0.10.0 — token cost per task (median, N=3, min–max)`.
- No legend; inline annotation `■ baseline    ■ leveraged` top-right.
- Font: Arial / Helvetica fallback. No DejaVu.
- Render 1600×900 actual, displayed 800px in README.
- Sorted by leveraged savings descending: best wins on top, regressions on bottom. Honest reading order.

### 6. Per-task chart

- 2×2 subplot grid (one per task).
- Each subplot: 2 bars (baseline / leveraged). Baseline is a single Opus-tinted block (`#6B46C1` muted purple). Leveraged is a stacked bar: Opus / Sonnet / Haiku / cache-read in consistent tier colors (Opus `#6B46C1`, Sonnet `#2B6CB0`, Haiku `#2F855A`, cache-read `#A0AEC0`).
- Quality mark + check name in 8pt monospace at bottom-right of each subplot.
- Title: task ID + one-line description.
- Shared legend at bottom.
- 1600×1200 actual, displayed 800px in README.

### 7. Per-agent internal report

Source: `track-delegations.sh` JSONL captured per-session via redirected stderr from `claude -p` (the hook still fires for subagent invocations because it's loaded by the plugin).

Per-agent rows:
- `agent`, `tier_configured`, `n_invocations`
- `median_tokens_per_invocation`, `min`, `max`
- `median_duration_ms`
- `cache_hit_rate = cread / (cread + ccreate + input)`
- `opus_baseline_estimate`: tokens the baseline condition spent on the equivalent task scope (direct read from baseline transcript per task)
- `savings_per_invocation = opus_baseline_estimate − median_tokens`
- `quality_pass_rate`
- `verdict`: see thresholds

Verdict thresholds (applied to median, requires N ≥ 3 invocations for stability):
- **GREAT** — savings > 50% of baseline AND quality_pass_rate ≥ 0.9 AND max < 2× median (predictable)
- **GOOD** — savings 20–50% AND quality_pass_rate ≥ 0.9
- **MARGINAL** — savings 5–20%, OR savings > 20% but quality 0.7–0.9. Action: investigate prompt / heuristic.
- **NEEDS IMPROVEMENT** — savings positive < 5%, OR quality < 0.7. Action: rework before next release.
- **DELETE CANDIDATE** — savings ≤ 0 AND n_invocations ≥ 5. Don't delete on first bad run.
- **INSUFFICIENT DATA** — n_invocations < 3. Default for v1 where each agent only fires in 1 task's runs.

**Delegation overhead is charged to the agent**, not the baseline: the parent turn's `tool_use` token cost (Task tool input/output payload) is subtracted from savings. Otherwise we systematically over-credit.

Also emitted: per-task-per-agent matrix (catches the "great on T1, terrible on T2" case that global averages hide), and a scatter plot of `savings_per_invocation` vs `n_invocations` (per agent, color-coded by verdict).

### 8. Pitfalls + mitigations (verified during build)

| Risk | Mitigation |
|---|---|
| `CLAUDE.md` walks up parent dirs and leaks repo CLAUDE.md into baseline | Run fixtures from `$TMPDIR/leverage-bench-<runid>/<task>/`, never from inside the repo |
| User-scope `~/.claude/` plugins leak into baseline | `--setting-sources project` + verify in smoke that baseline's `agents` list only contains CC built-ins |
| Model auto-upgrade between runs makes results non-comparable | Capture `model` from `system.init` into manifest; harness refuses cross-run comparisons on mismatch |
| Hook stderr pollutes stream-json parser | Keep stderr separate (`2> hooks.log`), parse only stdout for stream-json |
| Rate limit hits mid-suite | Checkpoint per (task, condition, run_idx) to `bench/harness/_state/`; resume skips completed cells |
| Fixture mutation across runs | `git clean -fdx && git reset --hard fixture-base` before each run + sha256 check of working tree against golden hash |
| Cache warming bias (run #1 pays creation, run #2-N reads) | Use fresh CLAUDE_CONFIG_DIR per run — every run is cold-cache. Report cold cost honestly. |
| Network failure mid-run silently produces invalid result | Bail with exit 2 if a run takes >3× median of completed runs in same cell |
| Baseline session uses `Explore` built-in agent, blurring "no leverage" framing | Accept it; baseline = "vanilla Claude Code", not "Opus with no agents". Document in report caption. |
| Slash command namespacing (`claude-leverage:commit-smart`) might not resolve from unprefixed `/commit-smart` | Smoke-test during harness build; fall back to prefixed form if needed |

### 9. Output artifacts

For each run directory `bench/results/YYYY-MM-DD_vX.Y.Z/`:

- `manifest.json` — pinned versions, models resolved, N, timestamps, total cost USD, total wall-clock minutes
- `raw/<task>__<condition>__<run_idx>.jsonl` — full stream-json for that session
- `raw/<task>__<condition>__<run_idx>.hooks.log` — captured stderr (track-delegations notes)
- `raw/<task>__<condition>__<run_idx>.quality.json` — quality-check pass/fail + which assertion fired
- `report.md` — markdown summary, tables per task, all numbers, raw data references
- `per-agent-report.md` — per-agent verdicts + action items
- `hero.png` — README hero chart
- `per-task.png` — README Benchmarks section chart
- `per-agent-scatter.png` — internal: savings vs invocations scatter

`bench/latest` is a symlink (on Windows: a junction or `latest.txt` pointer file) to the most recent run dir.

## Honesty principles (load-bearing)

1. **Show negatives.** If leverage costs more on T3 because the delegation overhead exceeds savings, the bar in the hero chart goes red. We do not hide it.
2. **Cite N.** Every chart title and README caption states N explicitly. "Median, N=3, min–max range." No marketing inflation.
3. **Cold cache is reported.** Every session pays cache creation. The numbers reflect that, and the report says so. We don't measure warm-cache numbers and present them as typical.
4. **Quality is a gate, not a separate metric.** A leveraged run that fails its quality check does **not** count toward "% savings" in the headline. Failed leveraged runs are still tabulated in the per-task table with a `✗` mark.
5. **Limitations section is explicit.** README and report carry a "What this does NOT measure" paragraph: no wall-clock, no statistical significance with N=3, no realistic-suite coverage, no cross-language coverage, no monorepo coverage.

## Out-of-scope for v1

- Adaptive N expansion (stubbed)
- 10–15 task realistic suite
- Multi-language fixtures (only Python in v1)
- Monorepo / large-codebase fixtures
- Cross-version trend chart (only one run exists)
- CI automation
- Wall-clock benchmarking

These belong in v2, planned after v1 produces stable numbers and we know which pitfalls actually bit.

## README integration

- **Hero chart** placed below the existing top-of-README marketing paragraph and badge row, above the "Why" section. One sentence above it: *"Real benchmark numbers, not estimates."*
- **Benchmarks section** added after "Workflow example", before "Quick install". Contains: per-task chart, table with per-task numbers, link to `bench/latest/report.md`, "Last benchmarked: YYYY-MM-DD on claude-leverage vX.Y.Z" badge.
- **Limitations paragraph** is part of Benchmarks section, not buried in a footnote.
- The existing "30–70% token savings" claim in the marketing paragraph stays for now, **but is hyperlinked to the Benchmarks section**. Once the benchmark produces a tighter number, the claim is updated to match.

## Build sequence

1. Spec written (this file)
2. `bench/README.md` (how to run, how to read)
3. `bench/harness/style.py` (matplotlib style)
4. `bench/harness/tasks.yaml`
5. Fixture builders (`bench/fixtures/*` — git-init scripts, seed files)
6. `bench/harness/score.py` (token accounting, quality checks)
7. `bench/harness/run.py` (orchestrator, profile isolation, checkpointing)
8. `bench/harness/report.py` (markdown + hero + per-task PNGs)
9. `bench/harness/per_agent_report.py` (internal verdicts + scatter)
10. First run: 24 sessions
11. Generate reports + PNGs
12. Update top-level README

Each step verified before next; failures in step N block step N+1.
