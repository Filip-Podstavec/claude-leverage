---
status: accepted
date: 2026-06-03
deciders: Filip Podstavec
consulted: Claude Opus 4.8 (brainstorming session)
informed: stack users
---

# 0011. Codex plugin marketplace as a third distribution path

## Context and Problem Statement

OpenAI Codex shipped a plugin marketplace (installable from GitHub shorthand, a
Git URL, or a local marketplace root). Its format is close to Claude Code's:
skills as `skills/<name>/SKILL.md`, hooks as `hooks/hooks.json`, a plugin
manifest, and a marketplace root — and Codex even sets `CLAUDE_PLUGIN_ROOT` for
hook compatibility. Until now this repo reached Codex two ways: Codex reads
`AGENTS.md` natively, and `scripts/install-codex.sh` copies skills/hooks/agents
into `~/.codex` + `~/.agents`. The question: should the stack also ship as an
installable Codex plugin, and if so, how do we keep yet another manifest from
drifting?

Two format gaps block a drop-in install: Codex reads the plugin manifest ONLY
from `.codex-plugin/plugin.json` (no legacy fallback), and its marketplace
schema differs from Claude's (`interface.displayName` not `owner`; per-plugin
`policy`).

## Decision

We ship a Codex plugin distribution path via **generated** tool-native
artifacts. `scripts/gen-codex-plugin.py` derives `.codex-plugin/plugin.json` and
`.agents/plugins/marketplace.json` from the Claude manifest pair, which stays
the single source of truth. A `--check` mode runs in CI and `smoke-plugin.sh`.
The plugin path is **complementary** to the install script: it carries skills +
hooks only; subagents, the `/flaky-test` command, and the global `@AGENTS.md`
import remain on the script path.

## Decision Drivers

- The repo already treats Codex parity as a generated-and-`--check`ed artifact
  (`gen-codex-agents.py`); a second generator is the idiomatic fit.
- Three manifests bumped by hand drift silently — exactly the failure
  `check_version_sync.py` exists to stop.
- Codex plugins can't carry slash commands or subagents, so the plugin path
  cannot fully replace the install script; framing them as complementary is
  honest and avoids a regression.

## Considered Options

1. **Generated tool-native artifacts (selected).** New generator emits
   `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` from the
   Claude source, `--check` in CI. Clean schema separation, no drift.
2. **Augment the shared `.claude-plugin/marketplace.json`** with Codex fields
   (Codex reads it via the legacy path). Rejected: mixes two schemas in one
   file and still needs a hand-written `.codex-plugin/plugin.json`.
3. **Hand-write both Codex files + extend `check_version_sync.py`.** Rejected:
   more manual upkeep per change and weaker than generation against structural
   drift.

## Decision Outcome

**Chosen: Option 1.** `.claude-plugin/` is the source of truth; the Codex
artifacts are generated and committed, guarded by `gen-codex-plugin.py --check`
in CI (`codex-plugin-parity` job) and `smoke-plugin.sh` (gate 3b). README
documents the plugin path (option A) alongside the install script (option B),
explicitly noting the skills+hooks-only scope.

### Consequences

**Positive:**
- One source of truth; Codex artifacts can't silently drift from the Claude
  manifest.
- Codex users get a one-command marketplace install for skills + hooks.

**Negative / costs:**
- A third manifest to regenerate (automated; `--check` catches a forgotten
  run).
- `policy.authentication` for an app-less plugin is assumed absent pending a
  real Codex test-install (tracked as an AIDEV-NOTE in the generator).

## Alternatives considered

- See "Considered Options" above (options 2 and 3, both rejected).

## References

- `docs/superpowers/specs/2026-06-03-codex-plugin-distribution-design.md` — the
  design this ADR records.
- <https://developers.openai.com/codex/plugins> and
  <https://developers.openai.com/codex/plugins/build> — the Codex plugin spec.
- [ADR 0002](0002-agents-md-canonical-claude-md-import.md) — AGENTS.md as the
  cross-tool canonical surface (the native Codex path).
