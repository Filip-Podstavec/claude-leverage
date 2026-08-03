# Agents

Claude Code subagents shipped by `claude-leverage`. Each subagent runs with its
own context window, an explicitly-declared model, and a restricted tool list.
The main session delegates to them via the `Task` tool and receives a
structured result back.

This `agents-docs/` directory exists as a sibling of `agents/` (not inside it)
because Claude Code's plugin loader registers every `*.md` under `agents/` as
an agent — a `README.md` inside `agents/` would become a phantom agent named
`README`. The split is documented in `tests/test_agent_command_frontmatter.py`.

## Install

The plugin install registers these automatically. For manual / standalone:

```bash
# User scope (available in all projects)
mkdir -p ~/.claude/agents
cp agents/*.md ~/.claude/agents/

# Project scope
mkdir -p .claude/agents
cp agents/*.md .claude/agents/
```

Run `/agents` in a running session to pick up changes without restart.

## Codex parity

Each subagent here has a TOML pair under `.codex/agents/` (generated from the
MD frontmatter by `scripts/gen-codex-agents.py`). The MD form is canonical;
re-run the generator after editing any agent. CI fails on drift.

Known limitation: Codex agent TOML has no per-command Bash scoping, so the
generator emits plain `Bash` where the Claude frontmatter says e.g.
`Bash(git log:*)` — in Codex, containment relies on `sandbox_mode =
"read-only"` (OS-level sandbox), not on the tool list. Applies to all three
agents.

## Available agents

- [`security-reviewer.md`](../agents/security-reviewer.md) — Sonnet, read-only.
  Audits the current diff for OWASP-Top-10-shaped issues. Returns deterministic
  Critical / Important / Nice schema. Invoked by `/security-review`.
- [`flaky-test-isolator.md`](../agents/flaky-test-isolator.md) — Sonnet,
  Bash + read-only. Runs ONE test N times, groups failures by normalized
  signature, emits stability report. Invoked by `/flaky-test`. Never modifies
  code; diagnoses, does not fix.
- [`readiness-reviewer.md`](../agents/readiness-reviewer.md) — Sonnet,
  read-only. Judges whether discoverability artifacts (AGENTS.md, README,
  ADRs, GLOSSARY) are truthful, actionable, and mutually consistent (S1–S5).
  Invoked by `/repo-doctor --semantic`. Advisory — never enters the
  deterministic score (ADR 0012).

## Why so few

Eleven other subagents shipped in v0.x. The benchmark series in
[`bench/archive-token-savings-thesis/`](../bench/archive-token-savings-thesis/)
showed all of them costing more than the inline equivalent on Opus 4.7. v1.0.0
keeps only the agents whose value is **not** cost-driven:

- `security-reviewer` — deterministic output schema; isolated context window
  reduces risk of "fixing" findings mid-review.
- `flaky-test-isolator` — statistical signal across N runs that the main
  session cannot cheaply produce.
- `readiness-reviewer` (v1.15.0) — same isolation argument as
  security-reviewer: a separate context window judging docs truthfulness
  can't be tempted to "fix" the docs it is judging mid-review.

The retired agents are frozen in `bench/archive-token-savings-thesis/agents/`.
If a future model-cost shift makes any of them net-positive, resurrect from
there.

## Model strategy

The main session typically runs Opus. Subagents in this stack run Sonnet
(security review, flaky-test analysis, readiness review — all
reasoning-heavy enough that Haiku regresses output quality). Each agent
declares `model:` explicitly in its frontmatter — no implicit inheritance.
