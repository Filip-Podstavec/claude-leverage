<div align="center">

<img src="assets/banner.svg" alt="claude-leverage" width="640">

**Make any repo AI-first - write sustainable code from the start, or refactor a legacy codebase to prepare it for agent-driven development.**

[![Claude Code - first-class](https://img.shields.io/badge/Claude_Code-first--class-8b5cf6?style=for-the-badge)](https://docs.anthropic.com/en/docs/claude-code)
[![Codex CLI - first-class](https://img.shields.io/badge/Codex_CLI-first--class-10a37f?style=for-the-badge)](https://developers.openai.com/codex)

<sub>Convention layer (<code>AGENTS.md</code>) is also read by any AGENTS.md-aware tool - Cursor, Windsurf, Copilot…</sub>

<br>

[![CI](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml/badge.svg)](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-1.11.0-success)
![Skills](https://img.shields.io/badge/skills-15-8b5cf6)
![Hooks](https://img.shields.io/badge/hooks-9-orange)
![Subagents](https://img.shields.io/badge/subagents-2-1f6feb)

</div>

> A small, opinionated **AI-coding-agent suite** for Claude Code and Codex CLI:
> deterministic security hooks, cross-tool skills, and self-maintaining
> conventions that keep a repo safe for the *next* agent to modify.
>
> **Complements** skills-based plugins like the official `superpowers` plugin;
> it does not try to replace them.

## Contents

- [The problem it solves](#the-problem-it-solves)
- [Who it's for](#who-its-for)
- [Quick start](#quick-start)
- [Install](#install)
- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [Benchmarks](#benchmarks)
- [How it compares](#how-it-compares)
- [What's inside](#whats-inside)
- [Why one repo for two tools](#why-one-repo-for-two-tools)
- [Honest history](#honest-history)
- [Verify, update, uninstall](#verify-update-uninstall)
- [License](#license)

## The problem it solves

Shipping at velocity with AI agents is easy. Shipping in a way that the *next*
agent (human or AI) opening the repo in six months can still safely modify is
the hard part. That second part is what the hooks, conventions, and skills here
automate - not just at session start, but continuously as the repo grows.

<table>
<tr><th align="left">Without a stack</th><th align="left">With claude-leverage</th></tr>
<tr>
<td>Context dies between sessions - every agent re-learns the repo from scratch.</td>
<td>AIDEV anchors + the <code>context-surface</code> hook surface the right facts at the moment of edit.</td>
</tr>
<tr>
<td>Docs drift out of sync with the code until nobody trusts them.</td>
<td>Self-maintenance nudges flag missing <code>AGENTS.md</code>, stale anchors, and code↔docs drift while it's still cheap to fix.</td>
</tr>
<tr>
<td>Big tasks lose the plot; the <em>why</em> behind decisions evaporates.</td>
<td>Durable memory: ADRs and distilled session logs carry intent across sessions.</td>
</tr>
<tr>
<td>Nothing stands between a careless agent and a leaked secret or a force-push.</td>
<td>Deterministic shell hooks block secrets, force-push, and <code>--no-verify</code> before any model decision.</td>
</tr>
</table>

Three properties guide every decision in this repo:

1. **Security by default** - deterministic hooks, no model needed.
2. **Self-maintaining as the repo grows** - non-blocking nudges surface
   maintenance debt early.
3. **Cross-tool by design** - same `AGENTS.md`, same `SKILL.md`, same hook
   scripts in Claude Code and Codex. Author once.

## Who it's for

- **Freelancer on client repos** - you ship features across many client
  codebases through agents, and each one has to stay safe to hand back. The
  security hooks and `AGENTS.md` conventions travel with you.
- **Team inheriting a legacy repo** - you've opened a six-month-old codebase
  with no docs. `/repo-doctor` scores its AI-readiness and names the
  highest-leverage gaps; the bootstrap skills make it navigable fast.
- **Solo builder shipping at velocity** - you want speed without the repo
  rotting into unmaintainable AI-slop. Self-maintenance nudges plus ADR/session
  memory keep intent intact.

## Quick start

**Inheriting or already have a repo? Start here.** Install the plugin:

```
/plugin marketplace add Filip-Podstavec/claude-leverage
/plugin install claude-leverage@filip-podstavec
```

Then make the repo AI-ready, top-down:

1. **`/repo-doctor`** - read-only AI-readiness audit. Scores ~24 dimensions
   (Foundation / Why / What / In-code / Hygiene / Sync), reports a readiness
   level (L0–L4) with a local score trend, and names the gaps that matter
   most (`--fix` walks you through them).
2. **Fix the top gaps it reports** - usually `/init-repo` (drop in a root
   `AGENTS.md`), then `/arch-map` and `/glossary-init` for machine-readable
   module metadata and domain terms.
3. **`/refresh-context-map`** - build the manifest that powers just-in-time
   context surfacing, so the right anchors appear at edit time.

**Starting a fresh repo?** Install, then run `/init-repo` to drop in
`AGENTS.md`, `.gitignore` patterns, and an optional structured-logging starter.

Full install (including Codex CLI) is below.

## Install

### Claude Code

```
/plugin marketplace add Filip-Podstavec/claude-leverage
/plugin install claude-leverage@filip-podstavec
```

That's it. **Restart Claude Code** (or run `/skill list` and `/agents` in a
current session) to pick up all 15 skills and 2 subagents.

### Codex CLI

Two ways to use the stack with Codex — they're complementary, not either/or.

**A. Plugin marketplace (skills + hooks).** Codex now has a plugin marketplace;
add this repo as a marketplace source and install it from `/plugins`:

```bash
npm i -g @openai/codex        # one time
```
Then in a Codex session, open `/plugins`, add the marketplace from GitHub
shorthand `Filip-Podstavec/claude-leverage`, open the `claude-leverage` plugin,
and select **Install plugin**.

This delivers the **skills** and the **security/nudge hooks** (Codex sets
`CLAUDE_PLUGIN_ROOT` for compatibility, so the same `hooks/hooks.json` works).
It does **not** deliver the subagents or the `/flaky-test` command — Codex
plugins don't load those — nor the global `@AGENTS.md` import. For the full
stack, use option B.

**B. Install script (full stack: + subagents + global AGENTS.md import).**

```bash
# 1. Install Codex CLI itself (one time)
npm i -g @openai/codex

# 2. Clone this repo to a stable location
git clone https://github.com/Filip-Podstavec/claude-leverage.git ~/.local/share/claude-leverage
cd ~/.local/share/claude-leverage

# 3. Run the installer
bash scripts/install-codex.sh         # macOS / Linux / WSL2
# OR
pwsh scripts/install-codex.ps1        # Windows PowerShell
```

<details>
<summary>What the Codex installer does</summary>

1. Resolves repo path into `~/.codex/hooks.json` so security + nudge hooks
   fire in every Codex session globally.
2. Appends `@<repo-path>/AGENTS.md` to `~/.codex/AGENTS.md` so the canonical
   guidance loads on every Codex session.
3. Copies `.codex/agents/*.toml` to `~/.codex/agents/`.
4. Copies all 15 skills to `~/.agents/skills/claude-leverage/` so they work
   in Codex sessions exactly as in Claude Code.

**Idempotent**: re-running detects existing install via marker comments and
overwrites in place. Atomic skill swap (staging dir + rename) so a copy
failure mid-loop leaves the previous install intact.

</details>

### Optional: portable statusline

Five segments shown left-to-right: 5-hour rate limit, 7-day rate limit, current
context window %, model name, git branch.

![statusline](statusline/screenshot.png)

Claude-Code-only (Codex has no statusline). Single Python file, no `jq`
dependency, works on Windows under Git Bash. Color thresholds: green <60 %,
yellow 60-84 %, red ≥85 %.

```bash
# Copy into ~/.claude/ (overwrites only if you have no statusline configured)
cp statusline/statusline-command.sh ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
```

Then add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash ~/.claude/statusline-command.sh"
}
```

Restart Claude Code. To opt out later: delete the `statusLine` block from
`settings.json`.

## What you get

<details>
<summary><strong>Always-on safety</strong> - hooks, no setup, no model invocation</summary>

- `block-secrets-precommit` - refuses `git commit` if staged diff contains
  API keys / tokens / private keys (per-line allowlist via marker comment)
- `block-dangerous-git` - refuses `git push --force`, `--no-verify`,
  `git reset --hard` on protected branches
- `ai-first-nudge` - non-blocking: ≥50 net-new LOC without AIDEV-NOTE on
  non-test files OR new source-dir without AGENTS.md → one-line suggestion
- `security-nudge` - non-blocking Stop hook: ≥80 net-new LOC touching
  sensitive paths → suggests `/security-review`
- `stack-freshness` - non-blocking SessionStart: 30+ days since last
  `/stack-check` → one-line reminder via SessionStart `additionalContext`
  (no network)
- `bare-repo-nudge` - non-blocking SessionStart, two-branch nudge:
  (A) cwd is not a git repo AND not `$HOME`/`/tmp`/system → reminder
  to `git init` + `/init-repo`; (B) cwd IS a git repo but root has no
  `AGENTS.md` / `CLAUDE.md` AND has a project marker file
  (`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / …)
  → reminder to `/init-repo` so the convention layer (AIDEV anchors,
  structured logging, …) actually gets loaded. One-per-day per
  cwd/repo-root.
- `skill-cheatsheet` - non-blocking SessionStart, gated on the repo
  having a `claude-leverage:` marker in `AGENTS.md` (i.e., the user
  has actively adopted the stack). Surfaces a compact list of
  high-value skills + triggers once per 14 days per repo, via
  SessionStart `additionalContext`. Mitigates the documented
  skill-auto-activation gap (`description: |` block scalars where
  the runtime parses only the first line). Override via
  `CLAUDE_LEVERAGE_SKILL_HINT_DAYS` (0 = disabled).
- `overdue-todo-nudge` - non-blocking SessionStart, network-free. Flags
  `AIDEV-TODO` / `AIDEV-QUESTION` anchors whose ISO-8601 deadline has
  already passed, via SessionStart `additionalContext`, once per repo
  per day. Source code only + first-token rule keep false positives near
  zero (skips the doc/template/test trees where example anchors live).
  The passive complement to `/stack-check`'s on-demand anchor report.
  Opt-out: `CLAUDE_LEVERAGE_SKIP_OVERDUE_TODO=1`.
- `context-surface` - **opt-in** PreToolUse hook on
  `Read|Edit|Write|MultiEdit`. Reads a pre-built manifest at
  `.claude-leverage-context-map.json` (produced by `scripts/build-context-map.py`,
  or `/refresh-context-map` skill) and emits the AIDEV anchors that
  apply to the file the agent is about to touch via
  `hookSpecificOutput.additionalContext`. Cuts per-session token tax -
  agent no longer has to read every `AGENTS.md` preemptively to catch
  documented gotchas; the right anchors are surfaced at the moment of
  edit. Graceful no-op when manifest is missing. Verbose mode
  (`CLAUDE_LEVERAGE_CTX_VERBOSE=1`) also emits per-dir `AGENTS.md` chain
  + ADR refs. Opt-out: `CLAUDE_LEVERAGE_CTX_DISABLE=1`. See
  [ADR 0008](docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md).

</details>

<details>
<summary><strong>Security review</strong> - skill + dedicated subagent</summary>

- `/security-review` - audit current diff for OWASP-Top-10-shaped issues +
  `package.json` / `requirements.txt` typosquatting heuristic. Read-only
  Sonnet subagent returns Critical / Important / Nice schema with
  `file:line`. No dependency on any other plugin.

</details>

<details>
<summary><strong>Repo-maintenance skills</strong> - invoke periodically</summary>

- `/repo-map` - refresh the architecture mermaid block in README between
  idempotent markers; optional dep-graph block via `madge` / `pydeps`
- `/process-diagram <name>` - sequence/flowchart for a named workflow,
  inserted into target markdown between markers, mmdc-validated
- `/stack-check` - Claude Code + Codex + plugin + CLI dep versions vs
  `stack.toml`, plus stale-anchor walk + AGENTS.md sanity audit
- `/log-structured` - audit non-structured logging, suggest spec-compliant
  replacements per the JSON-lines convention

</details>

<details>
<summary><strong>Setup &amp; handoff skills</strong> - per-project / per-decision</summary>

- `/init-repo` - bootstrap a fresh project: AGENTS.md from per-language
  template, `.gitignore` patterns, optional structured-logging starter
- `/codex-sandbox` - configure per-project `.codex/config.toml` sandbox +
  approval modes (dev / prod / custom)
- `/explain-diff` - plain-English 3-5 bullet diff narration in three
  audience modes (`--for pr / review / self`)
- `/adr-new` - bootstrap a numbered MADR-flavored Architecture Decision
  Record. Immutable status, captures *why* for the next agent in 6 months
- `/session-log` - distill the current session into `docs/sessions/`. The
  continuity layer between sessions - distillate, not transcript
- `/glossary-init` - bootstrap/extend `GLOSSARY.md` at repo root for
  domain terms specific to *this* repo. Surfaces candidates by identifier
  frequency; never invents definitions (the user types them)
- `/arch-map` - bootstrap/refresh `architecture.yml` at repo root -
  machine-readable module metadata (role/stability/public_surface/...);
  hand-curated, `--validate` mode for CI
- `/repo-doctor` - read-only AI-readiness audit. Scores ~24 dimensions
  across **Foundation** (AGENTS.md, CLAUDE.md, per-dir AGENTS.md),
  **Why** (ADRs, session logs), **What** (GLOSSARY.md,
  architecture.yml), **In-code** (AIDEV anchor density, overdue),
  **Hygiene** (tests + test/source LOC ratio, structured logging,
  .gitignore, README quickstart, language manifest, CI config,
  .env.example, reproducible env, secret guardrails), and **Sync**
  (code↔docs drift: arch-map vs disk, glossary vs code, per-dir
  AGENTS.md staleness, CHANGELOG vs version, README slash-refs).
  Reports a readiness level L0–L4 (gated, not averaged — ADR 0012)
  plus a local score trend; `--fix` walks the top gaps. Each gap →
  concrete fix action. `--score` / `--json` /
  `--fail-on missing|todo|stale` /
  `--scope foundation|why|what|incode|hygiene|sync|all` for CI gating;
  `--semantic` adds an advisory truthfulness review (subagent,
  never in the score)
- `/refresh-context-map` - rebuild `.claude-leverage-context-map.json`,
  the manifest powering the `context-surface` PreToolUse hook. Run after
  anchor / per-dir `AGENTS.md` / ADR changes, or after a `git merge`
  (manifest auto-resolves to local via `.gitattributes merge=ours`, but
  is then stale relative to the merged tree until rebuilt)

</details>

<details>
<summary><strong>Workflow commands</strong> - Claude Code only</summary>

- `/flaky-test` - delegates to `flaky-test-isolator` subagent for N-run
  stability analysis

(For commits, the vanilla Claude commit workflow + the
`block-secrets-precommit` / `block-dangerous-git` hooks already cover
secret scanning, Conventional Commits style, refusing `.env`, refusing
`--no-verify`, and refusing force-push. v1.4.4 removed the
`/commit-smart` slash command - it added a treacherous auto-push to
something that should be opt-in. Just commit with vanilla and push
explicitly when you want.)

</details>

<details>
<summary><strong>Conventions</strong> - enforced via documentation + nudges</summary>

- AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION anchor comments (with optional
  ISO-8601 deadlines: `AIDEV-TODO(by: 2026-08-01)`)
- JSON-lines structured logging spec with `trace_id` / `span_id` / `attrs`
- Per-directory AGENTS.md for non-trivial modules
- ADRs for load-bearing architectural decisions
- Session logs for continuity between AI sessions

</details>

<details>
<summary><strong>Cross-tool plumbing</strong></summary>

- Same `AGENTS.md` for Claude Code (via `@AGENTS.md` import in `CLAUDE.md`)
  and Codex (native read)
- Hook scripts in `scripts/hooks/` shared by both tools
- Skills installed to `~/.agents/skills/` by the Codex installer
- Subagents authored in MD + auto-generated to TOML for Codex parity (CI gate)

</details>

## How it works

Typical session for a security-sensitive feature, end-to-end:

<!-- process-diagram:security-first-flow:start -->
<!-- Regenerable via: /process-diagram security-first-flow --into README.md -->
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CC as Claude Code (Opus)
    participant Hook as scripts/hooks/*.sh
    participant SR as security-reviewer<br/>(Sonnet, read-only)
    participant Git

    User->>CC: edit src/auth/handler.py
    CC->>Hook: PostToolUse (Write/Edit)
    Hook-->>User: ai-first-nudge: "73 LOC no AIDEV-NOTE anchor"

    User->>CC: /security-review
    CC->>SR: Task (delegate)
    SR->>Git: git diff --cached
    Git-->>SR: staged diff
    SR-->>CC: Critical / Important / Nice<br/>(file:line citations)
    CC-->>User: relay report verbatim

    User->>CC: /adr-new "use HS256 not RS256 here"
    CC->>CC: write docs/adr/0007-...md (immutable)

    User->>CC: commit this
    CC->>Hook: PreToolUse (Bash: git commit)
    Note right of Hook: block-secrets-precommit<br/>scans staged diff
    Hook-->>CC: allow (no secrets)
    CC->>Git: commit (Conventional Commits)
    Note right of CC: push only when user asks<br/>(no auto-push in v1.4.4+)

    User->>CC: /session-log "wire HS256 auth + middleware"
    CC->>CC: write docs/sessions/YYYY-MM-DD-...md (distillate)

    Note over CC,Hook: Stop hook: security-nudge fires<br/>if sensitive paths touched (1× per branch/day)
```
<!-- process-diagram:security-first-flow:end -->

Reading the diagram: explicit user invocations are solid arrows
(`User -> CC`), automatic hook firings are dashed `Hook -> User`
returns, subagent delegation is one `Task` round-trip. Nothing in the
maintenance layer (ADRs, session logs) is auto-fired - the agent
recognizes the moment from the trigger-aware skill descriptions and
the convention documented in `AGENTS.md`.

If you haven't run `/stack-check` in 30+ days, the SessionStart
`stack-freshness` hook prints a one-line reminder (no network). The
actual version check + AIDEV anchor health + AGENTS.md sanity audit
only fires on explicit invocation.

For deeper walkthroughs see
[`workflows/onboarding-a-legacy-repo.md`](workflows/onboarding-a-legacy-repo.md),
[`workflows/security-first-feature.md`](workflows/security-first-feature.md),
and [`workflows/maintaining-as-it-grows.md`](workflows/maintaining-as-it-grows.md).

<details>
<summary>Architecture at a glance</summary>

<!-- repo-map:start -->
<!-- This block is regenerated by skills/repo-map. Do not hand-edit.    -->
<!-- Re-run /repo-map to refresh after directory structure changes.     -->
```mermaid
flowchart LR
    Filip["Filip"] --> CC["Claude Code session"]
    Filip --> CX["Codex CLI session"]

    CC -- "reads" --> CMD["CLAUDE.md (1 line: @AGENTS.md)"]
    CMD -- "@import expand" --> AMD["AGENTS.md (canonical)"]
    CX -- "reads directly" --> AMD

    CC -- "loads skills from" --> SK["skills/"]
    CX -- "loads skills from" --> SK

    CC -- "hooks via" --> HK["hooks/hooks.json"]
    CX -- "hooks via" --> HKC["~/.codex/hooks.json (installed)"]
    HK -- "exec" --> SHELL["scripts/hooks/*.sh"]
    HKC -- "exec" --> SHELL

    CC -- "subagents" --> A1["agents/*.md (Markdown+YAML)"]
    CX -- "subagents" --> A2[".codex/agents/*.toml (TOML, generated)"]
```
<!-- repo-map:end -->

</details>

## Benchmarks

**Does claude-leverage actually pay off?** Controlled A/B benchmark on a real
client codebase (~30k LOC Python web service). Two trees of the same codebase:

- **BEFORE** - commit predating claude-leverage adoption. No `AGENTS.md`,
  no AIDEV anchors, no per-directory docs, monolithic API surface.
- **AFTER** - current HEAD with the full in-repo artifact set: root
  `AGENTS.md`, per-directory `AGENTS.md`, AIDEV anchors throughout,
  ADRs, `GLOSSARY.md`, `architecture.yml`, per-domain router split,
  and the `.claude-leverage-context-map.json` manifest powering the
  `context-surface` PreToolUse hook.

Identical implementation task in both arms: add a new paginated HTTP
endpoint following the conventions documented in each tree. Five
Claude Opus 4.7 runs, plus one Claude Sonnet 4.6 run on a different
task type (structured-logging migration) for cross-model sanity.

![A/B benchmark results](bench/eval/results.png)

### Headline (n=5, Opus 4.7)

| Metric | BEFORE | AFTER | Δ |
|---|---:|---:|---:|
| Mean run cost | $21.93 | $16.10 | **−26.6 %** |
| Median run cost | $20.09 | $16.36 | **−18.6 %** |
| Mean active runtime (minutes) | 9.8 | 8.6 | **−12.1 %** |
| Files read before first edit | 22.4 | 18.8 | −16.1 % |
| Load-bearing AIDEV-NOTE trap caught | 0 / 5 | **5 / 5** | |
| Cost direction | - | cheaper in **5 / 5** runs | |

Plus the separate Sonnet 4.6 run on a logging-migration task: **−40 % cost**.

### Cheaper *and* the code is more maintainable

The cost number alone understates the value, because **the AFTER agent
does not get cheaper by being lazier**. It gets cheaper by being
*dramatically* more efficient at orientation, then often spends part of
the saved budget producing **richer, more convention-aware output**:

- Less searching around - Grep counts drop −40 to −60 % per run, Glob
  often drops to zero. The agent knows where to look because per-
  directory `AGENTS.md` is auto-surfaced by the `context-surface` hook.
- Fewer files re-read before the first edit (orientation cost ↓ in
  4 of 5 runs).
- **But sometimes *more* output tokens produced.** Run 4 AFTER
  generated +9.2 % output vs BEFORE, yet the total run still cost
  −9.5 % less.
- **Wall-clock confirms the cost signal.** With idle-pause time
  filtered out (gaps longer than 60 s ignored), AFTER also completes
  the task faster on average - mean active runtime 9.8 min BEFORE
  vs 8.6 min AFTER (−12.1 %). The time saving is smaller than the
  cost saving (−26.6 %) because part of the orientation budget gets
  reinvested into richer output, not pocketed.

That "more output" is the **maintainability dividend**. Across all 5
AFTER runs, the agent:

- Caught a documented load-bearing AIDEV-NOTE trap (a database-driver
  gotcha where the most natural parameter naming would silently produce
  wrong query results in production). The BEFORE agent caught it in
  **0 / 5** runs.
- Used the per-domain `routers/` split instead of dumping the new
  endpoint into the monolithic API file.
- Used the LRU-cached SQL loader instead of the legacy direct-read form.
- In one run, additionally updated the API documentation file per the
  PR recipe documented in the per-directory `AGENTS.md` - a step the
  BEFORE agent had no way of knowing about.

The BEFORE agent's code worked. But it worked in the *old style* - no
awareness of the conventions the rest of the codebase has since adopted.
The next engineer (human or AI) opening that PR pays the cost later, in
rework. That cost does not show up in the benchmark; it shows up six
months later as drift.

**Net effect: fewer tokens spent, and the tokens that are spent go into
code that doesn't have to be rewritten later.**

<details>
<summary>Caveats (please read before extrapolating)</summary>

- Single codebase, single task type, five Opus runs. Plus one Sonnet
  run on a different task. This is a *first signal*, not a proof.
- Cost variance is high (std ≈ $4 per arm; delta std ≈ 20 percentage
  points). The qualitative signal (5 / 5 trap-catch, consistent
  convention adherence) is more reliable than the cost delta itself.
- Two runs were invalidated due to network instability during the
  benchmark and excluded from the table above.
- Numbers should not be extrapolated to "X % cost savings on your
  codebase". They should be read as: "claude-leverage measurably
  changes the agent's behavior toward documented repo conventions,
  and at least sometimes saves money doing it."

Methodology, dropped-run notes, and reproducer:
[`bench/eval/`](bench/eval/).

</details>

### Spot-check: plugin v1.11.0 on Claude Opus 4.8 (n=1, expanding)

A newer, separate data point on the **current** plugin line and model — the
headline chart above stays a clean Claude Opus 4.7 / n=5 set; this one is not
folded into it. Same anonymised codebase, same endpoint-implementation task,
Pure A/B (plugin OFF in BEFORE, ON in AFTER).

![A/B spot-check, Opus 4.8 + plugin v1.11.0](bench/eval/results-current.png)

| Metric | BEFORE | AFTER | Δ |
|---|---:|---:|---:|
| Run cost | $33.15 | $17.45 | **−47.4 %** |
| Total tokens | 10.02 M | 4.64 M | −53.7 % |
| Files read before first edit | 19 | 8 | −57.9 % |
| Grep + Glob calls (orientation flailing) | 11 | 0 | −100 % |

Both arms completed the task correctly. AFTER reached the same result with
roughly half the orientation reading and zero grep/glob flailing — it went
straight to the per-directory `AGENTS.md` and SQL docs instead of searching
around. The documented parameter-naming gotcha bit neither arm this run: AFTER
avoided it knowingly (and documented the reason inline for the next agent),
BEFORE avoided it incidentally by following a local formatting convention — so
no "trap-catch" win to claim here, just the cheaper-and-self-documenting path.

This is a single run and **less clean than the headline set**: part of BEFORE's
higher cost is unrelated extra work the agent chose to do (it fixed a
pre-existing cross-platform bug along the way), not pure orientation waste. The
chart is built to grow — more Opus 4.8 / v1.11.0 runs append to it. Treat it as
a first signal on the current line, not a result.

## How it compares

claude-leverage and `superpowers` solve **different** problems - one is a
guardrail + convention + memory layer, the other is a set of process-discipline
skills. They're complementary; the table is a positioning aid, not a scoreboard.

| Capability | claude-leverage | superpowers | vanilla CC / Codex |
|---|:---:|:---:|:---:|
| Deterministic security hooks (secrets, dangerous git) | ✅ | - | - |
| Cross-tool: one source for Claude Code **and** Codex | ✅ | Claude only | - |
| AIDEV anchor + structured-logging conventions | ✅ | - | - |
| Durable memory (ADRs, session logs) | ✅ | - | - |
| Self-maintenance nudges (stale anchors, missing AGENTS.md) | ✅ | - | - |
| Process-discipline skills (TDD, brainstorming, debugging) | - | ✅ | - |

*They solve different problems - run both together.*

## What's inside

| Directory | Purpose |
|-----------|---------|
| [`agents/`](agents/) | Claude Code subagents (Markdown + YAML frontmatter) |
| [`.codex/agents/`](.codex/agents/) | Codex subagents (TOML; auto-generated from `agents/`) |
| [`skills/`](skills/) | 15 cross-tool skills (`agentskills.io` SKILL.md spec) - adds `/refresh-context-map` in v1.8.0 |
| [`commands/`](commands/) | 1 Claude Code slash command (`/flaky-test`) |
| [`hooks/hooks.json`](hooks/hooks.json) | Claude Code hook config (paths point at `scripts/hooks/`) |
| [`.codex/`](.codex/) | Codex hook template + sandbox/approval defaults |
| [`scripts/hooks/`](scripts/hooks/) | Hook shell scripts, shared by both tools |
| [`scripts/`](scripts/) | Installers, generators, version checks, `smoke-plugin.sh`, and `score_adherence.py` (deterministic naming/casing/structure scorer; `--repo` / `--diff`) |
| [`statusline/`](statusline/) | Portable statusline script + screenshot |
| [`assets/`](assets/) | README banner + static image assets |
| [`claude-md-snippets/`](claude-md-snippets/) | Opt-in CLAUDE.md / AGENTS.md routing rules (2 ship by default; installable via `/init-repo`) |
| [`templates/`](templates/) | Per-language AGENTS.md example + structured-logging starter kits (4 languages) |
| [`conventions.yml`](conventions.yml) | Per-repo conventions profile (naming casing, vague-name denylist, dir roles, house rules) - surfaced to agents pre-edit by the `context-surface` hook |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records (numbered, immutable; 4 seed ADRs + template) |
| [`docs/sessions/`](docs/sessions/) | Distilled session logs (template + 1 demo log) |
| [`docs/specs/`](docs/specs/) | Design specs (the v1.0 pivot package + research) |
| [`workflows/`](workflows/) | End-to-end prose guides combining skills/hooks/conventions |
| [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/) | Frozen evidence of the v0.x experiment that motivated the v1.0 pivot |

## Why one repo for two tools

Per the [research](docs/specs/research/research_dual_codex_claude.md):
`AGENTS.md` is the open spec both tools converge on. Claude Code reads
`CLAUDE.md` natively but its `@<path>` import lets `CLAUDE.md` be a one-line
redirect to `AGENTS.md`. Hook event vocabularies match between the two tools
(`PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`), so the same shell
scripts work for both - only the trigger config differs. Subagents must be
authored twice (MD+YAML for Claude, TOML for Codex), but `scripts/gen-codex-agents.py`
keeps them in sync and CI fails on drift.

The full design rationale is in
[`docs/adr/0002-agents-md-canonical-claude-md-import.md`](docs/adr/0002-agents-md-canonical-claude-md-import.md).

## Honest history

This repo began as a v0.x experiment in routing work across Sonnet/Haiku
subagents to save tokens. Opus 4.7's prompt caching inverted the economics -
inline "read large, emit small" became cheaper than per-invocation dispatch - so
the token-savings thesis stopped paying for itself, and v1.0.0 pivoted to what
the data still supports: deterministic security hooks, on-demand skills, and
self-maintaining conventions.

Full data + rationale: [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/),
[`docs/adr/0001-pivot-from-token-savings-to-dev-stack.md`](docs/adr/0001-pivot-from-token-savings-to-dev-stack.md).

## Verify, update, uninstall

<details>
<summary>Verifying an install works</summary>

Before pushing changes to the plugin, run the bundled smoke check:

```bash
bash scripts/smoke-plugin.sh
```

It runs every pre-push gate in one shot: pytest, version sync, codex agent
parity, shellcheck (if installed), every hook script with empty stdin, plus
an end-to-end install-codex run against a scratch directory. Green exit
means safe to push; red exit prints which gate failed.

If you're a user installing the plugin (not modifying it), the equivalent
verification is:

```
/plugin install claude-leverage@filip-podstavec
/skill list                # confirm 15 skills appear
/agents                    # confirm security-reviewer + flaky-test-isolator
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > /tmp/test.txt && git add /tmp/test.txt
# Ask the agent to commit /tmp/test.txt - block-secrets-precommit should refuse.
```

</details>

<details>
<summary>Update / uninstall</summary>

**Claude Code:**

```
/plugin marketplace update
/plugin update claude-leverage
/plugin uninstall claude-leverage@filip-podstavec
```

**Codex (uninstall):**

```bash
# Linux / macOS / WSL2
rm -rf ~/.agents/skills/claude-leverage
rm    ~/.codex/agents/security-reviewer.toml ~/.codex/agents/flaky-test-isolator.toml
# restore original ~/.codex/hooks.json (the installer leaves a .bak)
mv ~/.codex/hooks.json.pre-claude-leverage.bak ~/.codex/hooks.json 2>/dev/null \
   || rm ~/.codex/hooks.json
# Edit ~/.codex/AGENTS.md and delete the block between the two
# "# claude-leverage:" markers.
```

PowerShell variant:

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.agents\skills\claude-leverage
Remove-Item -Force $env:USERPROFILE\.codex\agents\security-reviewer.toml,$env:USERPROFILE\.codex\agents\flaky-test-isolator.toml
$bak = "$env:USERPROFILE\.codex\hooks.json.pre-claude-leverage.bak"
if (Test-Path $bak) { Move-Item -Force $bak "$env:USERPROFILE\.codex\hooks.json" }
else { Remove-Item -Force "$env:USERPROFILE\.codex\hooks.json" }
# Then edit ~/.codex/AGENTS.md and remove the marker block.
```

</details>

## License

[MIT](LICENSE) - see also [CONTRIBUTING.md](CONTRIBUTING.md).
