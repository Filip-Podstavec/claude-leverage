# Writing code for AI agents — practitioner-grade research (2026)

Scope: concrete patterns that let an agent (Claude Code, Codex, Cursor) open a repo and act without a human explaining. Sources cited inline.

## 1. AI-targeted code comments — the AIDEV-* convention

The most influential concrete convention is **anchor comments**, popularized by Diwank Singh Tomer's "Field Notes from Shipping Real Code with Claude" (Julep, 2025), which trended on HN and LessWrong and got folded into multiple "field notes" derivatives.

Rules from the original post:

- Prefixes: `AIDEV-NOTE:`, `AIDEV-TODO:`, `AIDEV-QUESTION:` — all-caps, grep-able.
- Keep them ≤120 chars.
- "Before scanning files, always first try to grep for existing `AIDEV-*`" — i.e. agents are instructed (via CLAUDE.md) to read anchors first.
- "Do not remove `AIDEV-NOTE`s without explicit human instruction."
- Add them when code is "too complex, or very important, or could have a bug."

**Evidence the tag prefix matters (vs. plain comments):** the author's defense on HN — `AIDEV-*` is (a) visually distinct from normal TODOs, (b) grep-able as a fenced subset so the agent can "look around the codebase in one glance" without pulling unrelated TODO noise into context. That second point is the real win: it's a token-efficient retrieval primitive.

**When the payoff is real:** "WHY this constraint exists" comments at non-obvious decision points (regulatory carve-outs, perf workarounds, ordering dependencies, idempotency tricks). Agents will otherwise "fix" the constraint away — this is the dominant failure mode the convention prevents. Cursor's own agent guide says it bluntly: agents need "clear signals for whether changes are correct" (Cursor, *Best practices for coding with agents*), and a load-bearing comment is the cheapest such signal.

**When it's clutter:** restating what the code does, decorating every function, or replacing what a linter/type system would catch deterministically. Anthropic's CLAUDE.md guidance generalizes here: "Never send an LLM to do a linter's job" (HumanLayer, *Writing a good CLAUDE.md*).

A research-flavored alternative — **Semantic Anchors** (github.com/LLM-Coding/Semantic-Anchors) — promotes referencing known methodologies by name ("TDD, London School") rather than inventing project-local tags. Useful complement; not a replacement for AIDEV-*.

## 2. Structured logging for agent consumption

Consensus from observability writeups (Dash0, Groundcover, Alhena, the AgentTrace paper arXiv:2602.10133):

- **JSON lines, one event per line.** Free-text logs force the agent to write fragile regex.
- **Required fields:** ISO-8601 timestamp, level, `trace_id`, `span_id`, `service`/`component`, `event` (short snake_case name), `message`, plus a typed `attrs` object for structured payload.
- **Propagate `trace_id` across process/HTTP/queue boundaries** (W3C traceparent header). This is what lets an agent reconstruct "what happened in this one request" from `grep trace_id=…` across services — cited as cutting MTTR 30–50% in centralized-logging studies (Dash0).
- **Agent-specific additions (AgentTrace):** for code that *is* an AI agent, log cognitive traces (prompt, response, tool calls), operational traces (latency, cost, tokens), and contextual traces (session/user/env) as separate schema-typed events, not strings.
- **Anti-patterns:** multi-line stack traces without a `stack` field, log messages that interpolate values (`f"user {id} failed"`) instead of putting `id` in attrs, and per-service log shapes that diverge.

For human-AI mixed consumption: a structured log can always be pretty-printed; the reverse is lossy. Default to JSON in prod, pretty in dev via a formatter flag.

## 3. File/module organization for context-efficient agents

Patterns that demonstrably reduce files-read-per-task (Repository Intelligence Graph paper, arXiv:2601.10112, reports +12.2% accuracy and −53.9% completion time with a structural map):

