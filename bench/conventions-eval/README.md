# Conventions A/B — full-repo quality eval

**The valid test of whether the plugin improves output, on a real codebase.**

A synthetic single-file naming test does NOT measure the plugin's value — a
capable model writes clean generic code unaided (we ran those experiments and
rolled them back; see the session log 2026-06-03). The plugin's value —
navigation, anti-bloat in legacy code, applying *non-default* conventions — only
shows up on a real codebase with real cruft. That is what this harness measures.

## What it answers (three separate questions, three measurements)

1. **Are the conventions surfaced?** — deterministic, no model. Feed the
   `context-surface` hook a fake edit to a source file and grep for the
   conventions block. (One-liner; see "Delivery check" below.)
2. **Do agents apply non-default conventions?** — a divergent-rule probe: same
   task with vs without a house rule the model can't guess; measure compliance.
3. **Is the output better overall?** — the full-repo before/after A/B here.

## Setup (operator side — trees are NOT committed)

Two trees of the **same real codebase**, kept on the operator's machine/server
(client code never enters this repo):

- `before/` — a historical commit pre-adoption: no `AGENTS.md`, no AIDEV anchors,
  no `conventions.yml`, monolithic structure. Remote removed so the agent can't
  peek at future commits.
- `after/` — current HEAD enriched with the in-repo artifacts: root + per-dir
  `AGENTS.md`, AIDEV anchors, ADRs, `GLOSSARY.md`, **`conventions.yml`** (run
  `/conventions-init`, fill the house rules), and a built context-map manifest
  (`/refresh-context-map`).

## Run

Identical task prompt, fresh `claude`/`codex` invocations, plugin ON in both
(measures the in-repo enrichment) — same calendar day, no carry-over context.
The task should touch naming + structure + at least one house rule.

## Measure

- **Task success** (binary): did it produce correct, working code? — the
  load-bearing signal.
- **House-rule compliance**: did the change follow the divergent `conventions.yml`
  rules the model couldn't infer? A per-rule grep/check (e.g. required prefix,
  chosen library, error pattern). This is where the plugin earns its keep.
- **Adherence delta**: `python bench/conventions-eval/score_diff.py <before_change> <after_change>`
  on the produced change. A hygiene/delivery signal — expect it small for a strong
  model; do NOT treat it as the verdict.
- **Cost / orientation**: token cost and files-read-before-first-edit from the
  JSONL transcript (same as `bench/eval`).

## Delivery check (deterministic, run on the target repo)

```bash
repo=$(git rev-parse --show-toplevel); f="$repo/<some-source>.py"
printf '{"tool_name":"Edit","cwd":"%s","tool_input":{"file_path":"%s"}}' "$repo" "$f" \
  | bash "$repo/scripts/hooks/context-surface.sh" \
  | python -c "import sys,json;print(json.load(sys.stdin)['hookSpecificOutput']['additionalContext'])"
```
Conventions appear → the plugin is feeding them in. No model, no cost.

## Honest caveats

- Small n is directional, not significant — report spread, never headline a delta
  the n can't support.
- The adherence score is one signal among three; task-success and house-rule
  compliance carry more weight for the "is it useful" question.
- Keep everything client-side and sanitized — no client code, name, or task
  description in this repo.
