---
name: process-diagram
description: >
  USE WHEN documenting a non-obvious workflow prose explains poorly,
  or when user describes a multi-step process and asks for a
  visualization. Generates a mermaid sequenceDiagram or flowchart,
  optional insertion into target markdown between idempotent markers,
  `mmdc` validation in a 3-retry loop.
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(test:*)
  - Bash(mmdc:*)
argument-hint: "<workflow-name> [--into <path.md>] [--type sequence|flowchart]"
---

# /process-diagram

## What it does

Produces a Mermaid diagram for a named workflow (the flow of
`/security-review`, how a hook intercepts a Bash call, how the
SessionStart `bare-repo-nudge` decision tree resolves, etc.) and
optionally inserts it into a target markdown file between idempotent
markers:

```html
<!-- process-diagram:<name>:start -->
```mermaid
sequenceDiagram
    ...
```
<!-- process-diagram:<name>:end -->
```

## Workflow

1. **Parse arguments.**
   - First positional arg: the workflow name (snake_case). Becomes the
     diagram's identifier in the markers.
   - `--into <path>`: target markdown file to insert into. If omitted,
     just print the diagram to the user.
   - `--type sequence|flowchart`: override the auto-pick. Default rule:
     sequence diagrams for inter-component flows (actors talking to each
     other), flowcharts for decision logic / state transitions.

2. **Resolve the workflow.** Three sources, in order:
   - If a SKILL.md or command file with the workflow's name exists in
     `skills/` or `commands/`, Read it for the participants and steps.
   - If the user describes the workflow in conversation, use that.
   - Otherwise, ask the user for participants and the 3–10 steps. Do not
     hallucinate a flow.

3. **Generate the mermaid.**
   - For `sequenceDiagram`: list participants first (`participant U as User`,
     `participant M as Main session`, …), then the message arrows. Use
     `->>` for sync, `-->>` for response, `Note over` for annotations.
   - For `flowchart`: use `flowchart LR` (or `TB` if the user prefers).
     Wrap labels containing special characters (parens, colons, slashes)
     in double quotes — Mermaid's parser bails on bare ones (per the
     known issue documented in `docs/specs/research/research_visualization.md`).
   - Avoid Mermaid reserved IDs: `end`, `class`, `subgraph`. Pick
     descriptive IDs (`User`, `MainSession`, `SecurityReviewer`).

4. **Validate with mmdc if available.**
   - Write the mermaid to a temp file (`mktemp`).
   - Run `mmdc -i <tmp.mmd> -o <tmp.svg> 2>&1`.
   - If non-zero: read the error message, fix the specific issue, retry.
     Cap at 3 retries — if still failing, surface the mermaid + error to
     the user and let them decide.
   - If `mmdc` is not on PATH: skip validation with a one-line warning.

5. **Insert or print.**
   - With `--into <path>`: scan the target for existing markers with the
     same `<name>`. If found: `Edit` to replace the entire block
     atomically (both markers stay byte-identical, body changes). If not
     found: append after the first H1 heading.
   - Without `--into`: print the fenced mermaid block to the user.

## Examples

```
/process-diagram security-review
/process-diagram bare-repo-nudge --into hooks/README.md
/process-diagram stack-check-pipeline --type flowchart --into docs/specs/2026-05-24-pivot/05-stack-freshness.md
```

## Hard rules

- **Never overwrite content outside the markers.** Idempotence is the
  whole point of the markers.
- **Never silently change marker IDs.** If the user says
  `/process-diagram security-review` and the existing block is
  `<!-- process-diagram:security-flow:start -->`, ask which one to update;
  do not duplicate.
- **Refuse to invent a flow.** If the user gives only a workflow name and
  no description, and you cannot find a SKILL/command file to read for
  it, ASK for the participants and steps. Hallucinated diagrams are
  worse than no diagram.
- **Cap retries at 3.** If `mmdc` keeps complaining, surface to the user
  rather than burning a context window on infinite tweak loops.

## Common mermaid traps (and how to avoid)

| Failure | Fix |
|---------|-----|
| Label has `(parens)` and parser bails | Wrap label in `"..."` |
| Label has `:` or `/` | Wrap label in `"..."` |
| Node ID is `end` or `class` | Pick a different ID (e.g., `EndNode`) |
| Arrow type mismatch (`-->>` in flowchart) | Sequence uses `->>` / `-->>`; flowchart uses `-->` / `-.->` |
| Stale syntax (`graph TB` instead of `flowchart TB`) | Prefer `flowchart` for new diagrams |

## What this skill does NOT do

- **Generate diagrams from code AST.** That's `/repo-map` territory
  (architecture overview from directory structure + AGENTS.md hints), or
  dedicated tools (madge for JS/TS dep graphs).
- **Auto-update existing diagrams when code changes.** Run the skill
  explicitly when the workflow shifts; the `docs-sync` skill can flag
  drift.
