# Plan 3 — dynamic validation (deferred design record)

> **Status:** DEFERRED — design recorded, intentionally unscheduled. Do not
> implement until (a) Plans 1–2 are shipped AND (b) a real case appears where
> declared commands that don't run slip past the semantic review. Parent
> design: [2026-08-01-readiness-extension-design.md](2026-08-01-readiness-extension-design.md).
> Revised after Opus design review: ships as a **separate skill**, not a
> `/repo-doctor` scope (finding 9).

**Goal:** Answer the one question layers 1–2 cannot: do the build/test/lint
commands this repo *declares* actually run?

**Why deferred:** It is the only layer that executes repo-declared commands —
the safety story (not the check logic) is the bulk of the work; the semantic
scope already catches the most common lie (commands referencing files that
don't exist) statically; and shipping it half-guarded would contradict the
stack's "security by default" pillar.

## Contract (fixed now; ADR 0012 Decision (f) reserves the carve-out)

- **Separate skill, not a `/repo-doctor` scope.** Ships as its own skill
  (working name `/dynamic-check`) with its own frontmatter. Rationale
  (ADR 0012 (f)): the broad Bash grant this needs cannot sit in
  `/repo-doctor`'s always-active `allowed-tools` gated only by prose — that
  is exactly the "model rationalizes past the guardrail" failure mode the
  stack's hooks exist to prevent. This deliberately reverses ADR 0007's
  "one audit command" argument for this one layer; `/repo-doctor`'s report
  cross-references the skill instead.
- **Explicit-only.** Never runs as part of any `/repo-doctor` scope, never by
  default, never from a hook. Invoking it IS the consent to execute the
  repo's declared commands in the current environment — the same trust the
  user already extends by running `pytest` here by hand.
- **Declared commands only.** Sources, in order: fenced ```bash blocks under
  a Build/Test/Lint-shaped heading in root `AGENTS.md`; then README
  quickstart blocks. Nothing inferred, nothing synthesized. Each command is
  attributed to its source `file:line` in the report.
- **Denylist before anything runs.** Skip (and report as `skipped:
  denylisted`) any command matching: `sudo`, `rm `, `curl|wget … | sh`,
  `git push`, `docker … --privileged`, `> /dev/`, `chmod -R`, package
  publishes (`npm publish`, `twine upload`, `cargo publish`). The denylist is
  a tripwire, not a sandbox — any declared command is arbitrary code
  execution by indirection (`make setup`, `npm run build` can run anything
  through scripts the denylist never sees). The actual sandbox is the tool's
  own permission layer (Claude Code Bash permissions; Codex
  `workspace-write` profile, see `/codex-sandbox`).
- **Bounded.** Sequential execution, per-command timeout 300 s (override
  `CLAUDE_LEVERAGE_DYNAMIC_TIMEOUT`), stop after first 3 failures.
- **Never in the score.** The skill emits its own report (shape below) and
  its own `--fail-on` exit code; `/repo-doctor`'s deterministic score and
  levels never consume it (ADR 0012).
- **Read-only caveat, stated honestly.** Running builds/tests mutates
  untracked state (caches, `__pycache__`, `node_modules`). The SKILL's hard
  rule gains: "dynamic scope never modifies *tracked* files and never
  commits; build artifacts are the declared commands' own business."

## Report shape

```markdown
## Dynamic validation (advisory — executed declared commands)

| Command | Source | Result |
|---|---|---|
| `pytest tests/ -v` | AGENTS.md:98 | ✅ pass (41 s) |
| `make lint` | README.md:23 | ❌ fail — `make: *** No rule to make target 'lint'` (tail below) |
| `sudo make install` | README.md:31 | ⛔ skipped: denylisted (`sudo`) |
```

Failure rows carry the last ~5 lines of output, enough to act on without
re-running.

## Implementation sketch (when scheduled)

1. New `skills/dynamic-check/SKILL.md` with the contract above; its
   frontmatter carries the broad Bash grant, and the ADR update calls out
   that this is the single widest permission in the plugin — which is why it
   lives in a skill nobody runs by accident.
2. `/repo-doctor` gains only a cross-reference line in its report footer
   ("declared-command validation: `/dynamic-check`, opt-in").
3. `docs/repo-doctor-gaming.md` rows: "declared commands curated to only the
   ones that pass | countered by S1/S2 judging *coverage* of declared
   commands".
4. CHANGELOG + version bump + READMEs per `docs/maintaining.md`.
5. Open question for scheduling time: whether Claude Code's permission
   prompts on each command make the denylist redundant in interactive runs
   (they don't in `--dangerously-skip-permissions` / Codex full-auto runs —
   which is exactly why the denylist stays).
