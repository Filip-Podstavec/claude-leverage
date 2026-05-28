# README redesign — design spec

**Date:** 2026-05-28
**Status:** implemented (2026-05-28)
**Topic:** Make `README.md` modern, scannable, and credible — so a stranger
understands *why* claude-leverage exists and *how to start*, especially on a
legacy repo.

## Motivation

The current `README.md` is information-rich but visually flat: no hero, no table
of contents, a wall-of-bullets "What you get" section, no onboarding path, and
no tool-compatibility cues. A first-time reader cannot tell within one screen
what this is, who it's for, or where to begin.

The reference repo [`withkynam/vibecode-pro-max-kit`](https://github.com/withkynam/vibecode-pro-max-kit)
sells far better through: a centered hero, a clickable tool-logo row, a TOC,
problem→solution grids, collapsible progressive disclosure, and an explicit
getting-started narrative.

**This redesign borrows the reference's *structure and polish* but rejects its
*hype tone*.** The reference leans on anime GIFs, fabricated-sounding
testimonials, and a comparison table that "beats" competitors (including
`superpowers`). claude-leverage's entire credibility hook is the opposite — the
"Honest history" section that admits its original token-savings thesis was
disproven, and the stated positioning that it *complements* `superpowers`
rather than replacing it. Copying the hype would betray that ethos.

## Goals

- Modern, scannable README that communicates the *why* above the fold.
- Explicit onboarding, with the **legacy-repo path via `/repo-doctor`**
  emphasized.
- An AI-tool logo row with links — honest about what is first-class vs.
  portable.
- **Preserve all existing content** — move exhaustive detail behind `<details>`
  rather than deleting it.
- **Preserve all regeneration markers** (`<!-- repo-map:* -->`,
  `<!-- process-diagram:* -->`) so `/repo-map` and `/process-diagram` still work.
- Fix the version-badge drift (`1.7.0` → `1.8.3`).
- Add a committed SVG wordmark banner.

## Non-goals

- No fabricated testimonials, anime GIFs, or hype superlatives.
- No overclaiming multi-tool support (see honest-framing decision #1).
- No competitive "we beat them" comparison table.
- Do **not** remove or shrink the "Honest history" section — it stays prominent.
- No content deletion; only reorganization + progressive disclosure.

## Honest-framing decisions (load-bearing)

These three constraints are the reason the "polished but honest" tone holds
together. They are deliberate and should not be quietly relaxed during
implementation.

1. **Tool-compatibility row is honest about tiers.** Exactly two tools are
   first-class: **Claude Code** (plugin) and **Codex CLI** (installer) — the
   hooks, skills, and subagents only run there. The `AGENTS.md` convention layer
   is portable to any AGENTS.md-aware tool. So the hero shows **two
   `for-the-badge` logo badges** (Claude Code, Codex CLI), each linking to the
   respective docs, followed by a smaller secondary line: *"Convention layer
   (`AGENTS.md`) is also read by any AGENTS.md-aware tool — Cursor, Windsurf,
   Copilot…"*. We do **not** render a row of seven logos implying full support.

2. **Positioning table is complementary, not competitive.** It contrasts
   *capability categories*, showing the two tools solve different problems, and
   ends with a "run both together" note. No row is framed as claude-leverage
   "winning."

3. **Benchmark numbers are unchanged.** Only the presentation is tightened
   (caveats moved into a `<details>`). The figures, the n=5 caveat, and the
   dropped-run notes stay factual.

## New section structure

Rendered length stays short (hero + grid + quick-start above the fold);
exhaustive detail lives behind collapsibles.

1. **Hero (centered, `<div align="center">`)**
   - SVG banner (`assets/banner.svg`) via `<img>`.
   - One-line tagline: *"Ship fast with AI agents — and leave a repo the next
     agent can still safely change in six months."*
   - **Works-with row:** two `for-the-badge` logo badges — **Claude Code**
     (→ `https://docs.anthropic.com/en/docs/claude-code`) and **Codex CLI**
     (→ `https://developers.openai.com/codex`).
   - Secondary portability line (honest-framing #1).
   - **Badge row:** CI · MIT · `v1.8.3` · `14 skills` · `8 hooks` ·
     `2 subagents`.

2. **One-paragraph pitch** — what it is + "complements `superpowers`, does not
   replace it."

3. **Table of contents** — anchor links to the sections below.

4. **The problem → the fix** — two-column HTML table (`<table>`), no win/lose
   framing:
   - *Context dies between sessions* ↔ *AIDEV anchors + `context-surface` hook
     surface the right facts at edit time.*
   - *Docs drift out of sync with code* ↔ *Self-maintenance nudges flag missing
     AGENTS.md, stale anchors, drift.*
   - *Big tasks collapse / lose the plot* ↔ *Durable memory: ADRs + session
     logs carry intent across sessions.*
   - *No security gate before commit* ↔ *Deterministic hooks block secrets,
     force-push, `--no-verify`.*

5. **Who this is for** — three short personas (HTML grid or list):
   - **Client freelancer** — ships across many client repos via agents; each
     repo must stay safe to hand back.
   - **Team inheriting a legacy repo** — needs to make a 6-month-old, doc-less
     codebase AI-navigable fast.
   - **Solo builder at velocity** — wants speed without the repo rotting into
     unmaintainable AI-slop.

6. **Quick start** — two paths; legacy path emphasized:
   - *New repo:* install → `/init-repo`.
   - *Existing / legacy repo (highlighted):* install → **`/repo-doctor`**
     (read-only AI-readiness audit) → fix the top gaps it reports →
     `/init-repo` · `/arch-map` · `/glossary-init` → `/refresh-context-map`.

7. **Install** — Claude Code (2 lines, prominent) + Codex CLI (script; the
   installer-internals list collapsed into `<details>`). Statusline stays as an
   "Optional" subsection.

8. **What you get** — the current dense bullet list refactored into collapsible
   `<details>` groups, each with a one-line `<summary>` and the existing bullets
   inside: *Always-on safety (hooks)* · *Security review* · *Maintenance skills*
   · *Setup & handoff skills* · *Conventions* · *Cross-tool plumbing*. No content
   removed.

9. **How it works** — the existing workflow sequence diagram and architecture
   flowchart, **with their `<!-- process-diagram:* -->` and `<!-- repo-map:* -->`
   marker comments preserved verbatim** so regeneration still targets them.

10. **Benchmarks** — keep the headline table and "cheaper *and* more
    maintainable" framing; move the "Caveats" block into `<details>`.

11. **Positioning** — fair capability table (honest-framing #2):

    | Capability | claude-leverage | superpowers | vanilla CC / Codex |
    |---|:---:|:---:|:---:|
    | Deterministic security hooks (secrets, dangerous git) | ✅ | — | — |
    | Cross-tool: one source for Claude Code **and** Codex | ✅ | Claude only | — |
    | AIDEV anchor + structured-logging conventions | ✅ | — | — |
    | Durable memory (ADRs, session logs) | ✅ | — | — |
    | Self-maintenance nudges (stale anchors, missing AGENTS.md) | ✅ | — | — |
    | Process-discipline skills (TDD, brainstorming, debugging) | — | ✅ | — |

    Caption: *They solve different problems — run both together.*

12. **What's inside** — the existing directory table, plus a new `assets/` row.

13. **Why one repo for two tools** — kept; optionally wrapped in `<details>`.

14. **Honest history** — kept prominent (credibility anchor), lightly tightened
    at most.

15. **Verify / Update / Uninstall** — collapsed into `<details>`.

16. **License.**

## SVG banner spec

- Path: `assets/banner.svg`, committed; referenced via
  `<img src="assets/banner.svg" alt="claude-leverage" width="640">`.
  (GitHub renders committed SVGs through `<img>` by relative path.)
- Design: a rounded-rectangle dark slate background (`#0f172a`) so it reads on
  both GitHub light and dark themes; monospace wordmark `claude-leverage` in
  light text (`#e2e8f0`) with a violet accent (`#8b5cf6`, matching the existing
  "Claude Code" blueviolet badge); muted subtitle (`#94a3b8`) with the tagline.
- Font: `font-family="ui-monospace, SFMono-Regular, Menlo, monospace"` (SVG
  `<text>`; no external font fetch).
- Dimensions: ~640×160 viewBox, no external assets, no script.

## Files to touch

- `README.md` — full rewrite per the structure above. Preserve marker-block
  *contents* exactly (do not hand-edit between `repo-map` / `process-diagram`
  markers).
- `assets/banner.svg` — new file.
- `README.md` "What's inside" table — add an `assets/` row.

### Maintenance-rule compliance

- Per AGENTS.md "README / per-dir docs": this redesign **adds/removes no** agent,
  command, skill, or hook, so the per-dir docs (`skills/README.md`,
  `hooks/README.md`, etc.) need no content change. It *does* add a top-level
  `assets/` dir → reflected in the "What's inside" table (above). Optionally add
  `assets/` to the AGENTS.md "Repo layout" block.
- `/repo-map` architecture block is preserved between its markers; no re-run
  required unless directory structure changes (adding `assets/` is cosmetic and
  not part of the rendered flowchart).
- No version bump in this change beyond fixing the **badge** to match the
  already-shipped `1.8.3` in `plugin.json` / `marketplace.json`. No
  `plugin.json` change.

## Tone / voice guidelines

- Factual and confident; no superlatives that aren't backed by the benchmark
  data.
- Emoji used sparingly and only where they aid scanning (problem/fix grid,
  personas). Section headings stay plain text. No decorative emoji spam.
- Keep British-vs-US and existing terminology consistent with the current
  README.

## Risks / verification

- **GitHub markdown sanitization:** `<div align>`, `<img>`, `<details>`,
  `<table>`, and shields.io badges all render on GitHub; mermaid renders. Low
  risk. Verify by rendering the README (push to a branch / use a markdown
  preview) before declaring done — do not claim it "looks good" without seeing
  it rendered.
- **Relative links:** all existing relative links (`docs/...`, `workflows/...`,
  `bench/...`, `LICENSE`, `CONTRIBUTING.md`) must survive the rewrite unchanged.
- **Marker integrity:** after the rewrite, confirm `repo-map` and
  `process-diagram` marker pairs are intact (a later `/repo-map` run must still
  find them).
- **Tests:** `pytest tests/` and `python scripts/check_version_sync.py` are
  unaffected (README isn't covered by tests), but run the smoke check before
  pushing per repo convention.

## Acceptance criteria

1. Hero renders with banner + honest two-tool works-with row + corrected
   version badge.
2. A legacy-repo reader can find the `/repo-doctor`-first quick-start path
   immediately.
3. "What you get", benchmark caveats, Codex installer internals, and
   verify/update/uninstall are behind `<details>` — page feels short while
   retaining all content.
4. Positioning table reads as complementary, not competitive.
5. "Honest history" remains prominent.
6. All regeneration markers and relative links intact.
