# extras/ — opt-in components

These components are **not loaded by the default plugin install.** They live here so they can be installed manually by users who want them, without imposing their cost on everyone.

## Why this directory grew in v0.12.0

Through three rounds of benchmarking ([`bench/`](../bench/)) we tested **7 subagent designs** against vanilla Claude Code on the current default model (Opus 4.7):

| Agent | Best result vs baseline | Verdict |
|---|---|---|
| `repo-explorer` (Haiku) | +135 % cost (forced-leveraged) | LOSES |
| `research-agent` (Sonnet) | +73 % cost | LOSES |
| `code-reviewer` (Sonnet) | +193 % cost (forced) | LOSES |
| `test-runner` (Sonnet) | +51 % cost (forced) | LOSES |
| `context-gatherer` (Haiku) | +23 % cost (forced) | LOSES |
| `output-digester` (Haiku) | +76 % cost (forced) | LOSES |
| `impact-mapper` (Haiku) | +66 % cost (forced) | LOSES |
| `docs-updater` (Sonnet) | not isolated, but T4-style work | likely LOSES |
| `flaky-test-isolator` (Sonnet) | not isolated, rare use case | unverified |

The mechanism: vanilla Claude Code already orchestrates Opus + Haiku/Sonnet via built-in `Explore` and `general-purpose` agents that the main session calls for free. Our parallel orchestration layer adds `Task`-tool dispatch overhead on every delegation (each subagent session re-pays cache_creation in a fresh, uncached context) — and the per-token Sonnet/Haiku savings consistently fail to cover that overhead on real workloads.

Prompt caching on Opus 4.7 makes "read large, emit small" cheap inline. A cold dispatch can't beat a warm cache.

**So the default plugin in v0.12.0 ships with zero subagents.** Just the security hooks (`block-secrets-precommit`, `block-dangerous-git`, `track-delegations`), `/commit-smart` (all-inline), and the observability commands. All the agents live here, opt-in.

## What's here

| Component | Use case | Why it's an extra |
|---|---|---|
| `agents/code-reviewer.md` | Structured Critical/Important/Nice findings on a diff | Costs +193 % vs Opus inline review (rigorously isolated audit, N=2) |
| `agents/test-runner.md` | Run tests + return structured failure analysis | Costs +51 % vs Opus reading pytest output inline |
| `agents/context-gatherer.md` | Pre-implementation context (files, types, patterns) | Costs +23 % vs Opus's built-in Explore |
| `agents/git-committer.md` | Sonnet-tier Conventional Commits writer for non-trivial commits | T4 benchmark showed +139 % vs Opus inline commit |
| `agents/git-committer-quick.md` | Haiku-tier writer for tiny commits | Dispatch overhead exceeds Haiku savings on small commits; `/commit-smart` no longer routes here |
| `agents/output-digester.md` | Run a noisy command, return structured digest | Tested with pip-install dry-run; costs +76 % (Opus reads pip output cheaply due to prompt caching) |
| `agents/impact-mapper.md` | "What breaks if I change X?" — structured callsite map | Costs +66 %; CC's Explore handles "find callers" well already |
| `agents/repo-explorer.md` | Pure location lookups ("where is X defined") | Confirmed duplicates CC's built-in `Explore` (also Haiku) |
| `agents/research-agent.md` | Cross-file pattern synthesis | Confirmed duplicates CC's built-in `general-purpose` |
| `agents/docs-updater.md` | README/CHANGELOG freshness vs diff | Low real-world frequency; structurally same shape as code-reviewer (loses) |
| `agents/flaky-test-isolator.md` | Run a test N times, group failures by signature | Specialized; the work is bounded so dispatch overhead likely exceeds savings |
| `commands/code-review.md` | `/code-review` slash command — wraps `code-reviewer` | Requires `code-reviewer` agent |
| `commands/test.md` | `/test` slash command — wraps `test-runner` | Requires `test-runner` agent |
| `commands/gather-context.md` | `/gather-context` — wraps `context-gatherer` | Requires `context-gatherer` agent |
| `commands/docs-sync.md` | `/docs-sync` — wraps `docs-updater` | Requires `docs-updater` agent |
| `commands/flaky-test.md` | `/flaky-test` — wraps `flaky-test-isolator` | Requires `flaky-test-isolator` agent |
| `claude-md-snippets/*-routing.md` | Auto-routing reminders that pair with the agents | Paired with their respective extras agents |

## When to opt in

The agents can still be useful when:

1. **You're rate-limited on Opus.** `git-committer-quick` (Haiku) draws from a separate rate pool. Same for `repo-explorer`. If Opus is throttled, an opt-in Haiku agent lets you keep working — at marginal extra cost in tokens, but it's tokens vs nothing.
2. **You want a fixed-schema response for downstream tooling.** `output-digester` returns a parseable digest; that has value for piping into scripts even if it costs more tokens than Opus's prose.
3. **You want enforced structure on outputs.** `code-reviewer` returns Critical/Important/Nice-to-have sections every time; vanilla Opus may give you a prose review of different shape each session. Determinism has its own value.

These are workflow/structure wins, not token-cost wins.

## How to opt in

After installing the main plugin, copy the extras you want into the same scope (user or project):

```bash
# User scope (~/.claude/)
cp extras/agents/code-reviewer.md ~/.claude/agents/
cp extras/commands/code-review.md ~/.claude/commands/

# Project scope (.claude/)
cp extras/agents/code-reviewer.md .claude/agents/
cp extras/commands/code-review.md .claude/commands/
```

Run `/agents` or `/commands` to verify the new entries appear.

## How to opt out

Remove the file. Run `/agents` or `/commands` to confirm it's gone.

```bash
rm ~/.claude/agents/code-reviewer.md ~/.claude/commands/code-review.md
```

## Frontmatter validation

`tests/test_agent_command_frontmatter.py` covers both `agents/` and `extras/agents/` at the same contract, so extras stay structurally valid alongside the default install.