- **Co-locate tests with code** (`foo.py` next to `foo_test.py`). Agents almost always need both; separated `tests/` trees double the reads.
- **One concept per module, exported via a thin `__init__.py`/`index.ts`.** Agents follow imports — a focused entrypoint is a free table of contents.
- **Per-directory README (or `AGENTS.md`)** with: what lives here, public surface, gotchas. Codex actually merges nested `AGENTS.md` files from repo root down to the cwd (OpenAI Codex docs), so directory-scoped instructions compose without bloating the root.
- **Stable file naming and predictable patterns** ("API routes go in `app/api/`") — Cursor's guide: "agents learn from executable signals" and from being able to *predict* where things live.
- **Reference canonical examples by path** in your conventions: "See `components/Button.tsx` for component structure" beats restating the convention in prose (Cursor blog).
- The Harness writeup ("The Agent-Native Repo") makes the stronger claim: in 2026, "agents fail more often because of repository ambiguity than model quality." Structure is a model-quality multiplier.

## 4. CLAUDE.md / AGENTS.md content discipline

The Anthropic official guide (code.claude.com/docs/best-practices) and HumanLayer's widely-cited piece converge:

- **Target length:** Anthropic says "keep it short"; HumanLayer benchmarks at ~60 lines; community consensus is <300 lines hard ceiling. Why: "Claude Code's system prompt already contains ~50 instructions… that's nearly a third of the instructions your agent can reliably follow."
- **Include:** bash commands the agent can't guess, code-style rules that *differ from language defaults*, test runner preferences, branch/PR conventions, env quirks, non-obvious gotchas, project-specific architectural decisions.
- **Exclude:** anything inferable from the code, standard language idioms, exhaustive command catalogs, API docs (link instead), file-by-file maps, "write clean code"-style platitudes, and auto-generated `/init` output (HumanLayer: "too high-leverage to leave to automation" — though Anthropic disagrees and recommends `/init` as a starting point).
- **Decision rule per line:** "Would removing this cause Claude to make mistakes?" If no, cut.
- **Progressive disclosure beats stuffing:** use `@path/to/file` imports or skills loaded on demand. Anthropic explicitly: "for domain knowledge or workflows that are only relevant sometimes, use skills instead."
- **AGENTS.md is now the cross-tool standard** (OpenAI, Google, others), with the same discipline; Codex reads it before any work and merges directory-scoped overrides.
- **Anti-patterns observed in the wild:** stale instructions referencing deleted files, "Code style" sections that duplicate the linter config, and the kitchen-sink CLAUDE.md that ends up ignored. Cursor's data: rules followed ~70% of the time; hooks 100% — so promote any must-always rule to a hook.

## 5. AI-first vs. YAGNI — where's the line?

The counter-position is real. YAGNI's classic formulation (c2 wiki, Fowler) says don't add structure for speculative needs. Three honest concessions:

- **Clear, conventional code is already AI-first.** Typed signatures, small functions, descriptive names, and a green test suite outperform any amount of AI-targeted decoration. Cursor's recommendation reduces to "use typed languages, configure linters, write tests."
- **AIDEV-* tagging and per-dir READMEs are cheap; structural rewrites for agents are not.** Don't restructure a working monorepo into agent-friendly micro-packages on speculation.
- **Stale agent-targeted artifacts are worse than none.** A 400-line CLAUDE.md describing a refactored module is actively misleading. If you won't maintain it, don't write it.

The defensible line: **invest where bugs cost real money and the codebase has load-bearing non-obviousness** (Diwank's original criterion). For a hobby script, write clear code and stop. For a payments service with five years of regulatory carve-outs, anchor comments, structured logs, and a tight CLAUDE.md pay for themselves on the first agent-driven incident response.

## Sources

- Diwank Singh Tomer, *Field Notes from Shipping Real Code with Claude* — diwank.space (origin of AIDEV-*)
- HN discussion: news.ycombinator.com/item?id=44211417
- Anthropic, *Best practices for Claude Code* — code.claude.com/docs/en/best-practices
- HumanLayer, *Writing a good CLAUDE.md* — humanlayer.dev/blog/writing-a-good-claude-md
- OpenAI Codex, *Custom instructions with AGENTS.md* — developers.openai.com/codex/guides/agents-md
- Cursor, *Best practices for coding with agents* — cursor.com/blog/agent-best-practices
- Harness, *The Agent-Native Repo: Why AGENTS.MD is the New Standard*
- AgentTrace: A Structured Logging Framework for Agent System Observability — arXiv:2602.10133
- Repository Intelligence Graph — arXiv:2601.10112
- Dash0, *Practical Structured Logging for Modern Applications*
- LLM-Coding/Semantic-Anchors — github.com/LLM-Coding/Semantic-Anchors
- agents.md open standard — agents.md
