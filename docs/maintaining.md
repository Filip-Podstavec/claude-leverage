# Maintaining this repo

Procedures for keeping the stack's artifacts in sync. The always-on summary is in
[`AGENTS.md`](../AGENTS.md) ("Maintenance"); the step-by-step lives here so the
root instruction file stays lean (see
[ADR 0009](adr/0009-agents-md-lean-budget-and-size-tiers.md)).

## README / per-dir docs

When you add/remove/rename any agent, command, skill, hook, or top-level dir:

1. Update top-level `README.md` — architecture block, install sections,
   what's-inside table.
2. Update the matching per-dir doc: `agents-docs/README.md`,
   `commands-docs/README.md`, `skills/README.md`, `hooks/README.md`, or
   `claude-md-snippets/README.md`.
3. Re-run `/repo-map` so the README architecture diagram stays current (the block
   has marker comments — re-running only rewrites between them).

## Plugin marketplace

When you change version or hook configuration:

1. Bump `version` in BOTH `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json`. They must match — CI fails on drift via
   `scripts/check_version_sync.py`.
2. Regenerate the Codex plugin artifacts from the Claude source:
   ```bash
   python scripts/gen-codex-plugin.py
   ```
   This rewrites `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
   CI (`codex-plugin-parity`) and `smoke-plugin.sh` fail if they drift. Never
   hand-edit the generated files — change `.claude-plugin/` and regenerate.
3. Hook scripts use `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/...` in `hooks/hooks.json`.
   Never `~` or `$HOME`. Codex sets `CLAUDE_PLUGIN_ROOT` for compatibility, so
   the same file works in both tools.
4. `.codex/hooks.json` is a template using `__CLAUDE_LEVERAGE_DIR__` placeholder.
   `scripts/install-codex.sh` resolves it at install time when writing to
   `~/.codex/hooks.json`.

## Subagent parity (Claude → Codex)

Any subagent in `agents/*.md` MUST have a paired `.codex/agents/*.toml`. After
modifying any agent, run:

```bash
python scripts/gen-codex-agents.py
```

CI fails if generator output drifts from committed TOML.

## Build / test

```bash
pytest tests/ -v                          # plugin integrity + frontmatter tests
python scripts/check_version_sync.py       # plugin.json == marketplace.json
shellcheck scripts/hooks/*.sh              # CI runs this; install locally to match
python scripts/gen-codex-agents.py --check # ensure .codex/agents/*.toml matches agents/
python scripts/gen-codex-plugin.py --check # ensure .codex-plugin/ + .agents/ match Claude manifest
bash scripts/smoke-plugin.sh               # single-shot pre-push: all of the above + install-codex e2e
```

### Pre-push hook (opt-in)

To make `bash scripts/smoke-plugin.sh` run automatically on every `git push`,
enable the in-tree hooks directory:

```bash
git config core.hooksPath .githooks
```

See [`.githooks/README.md`](../.githooks/README.md) for details (disable, bypass,
rationale for opt-in).

## Design specs

Living design docs in [`docs/specs/`](specs/):

- `2026-05-24-pivot/` — the v1.0.0 pivot package (this rewrite)
- `research/` — supporting research for the pivot

The original synthetic-benchmark design lives with the archived harness it
describes, at
`bench/archive-token-savings-thesis/2026-05-21-synthetic-benchmark-design.md`.
