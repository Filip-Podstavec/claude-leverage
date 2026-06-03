# Codex plugin distribution for `claude-leverage`

**Date:** 2026-06-03
**Status:** Approved (design) — ready for implementation plan

## Context

OpenAI Codex recently shipped a plugin system (`/plugins` in Codex CLI, plugin
marketplaces installable from GitHub shorthand, Git URL, SSH URL, or a local
marketplace root). The Codex plugin format is intentionally close to Claude
Code's:

- Plugin manifest at `.codex-plugin/plugin.json` (vs Claude's `.claude-plugin/plugin.json`).
- Marketplace root at `.agents/plugins/marketplace.json`, with **explicit legacy
  support** for `$REPO_ROOT/.claude-plugin/marketplace.json`.
- Skills as `skills/<name>/SKILL.md` — identical to Claude.
- Hooks as `hooks/hooks.json`. Codex passes `PLUGIN_ROOT`/`PLUGIN_DATA` **and
  also sets `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` for compatibility**.
- MCP via `.mcp.json`, apps via `.app.json`.

Sources: <https://developers.openai.com/codex/plugins>,
<https://developers.openai.com/codex/plugins/build>.

This repo already integrates with Codex two ways — Codex reads `AGENTS.md`
natively, and `scripts/gen-codex-agents.py` generates `.codex/agents/*.toml` for
subagent parity. **A Codex plugin marketplace is a third, complementary
distribution path**, not a replacement for either.

### Compatibility audit (current repo vs Codex plugin spec)

| Component | Status for Codex plugin install |
|---|---|
| Hooks (`${CLAUDE_PLUGIN_ROOT}` in `hooks/hooks.json`) | ✅ works — Codex sets `CLAUDE_PLUGIN_ROOT` for compat |
| Skills (`skills/*/SKILL.md`) | ✅ identical format |
| `plugin.json` | ❌ Codex reads **only** `.codex-plugin/plugin.json`; **no** legacy fallback for the manifest → must add |
| `marketplace.json` | ⚠️ legacy `.claude-plugin/marketplace.json` supported, but schema differs (`interface.displayName` not `owner`; per-plugin `policy` + `category` + `source`) |
| `commands/` (1×), `agents/` (2×) | ❌ not loaded by Codex plugin spec — agents already covered by native `.codex/agents/*.toml` |

## Decision

Add a Codex plugin distribution path via **generated, tool-native artifacts**
kept in sync from the existing Claude manifest, plus README/ADR/maintaining
documentation.

### 1. Source of truth & generated artifacts

`.claude-plugin/plugin.json` remains the **single source of truth** for
version/metadata. A new generator derives the Codex artifacts from it:

```
.claude-plugin/        ← source of truth (Claude reads natively)
  plugin.json
  marketplace.json
.codex-plugin/         ← GENERATED (Codex reads; no legacy fallback for manifest)
  plugin.json
.agents/plugins/       ← GENERATED (canonical Codex marketplace path)
  marketplace.json
scripts/gen-codex-plugin.py   ← new; mirrors gen-codex-agents.py, supports --check
```

### 2. `.codex-plugin/plugin.json` (generated)

Minimal — Codex defaults cover the rest (`skills/` → `./skills/`, hooks →
`./hooks/hooks.json`). `name`/`version`/`description` mirror the Claude manifest
1:1. No `interface` block (that is for curated-directory submission only —
YAGNI).

### 3. `.agents/plugins/marketplace.json` (generated)

Codex schema: top-level `name` + `interface.displayName` (replacing Claude's
`owner`). Per-plugin: `source: {source: "url", url: "…claude-leverage.git"}`
(plugin lives at repo root), `policy.installation: AVAILABLE`, `category`.

- **Open detail to confirm during implementation:** `policy.authentication`
  value when there is no app integration. The plugin ships no MCP/apps, so
  expect `NONE` or field omitted — verify via a real test-install in Codex CLI.

### 4. Documented limitation (not worked around)

Codex plugin spec loads only **skills + hooks + mcp + apps**. So `/flaky-test`
(1 command) and the 2 subagents do **not** load via the plugin. This is
acceptable: subagents are already delivered through the native
`.codex/agents/*.toml` path + `AGENTS.md`. README frames the two paths as
complementary, not a regression. We do **not** try to hack commands/agents into
the plugin.

### 5. CI / sync

`gen-codex-plugin.py --check` is added to `scripts/smoke-plugin.sh` next to
`gen-codex-agents.py --check`. Version drift across the three manifests is thus
impossible — all Codex artifacts derive from `.claude-plugin/plugin.json`.

### 6. README

New "Install as a Codex plugin" section: add the marketplace via GitHub
shorthand `Filip-Podstavec/claude-leverage`, then `/plugins` → install. Includes
the explicit limitation from §4 and a pointer to the native `.codex/` path for
agents/commands.

### 7. ADR + maintaining.md

- ADR (via `/adr-new`): "Codex plugin marketplace as a third distribution path"
  — context (Codex shipped plugins; format ≈ Claude Code clone), decision
  (generated tool-native artifacts), alternatives rejected (augmented shared
  `.claude-plugin/marketplace.json`; hand-maintained files + version-sync guard).
- `docs/maintaining.md`: add a step — "when you change version/skills/hooks, run
  `gen-codex-plugin.py`" — beside the existing `gen-codex-agents.py` step.

## Alternatives considered (rejected)

- **Augment the shared `.claude-plugin/marketplace.json`** with Codex fields
  (Codex reads it via the legacy path). Fewer files, but mixes two schemas in
  one file and still requires a hand-written `.codex-plugin/plugin.json`.
- **Hand-write both Codex files + extend `check_version_sync.py`** to assert
  version equality. No new generator, but more manual upkeep on every change and
  weaker than generation at preventing structural drift.

Both rejected in favor of generation, which matches the repo's existing
generated-and-`--check`ed-artifact idiom (`gen-codex-agents.py`).

## Out of scope

- Submitting to OpenAI's curated plugin directory (would need the `interface`
  block, assets, policy/ToS URLs).
- Any change to the existing native `.codex/` install path.
- MCP/apps support (the plugin ships none).

## Open questions

1. `policy.authentication` enum value for an app-less plugin — confirm via
   test-install (§3).
2. Branch: this work is unrelated to the current `feat/adherence-scorer` branch;
   implementation should start on a fresh branch off `main`.
