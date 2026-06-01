# Code conventions (full)

The always-on essentials live in [`AGENTS.md`](../AGENTS.md) ("Code
conventions"). This file holds the depth an agent only needs when actually
writing code in a given area — kept here, surfaced on demand, so the root
instruction file stays lean (see
[ADR 0009](adr/0009-agents-md-lean-budget-and-size-tiers.md)).

These conventions apply to code you ship in this repo AND are what the stack
documents for other repos via
[`templates/AGENTS.md.example`](../templates/AGENTS.md.example).

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
assets/                       README banner (banner.svg) + static image assets
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

## AIDEV-* anchor deadlines (optional)

`AIDEV-TODO` and `AIDEV-QUESTION` accept an optional ISO-8601 deadline:

```python
# AIDEV-TODO(by: 2026-08-01): replace the polling loop with webhooks
# AIDEV-QUESTION(by: 2026-07-15): is the encoding always UTF-8 here?
```

`/stack-check`'s anchor walk parses the date and reports overdue items
separately from age-based "stale" items, so deadlines have actual teeth.
Without a deadline, the same anchor falls under the age-based check
(fresh / aging / stale at 30 / 90 days).

## Structured JSON-lines logging

For application code that emits logs an agent will later need to read:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3","span_id":"4d5e6f","service":"billing","event":"invoice_paid","attrs":{"invoice_id":"inv_789","amount_cents":4900}}
```

Required fields: `ts` (ISO-8601 UTC), `level`, `trace_id`, `span_id`, `service`,
`event` (snake_case), `attrs` (typed object).

**Do not interpolate values into messages.** Put `user_id` in `attrs.user_id`,
not in the `message` string. Propagate `trace_id` across process/HTTP/queue
boundaries (W3C traceparent header). Per-language starter kits live in
[`templates/logging/`](../templates/logging/).

## Per-directory AGENTS.md for non-trivial modules

When a module has non-obvious public surface or gotchas, add an `AGENTS.md` at
its root. Codex merges nested AGENTS.md files from git root down to cwd
automatically; Claude Code picks them up when an agent Reads the file. Use
`/init-repo` to drop one into a fresh project, or copy
[`templates/AGENTS.md.example`](../templates/AGENTS.md.example) directly.

## When to invoke `/adr-new` and `/session-log`

These two skills are the durable-memory layer (see
[ADR 0004](adr/0004-adr-and-session-log-are-user-invoked-no-auto-fire-hook.md)
for why they don't auto-fire). They are **user/agent-invoked**, not hooked to a
lifecycle event. **The agent working in this repo is expected to recognize the
moment** and invoke. Specifically:

- **`/adr-new`** — invoke when a load-bearing architectural decision is being
  made or has just been made in conversation. "Load-bearing" means: someone is
  likely to propose reverting it in six months ("why didn't we use X?") without
  seeing the rationale. Examples that warrant an ADR: choosing a database /
  framework / integration pattern / auth model, OR explicit rejection of an
  alternative. Three sentences in `docs/adr/NNNN.md` is cheaper than re-arguing
  later.

- **`/session-log`** — invoke at the END of a substantial working session
  (commits shipped, multiple non-trivial decisions made, or open questions
  surfaced worth preserving). Signals to watch for: user says "thanks, that's it
  for today" / "tomorrow" / "wrap this up"; OR session shipped 3+ commits with
  no session log yet today; OR user asks for a summary / handoff / status.
  Distillate, NOT transcript.

Both skills' descriptions follow a `USE WHEN ... / Do NOT use for ...` pattern so
the Claude Code skill resolver surfaces them when the conversation matches the
trigger. But the agent **must still recognize the moment** — neither skill is
fired by a hook. If you forget, the plugin won't remind you (per ADR 0004).

## Module organization

- Co-locate tests with code (`foo.py` next to `foo_test.py`)
- One concept per module, thin entrypoint exporting the public surface
- Predictable file layout, documented in `AGENTS.md`
- Reference canonical examples by path ("see `agents/flaky-test-isolator.md` for
  the read-only-subagent pattern") rather than restating conventions
