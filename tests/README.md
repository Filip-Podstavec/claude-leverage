# tests

Pytest suite for plugin internals. Run locally with:

```bash
pytest tests/ -v
```

CI runs this on every PR and push to main (see `.github/workflows/ci.yml`).
For a single-shot pre-push check that bundles this with the other gates,
run `bash scripts/smoke-plugin.sh`.

## Coverage

- `test_plugin_integrity.py` — end-to-end validation that the shipped
  plugin manifest is internally consistent. Catches "plugin install
  silently broke" before push. Covers:
  - `plugin.json` + `marketplace.json` shape, version parity, and the
    name/owner conventions Claude Code's plugin loader expects.
  - Every hook script referenced in `hooks/hooks.json` resolves under
    `${CLAUDE_PLUGIN_ROOT}` (no `~` or absolute paths) and exists on disk.
  - Every skill in `skills/*/SKILL.md` has the agentskills.io frontmatter
    (`name`, `description`, optional `allowed-tools`).
  - Every Claude Code subagent in `agents/*.md` has a paired
    `.codex/agents/*.toml` (parity check; the generator drift check itself
    lives in `scripts/gen-codex-agents.py --check`).
  - `stack.toml` parses, declares `manifest_version`, and every
    `[[host.tool]]` / `[[deps.tool]]` entry has the required fields.

- `test_agent_command_frontmatter.py` — structural validation of every
  agent and command file shipped at the top level: frontmatter shape,
  required fields, filename/name parity, no duplicate names. Exists
  because Claude Code's plugin loader registers every `*.md` under
  `agents/` and `commands/` as a phantom — strict frontmatter discipline
  is what stops malformed files from breaking the whole plugin load.
