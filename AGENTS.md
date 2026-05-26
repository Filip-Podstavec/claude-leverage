# AGENTS.md

Canonical instruction set for any coding agent working in this repo. **Read this
first**, before touching any file.

- **Claude Code** loads this via the `@AGENTS.md` import in `CLAUDE.md`.
- **Codex CLI** reads `AGENTS.md` natively (no import needed).

Both tools see identical guidance. Tool-specific additions live in `CLAUDE.md`
(below the `@AGENTS.md` import) — keep them short.

## Mission

`claude-leverage` is Filip Podstavec's personal **AI-dev stack for Claude Code
and Codex**, built to help him ship **secure and long-term-maintainable software
for clients** when working primarily through AI agents.

The premise: shipping client work with AI agents at velocity is easy; shipping it
in a way that the *next* agent (human or AI) opening the repo in six months can
still safely modify is the hard part. This stack is the set of deterministic
guardrails, code conventions, and on-demand skills that make the second part
automatic — not just at session start, but **continuously as the repo grows**.

Three properties guide every decision in this repo:

1. **Security by default** — deterministic shell hooks block secrets, dangerous
   git operations, and force-push before the model can rationalize past them.
2. **Self-maintaining as the repo grows** — non-blocking nudges flag missing
   AIDEV-NOTE anchors, missing per-directory AGENTS.md, stale anchors with
   deadlines, and security-review-worthy diffs — so maintenance debt surfaces
   while it's still cheap to fix.
3. **Cross-tool by design** — the same `AGENTS.md`, same `SKILL.md` files, and
   same hook scripts work in both Claude Code and Codex. Authoring once.

The point is **not** to save tokens (that thesis was disproven by the v0.x
benchmark series — see `bench/archive-token-savings-thesis/` and
`docs/specs/2026-05-24-pivot/`). The point is to make the *next* agent's
job easier than the *previous* one's, every time, automatically.

## What's in it

Concretely:
- 7 hooks (security guardrails + maintenance nudges, all non-blocking unless
  blocking a real safety issue)
- 13 cross-tool skills (`/security-review`, `/repo-map`, `/process-diagram`,
  `/stack-check`, `/init-repo`, `/log-structured`, `/explain-diff`,
  `/codex-sandbox`, `/adr-new`, `/session-log`, `/glossary-init`,
  `/arch-map`, `/repo-doctor`)
- 1 Claude-only slash command (`/flaky-test`)
- 2 subagents (`security-reviewer`, `flaky-test-isolator`)
- 1 portable statusline
- Per-language AGENTS.md template + 4 structured-logging starter kits
- `docs/adr/` and `docs/sessions/` conventions with templates and bootstrap
  skills (the durable-memory + per-session-continuity layers)
- Workflow guides showing how to combine all of the above for common tasks
  (`workflows/`)

Installed:
- **In Claude Code** as a plugin (`/plugin install claude-leverage@filip-podstavec`).
- **In Codex** via `bash scripts/install-codex.sh` (or `.ps1` on Windows) — Codex
  has no plugin marketplace.

Distinct from the official `obra/superpowers-marketplace` plugin (the well-known
`superpowers` Claude Code plugin); this stack is **complementary** to it, not a
replacement. Plugin description deliberately avoids the `superpowers` keyword.

## Reading order for new agents

If you're an agent opening this repo for the first time, read in this
order (progressive disclosure: minimum context at session start):

1. **This file** (`AGENTS.md`) — what this repo is and how to work in it.
2. [`docs/adr/`](docs/adr/) — *why* the architecture looks the way it
   does. Skim the index; read the ones relevant to what you're about to
   change. Without these, you'll propose refactors away from
   load-bearing constraints.
3. [`docs/sessions/`](docs/sessions/) — the last 1–3 session logs.
   Where the previous human + agent left off. Often the highest-leverage
   orientation per token.
4. Specific [`docs/specs/`](docs/specs/) only when starting on that
   topic.
5. The code itself — by following imports from the relevant entrypoint
   (see "Repo layout" below).

## Repo layout

```
agents/                       Claude Code subagents (Markdown + YAML frontmatter)
.codex/agents/                Codex subagents (TOML; generated from agents/)
skills/                       Cross-tool skills (SKILL.md, agentskills.io spec)
commands/                     Claude Code slash commands
hooks/hooks.json              Claude Code hook config — paths point at scripts/hooks/
.codex/hooks.json             Codex hook config (template; install-codex resolves paths)
.codex/config.toml            Codex sandbox/approval policy
scripts/hooks/                Hook shell scripts, shared by both tools
scripts/                      Installers, generators, version checks, smoke-plugin.sh
statusline/                   Portable statusline script
claude-md-snippets/           Opt-in CLAUDE.md / AGENTS.md routing rules (installable via /init-repo)
templates/                    Per-repo AGENTS.md examples + structured-logging starter kits
agents-docs/, commands-docs/  Per-dir docs that can't live inside agents/ or
                              commands/ because Claude Code's plugin loader
                              registers every *.md as a phantom — see
                              tests/test_agent_command_frontmatter.py
docs/adr/                     Architecture Decision Records (numbered, immutable; /adr-new bootstraps)
docs/sessions/                Distilled session logs (/session-log writes one at end of session)
docs/specs/                   Design specs (current and historical)
workflows/                    End-to-end prose guides combining skills/hooks/conventions
bench/archive-token-savings-thesis/
                              Frozen evidence of the v0.x token-savings experiment
                              that motivated the v1.0 pivot. Don't delete.
```

