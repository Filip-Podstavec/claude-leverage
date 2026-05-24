# Workflows

End-to-end prose guides showing how the agents, skills, hooks, and
conventions in this stack combine for specific scenarios. Unlike the
atomic building blocks in [`agents/`](../agents/),
[`skills/`](../skills/), and [`commands/`](../commands/), workflows
describe how to **wire them together** for real tasks.

## Available workflows

- [**`security-first-feature.md`**](security-first-feature.md) — Shipping
  a new auth / payment / template / route safely with the stack. The
  three explicit skill invocations (`/init-repo` once,
  `/security-review` before commit, `/commit-smart` to ship) plus what
  fires passively (hooks, nudges) at each step.

- [**`maintaining-as-it-grows.md`**](maintaining-as-it-grows.md) — The
  mental model: what the stack maintains automatically (hooks, nudges,
  periodic checks) vs what you must invoke explicitly. Includes
  per-nudge tunables and the maintenance-debt cycle diagram showing
  how AIDEV anchors → deadline tracking → stack-check → resolved-debt
  closes the loop.

## Adding a workflow

Plain markdown, no frontmatter required. Aim for:

- One concrete scenario per file (not "general advice").
- Walks the user through what they do and what the stack does for them.
- Names specific skills / hooks / files; links to them in the repo.
- Documents what the workflow does NOT cover (so the user knows when
  to reach for a different tool or another plugin like superpowers).
