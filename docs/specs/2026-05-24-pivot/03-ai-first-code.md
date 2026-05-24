# 03 — AI-first code conventions

## What "AI-first" means here

The codebase is the index. The next agent to open the repo should be able
to orient and act using only `grep`, `Read`, and the AGENTS.md guidance.
No vector store, no precomputed map.

This is the answer to the user's question "does it make sense to give
agents a repo index, or is it better to put it in context?": **context
wins decisively in 2025-2026**. Boris Cherny (Claude Code lead) on
agentic search: *"outperformed everything. By a lot."* Sourcegraph
deprecated embeddings for Cody Enterprise. Aider keeps a tree-sitter
repo-map but only because aider is the agent — Claude Code's native
Explore does the same job for us. Detail in
`research_indexing.md`.

So instead of building a database, we build **the structured comment and
log layer that makes the codebase itself a usable database for grep**.

## Convention 1 — AIDEV-NOTE anchors

Source: Diwank Singh Tomer's "Field Notes from Shipping Real Code with
Claude" (Julep, 2025), widely adopted across the agent-coding community.

Three grep-able prefixes, all caps, ≤120 chars per line:

```python
# AIDEV-NOTE: this guard prevents the race documented in JIRA-1234;
# do not remove without reproducing that failure in tests first.
if not lock.acquire(timeout=0.1):
    return STALE_RESPONSE
```

```python
# AIDEV-TODO: switch to the new auth handler when ABCD-456 lands;
# tracking via `grep -r AIDEV-TODO` weekly.

# AIDEV-QUESTION: why are we double-encoding here?
# left open until we hear from billing team.
```

Rules (codified in `AGENTS.md`):

- `AIDEV-NOTE:` for load-bearing facts. WHY this constraint exists,
  where a non-obvious dependency lives, what would break.
- `AIDEV-TODO:` for known follow-ups, with enough context to resume.
- `AIDEV-QUESTION:` for genuine unknowns the next person (or agent)
  should resolve.
- **Agents read anchors first.** AGENTS.md instructs both Claude Code
  and Codex: *"Before scanning files in a module, run
  `grep -rn 'AIDEV-' <module>` and read the matching lines."*
