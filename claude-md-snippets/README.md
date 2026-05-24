# CLAUDE.md / AGENTS.md Snippets

Optional fragments meant to be appended to a project's `AGENTS.md` (or
`CLAUDE.md`, or `~/.claude/CLAUDE.md`) to add routing rules or
behavioral guidance that pair with specific skills or subagents from
this stack.

`/init-repo` is the installer: it offers to add selected snippets to a
project's `AGENTS.md` between marker comments, idempotently.

## Available snippets

- [`security-review-routing.md`](security-review-routing.md) — Promotes
  `/security-review` from "the Stop hook might suggest it" to "the
  project mandates it before commit" on diffs touching sensitive paths
  (auth, crypto, payment, templates, etc.). Pairs with the
  `security-nudge` Stop hook and the `security-reviewer` subagent.

(More snippets land here as patterns emerge from actual use.
Convention: one routing rule per snippet, with marker comments so
`/init-repo` can install / update / detect drift.)

## Snippet contract

Every snippet uses the same idempotent-marker pattern:

```markdown
<!-- claude-leverage:<snippet-name> START -->
<body>
<!-- claude-leverage:<snippet-name> END -->
```

The markers are the only contract between the snippet source and the
target file. `/init-repo`'s snippet installer:

- Appends a new block on first install
- Replaces the body between markers on update (drift detected)
- Skips silently if body matches source exactly
- Refuses to touch anything outside the marker block

Markers must stay byte-identical between source and installed copy.

## Why snippets are opt-in

Claude Code plugins install agents, commands, hooks, and skills — but
**not** CLAUDE.md / AGENTS.md content. There's no platform hook to
auto-append guidance to a user's `CLAUDE.md` on plugin install. The
snippet pattern works around this by treating snippet installation as
an explicit user choice per project, gated through `/init-repo`.

The historical alternative was `/install-snippets` (removed in
v1.1.0). That command did the same job but as a separate skill;
folding it into `/init-repo`'s interactive flow gave one less command
to remember.