## Maintenance rules

### README / per-dir docs

When you add/remove/rename any agent, command, skill, hook, or top-level dir:

1. Update top-level `README.md` — architecture block, install sections, what's-inside table.
2. Update the matching per-dir doc: `agents-docs/README.md`, `commands-docs/README.md`,
   `skills/README.md`, `hooks/README.md`, or `claude-md-snippets/README.md`.
3. Re-run `/repo-map` so the README architecture diagram stays current (the
   block has marker comments — re-running only rewrites between them).

### Plugin marketplace

When you change version or hook configuration:

1. Bump `version` in BOTH `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
   They must match — CI fails on drift via `scripts/check_version_sync.py`.
2. Hook scripts use `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/...` in `hooks/hooks.json`.
   Never `~` or `$HOME`.
3. `.codex/hooks.json` is a template using `__CLAUDE_LEVERAGE_DIR__` placeholder.
   `scripts/install-codex.sh` resolves it at install time when writing to
   `~/.codex/hooks.json`.

### Subagent parity (Claude → Codex)

Any subagent in `agents/*.md` MUST have a paired `.codex/agents/*.toml`. After
modifying any agent, run:

```bash
python scripts/gen-codex-agents.py
```

CI fails if generator output drifts from committed TOML.

## Code conventions

These apply to code you ship in this repo AND are the conventions this stack
documents for other repos (via `templates/AGENTS.md.example` once it lands).

### AIDEV-* anchor comments

Three grep-able prefixes for load-bearing facts in code:

- `AIDEV-NOTE:` — why this constraint exists / non-obvious invariant
- `AIDEV-TODO:` — known follow-up with enough context to resume
- `AIDEV-QUESTION:` — genuine unknown for the next person (or agent)

Rules: ≤120 chars per line, all-caps prefix. **Before editing a module, run
`grep -rn 'AIDEV-' <module>` first.** Do not silently remove anchors — removing
one requires an explicit decision in the commit/PR message.

Add anchors at non-obvious decision points (regulatory carve-outs, performance
workarounds, ordering dependencies, idempotency tricks). Do NOT decorate every
function — that's clutter. The PostToolUse `ai-first-nudge` hook prints a
non-blocking suggestion when ≥50 net-new LOC ship without any anchor.

**Deadlines (optional).** `AIDEV-TODO` and `AIDEV-QUESTION` accept an
optional ISO-8601 deadline:

```python
# AIDEV-TODO(by: 2026-08-01): replace the polling loop with webhooks
# AIDEV-QUESTION(by: 2026-07-15): is the encoding always UTF-8 here?
```

`/stack-check`'s anchor walk parses the date and reports overdue items
separately from age-based "stale" items, so deadlines have actual teeth.
Without a deadline, the same anchor falls under the age-based check
(fresh / aging / stale at 30 / 90 days).

### Structured JSON-lines logging

For application code that emits logs an agent will later need to read:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3","span_id":"4d5e6f","service":"billing","event":"invoice_paid","attrs":{"invoice_id":"inv_789","amount_cents":4900}}
```

Required fields: `ts` (ISO-8601 UTC), `level`, `trace_id`, `span_id`, `service`,
`event` (snake_case), `attrs` (typed object).

**Do not interpolate values into messages.** Put `user_id` in `attrs.user_id`,
not in the `message` string. Propagate `trace_id` across process/HTTP/queue
boundaries (W3C traceparent header).

### Per-directory AGENTS.md for non-trivial modules

When a module has non-obvious public surface or gotchas, add an `AGENTS.md` at
its root. Codex merges nested AGENTS.md files from git root down to cwd
automatically; Claude Code picks them up when an agent Reads the file. Use
`/init-repo` to drop one into a fresh project, or copy
[`templates/AGENTS.md.example`](templates/AGENTS.md.example) directly.

### When to invoke `/adr-new` and `/session-log`

These two skills are the durable-memory layer (see
[ADR 0004](docs/adr/0004-adr-and-session-log-are-user-invoked-no-auto-fire-hook.md)
for why they don't auto-fire). They are **user/agent-invoked**, not hooked
to a lifecycle event. **The agent working in this repo is expected to
recognize the moment** and invoke. Specifically:

- **`/adr-new`** — invoke when a load-bearing architectural decision is
  being made or has just been made in conversation. "Load-bearing" means:
  someone is likely to propose reverting it in six months ("why didn't we
  use X?") without seeing the rationale. Examples that warrant an ADR:
  choosing a database / framework / integration pattern / auth model, OR
  explicit rejection of an alternative. Three sentences in
  `docs/adr/NNNN.md` is cheaper than re-arguing later.

- **`/session-log`** — invoke at the END of a substantial working session
  (commits shipped, multiple non-trivial decisions made, or open
  questions surfaced worth preserving). Signals to watch for: user says
  "thanks, that's it for today" / "tomorrow" / "wrap this up"; OR
  session shipped 3+ commits with no session log yet today; OR user
  asks for a summary / handoff / status. Distillate, NOT transcript.

Both skills' descriptions follow a `USE WHEN ... / Do NOT use for ...`
pattern so the Claude Code skill resolver surfaces them when the
conversation matches the trigger. But the agent **must still recognize
the moment** — neither skill is fired by a hook. If you forget, the
plugin won't remind you (per ADR 0004).

### Module organization

- Co-locate tests with code (`foo.py` next to `foo_test.py`)
- One concept per module, thin entrypoint exporting the public surface
- Predictable file layout, documented here in AGENTS.md
- Reference canonical examples by path ("see `agents/flaky-test-isolator.md`
  for the read-only-subagent pattern") rather than restating conventions

## Security guardrails

These hooks run on every Bash tool call regardless of which agent invoked them:

- `block-secrets-precommit` — scans staged diff for API keys/tokens/private
  keys; blocks `git commit` if found. Per-line allowlist via the
  `claude-leverage-allow-secret` marker comment.
- `block-dangerous-git` — blocks force push, `--no-verify`, hard reset on
  protected branches (`main`/`master`).

**Never bypass these hooks.** If a legitimate need arises (e.g., a test fixture
containing a fake-looking token), use the per-line allowlist marker, not
`--no-verify`.

After significant net-new code in security-sensitive paths (auth, crypto,
routes, payment, templates), run `/security-review` before committing. The
`security-nudge` Stop hook will suggest this automatically when the diff
crosses the threshold.

## Commands available in this stack

| Command | What it does |
|---------|--------------|
| `/security-review` | Audit current diff for OWASP-Top-10-shaped issues |
| `/repo-map` | Generate/update mermaid architecture block in README between markers |
| `/process-diagram <name>` | Generate sequence/flowchart for a named workflow |
| `/stack-check` | Verify Claude Code, Codex, plugin, and CLI deps vs `stack.toml`; also flags stale AIDEV-TODO/QUESTION anchors and AGENTS.md sanity |
| `/init-repo` | Bootstrap a new repo with AGENTS.md + .gitignore patterns + optional structured-logging template |
| `/log-structured` | Find non-structured logging in a codebase and suggest spec-compliant replacements |
| `/explain-diff` | Plain-English 3–5 bullet narration of the current diff |
| `/codex-sandbox` | Interactive helper for `.codex/config.toml` sandbox + approval modes |
| `/adr-new` | Bootstrap a new numbered Architecture Decision Record in `docs/adr/` |
| `/session-log` | Write a distilled session log to `docs/sessions/` at end of session |
| `/glossary-init` | Bootstrap/extend `GLOSSARY.md` at repo root — domain terms specific to this repo, surfaced by identifier frequency, defined by the user |
| `/arch-map` | Bootstrap/refresh `architecture.yml` at repo root — machine-readable module metadata (role/stability/public_surface/...); has `--validate` mode for CI |
| `/repo-doctor` | Read-only AI-readiness audit — scores ~20 dimensions across Foundation / Why / What / In-code / Hygiene / Sync (code↔docs drift). Per-gap concrete fix action; `--score` / `--json` / `--fail-on` / `--scope` for CI |
| `/flaky-test` | Run a single test N times, group failures by signature |

## Build / test

```bash
pytest tests/ -v                          # plugin integrity + frontmatter tests
python scripts/check_version_sync.py       # plugin.json == marketplace.json
shellcheck scripts/hooks/*.sh              # CI runs this; install locally to match
python scripts/gen-codex-agents.py --check # ensure .codex/agents/*.toml matches agents/
bash scripts/smoke-plugin.sh               # single-shot pre-push: all of the above + install-codex e2e
```

### Pre-push hook (opt-in)

To make `bash scripts/smoke-plugin.sh` run automatically on every `git
push`, enable the in-tree hooks directory:

```bash
git config core.hooksPath .githooks
```

See [`.githooks/README.md`](.githooks/README.md) for details (disable,
bypass, rationale for opt-in).

## Design specs

Living design docs in `docs/specs/`:

- `2026-05-24-pivot/` — the v1.0.0 pivot package (this rewrite)
- `research/` — supporting research for the pivot

The original synthetic-benchmark design lives with the archived harness it
describes, at `bench/archive-token-savings-thesis/2026-05-21-synthetic-benchmark-design.md`.

## Honest history

This repo started as `claude-leverage` v0.x — a hypothesis that routing work
across Sonnet/Haiku via subagents would save tokens vs vanilla Claude Code.
Three rounds of benchmarking on Opus 4.7 disproved it: the plugin's per-session
load tax + per-invocation dispatch overhead consistently exceeded the per-token
savings from delegating execution to cheaper tiers.

The raw evidence is in `bench/archive-token-savings-thesis/`. v1.0.0 pivots to
what the data still supports: deterministic security hooks (no model needed),
inline workflow commands (no dispatch tax), and skills loaded on demand (no
per-session payload tax). The honest pivot is part of the story.