- **Agents do not silently remove anchors.** Removing one requires an
  explicit decision in the message (e.g. "removing AIDEV-NOTE on line
  87 because the JIRA-1234 fix landed in #5021").
- **Don't decorate.** Anchors are for non-obvious decisions, not
  function descriptions, not what-the-code-does narration. The linter
  + type system + tests are already telling the next agent that.

### Enforcement — `scripts/hooks/ai-first-nudge.sh`

PostToolUse on `Write`|`Edit`|`MultiEdit`, non-blocking:

- If the diff adds ≥50 LOC to a single file AND no AIDEV-NOTE appears
  in the new lines AND the file isn't in an ignore-list pattern
  (tests, fixtures, generated code), print:
  `(claude-leverage: 73 new LOC in services/payments.py with no AIDEV-NOTE — consider anchoring the load-bearing parts)`
- If the diff creates a new directory that doesn't yet have an
  `AGENTS.md`, print: `(claude-leverage: new module services/billing/ — consider adding AGENTS.md)`

Never blocks. Frequency cap: at most one nudge per session for the same
file (tracked in `~/.claude/claude-leverage/.session-nudges.jsonl`).

## Convention 2 — Structured logging for agent consumption

When the user's apps log, the logs should be agent-readable on first
look. Spec (from `research_ai_first_code.md`, AgentTrace paper +
Dash0 / Groundcover writeups):

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3","span_id":"4d5e6f","service":"billing","event":"invoice_paid","message":"invoice paid","attrs":{"invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"}}
```

Required fields:
- `ts` — ISO-8601 UTC.
- `level` — `debug|info|warn|error`.
- `trace_id`, `span_id` — propagate across boundaries (W3C
  traceparent).
- `service` / `component` — short snake_case.
- `event` — short snake_case name, machine-greppable.
- `message` — short human string.
- `attrs` — typed object for structured payload. **Do not interpolate
  values into `message`.** `user_id` goes in `attrs.user_id`, not in
  the message string.

This convention ships as a documented section in `AGENTS.md` plus an
optional `skills/ai-logging/SKILL.md` (v1.1) that, given a file or
function, suggests how to rewrite its prints/logs into this shape.

For agent-self code (skills/subagents/hooks shipping in this plugin),
where they log to the user, we already use the
"`(claude-leverage: <event>)`" pattern in `track-delegations.sh`. Keep
that for human-visible plugin output; reserve JSON-lines for
application logs.

## Convention 3 — Per-directory AGENTS.md

Codex natively merges nested AGENTS.md files from git root down to cwd
(closer wins). Claude Code via `@AGENTS.md` import handles the root
one; per-directory ones get picked up by the agent when it Reads the
directory or grep finds the file.

Template for a non-trivial module:

```markdown
# AGENTS.md — services/payments

## What lives here
Payment processing pipeline. Integrates Stripe, internal ledger, and
the EU VAT calculator in `vat/`.

## Public surface
- `services.payments.charge(invoice, payment_method) -> ChargeResult`
- `services.payments.refund(charge_id, amount=None) -> RefundResult`
Internal helpers in `_internal.py` are not stable; treat as private.

## Gotchas
- Stripe webhook signing key lives in env `STRIPE_WHK`; never log raw
  webhook bodies (PCI).
- VAT calculator is idempotent ONLY on `(invoice_id, country_code)` —
  do not retry on partial responses; see AIDEV-NOTE in `vat/calc.py`.

## Tests
`pytest services/payments/ -k integration` (requires `STRIPE_TEST_KEY`).
```

When to add one:
- Module has non-trivial public surface.
- Module has gotchas an agent would otherwise rediscover the hard way.
- Module has its own conventions different from the rest of the repo.

When *not* to add one:
- Module is small and self-explanatory.
- The AGENTS.md would only restate what's in code + linter rules.

The PostToolUse nudge suggests but doesn't enforce.

## Convention 4 — File/module organization

Three patterns that demonstrably reduce files-read-per-task
(Repository Intelligence Graph paper):

- **Co-locate tests** with code: `foo.py` next to `foo_test.py`. Avoid
  parallel `tests/` trees that double the agent's reads. Exception:
  end-to-end / integration tests that span modules naturally live in
  `tests/integration/`.
- **One concept per module, thin entrypoint.** `services/payments/__init__.py`
  exports the public surface; agents reading the entrypoint get a
  free table of contents.
- **Predictable patterns.** "All API routes go in `app/api/`." "All
  database migrations in `migrations/`." Document the pattern in
  AGENTS.md ("conventions" section), not in prose distributed across
  files.

These are guidance only — no hook can sensibly enforce module shape.

## What we explicitly do not do

- **No `.repo-map.json` checked in.** Stale-index killer.
- **No vector store / embeddings build step.** See `research_indexing.md`.
- **No ctags / global symbol index.** Native Explore covers it.
- **No mandate to add AIDEV-NOTE to every function.** Decoration is
  worse than nothing.
- **No CLAUDE-CODE-specific magic syntax.** Conventions work the same
  for Codex, Cursor, Aider, anyone reading the repo.

## Open questions for review

1. **The PostToolUse nudge frequency.** Once per session per file is
   the lightest reasonable cap. Should it be once per session period
   (never nag twice)? Or per-day? My recommendation: per-file
   per-session. Iterate from user complaints.
2. **AIDEV-NOTE in test files.** Currently the nudge ignores files
   matching `*_test.*`, `test_*.*`, `**/tests/**`, `**/fixtures/**`.
   Want exceptions (e.g., security test files where AIDEV-NOTE
   matters)?
3. **Logging skill (v1.1).** Should we ship `ai-logging` in v1.0 or
   defer? Probably defer — most of the user's value comes from the
   AIDEV-NOTE convention + enforcement, not from log-rewriting help.
4. **Per-directory AGENTS.md vs nested CLAUDE.md.** Codex *requires*
   AGENTS.md (no AGENTS.md → no instruction load). Claude Code reads
   CLAUDE.md but the `@AGENTS.md` import only resolves at the root.
   For nested dirs, Claude Code agents will pick up AGENTS.md content
   only when they Read the file directly. This is the practical
   tradeoff: nested AGENTS.md is "Codex-loaded, Claude-discovered."
   That's fine; both behaviors land the content in context where
   needed.
