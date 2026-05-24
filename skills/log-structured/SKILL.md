---
name: log-structured
description: |
  Walk a codebase (or a specific path), find non-structured logging
  statements (print, console.log, logger.X with string interpolation),
  and suggest spec-compliant replacements per the JSON-lines logging
  convention documented in AGENTS.md. Read-only — never auto-rewrites.
  Cross-tool (Claude Code and Codex).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(ls:*)
  - Bash(test:*)
argument-hint: "[path] [--lang python|typescript|go|rust|auto]"
---

# /log-structured

## What it does

Helps retrofit a codebase to the structured-logging spec from `AGENTS.md`:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3","span_id":"4d5e6f","service":"billing","event":"invoice_paid","attrs":{"invoice_id":"inv_789"}}
```

Walks a target path, finds anti-patterns, and emits a structured report
with file:line citations and concrete suggested replacements. **Never
modifies code** — the user decides per-finding.

## Anti-patterns flagged

| Pattern | Why it's a problem | Suggested fix |
|---------|-------------------|---------------|
| `print(...)` in production code | No level, no context, no structure | Replace with logger call |
| `console.log(...)` in production code | Same; not structured | Replace with structured logger |
| `logger.X(f"user {id} did {action}")` (Python) | Values baked into message → agent can't grep `event=did_action` | Move values to `attrs={"user_id": id, "action": action}` |
| `` logger.x(`user ${id} did ${action}`) `` (TS/JS) | Same | `logger.info("user_action", { user_id: id, action })` |
| `fmt.Printf("user %d ...", id)` followed by `log.Print` | Same | `slog.Info("user_action", "user_id", id)` |
| Missing `trace_id` propagation | Can't reconstruct request flow | Wire context-aware logger (template per lang) |
| Logging to stdout in a service that should log structured (e.g., `print` in Flask handler) | Operator tooling can't parse | Wire JSON formatter |

## Workflow

1. **Resolve target.** Default `.` (whole repo). If `$ARGUMENTS` has a
   path, use that. If `--lang <name>` is given, restrict scan to that
   language; else auto-detect from file extensions.

2. **Detect language(s)** by file extension. Walk only files matching:
   - Python: `*.py` (skip `tests/`, `*_test.py`, `__pycache__`)
   - TypeScript/JavaScript: `*.ts`, `*.tsx`, `*.js`, `*.jsx` (skip
     `node_modules/`, `dist/`, `build/`, `*.test.*`, `*.spec.*`)
   - Go: `*.go` (skip `*_test.go`, `vendor/`)
   - Rust: `*.rs` (skip `target/`, `tests/`)

3. **Grep for anti-patterns** in the scoped files. Use `Grep` tool with
   the patterns documented per-language in
   [`../../templates/logging/`](../../templates/logging/).

4. **For each finding**, emit:
   - `file:line — current line — suggested replacement`
   - Reference the language template by path:
     `see templates/logging/<lang>.md for the logger init`

5. **Summary** at the end:
   - Count by language
   - Count by anti-pattern type
   - Path to the language template for setup
   - Reminder: this skill does NOT modify code

## Output format

```markdown
# Structured logging audit — <YYYY-MM-DD>, <root>

## Findings

### src/billing/charge.py
- **line 47**: `print(f"charged user {user_id}")` →
  `logger.info("user_charged", attrs={"user_id": user_id})`
  See `templates/logging/python.md` for logger setup.
- **line 89**: `logger.error(f"failed: {e}")` →
  `logger.error("charge_failed", attrs={"error": str(e), "trace_id": current_trace_id()})`

### src/api/handler.ts
- **line 23**: `console.log(`req from ${req.ip}`)` →
  `logger.info("request_received", { ip: req.ip, route: req.path })`
  See `templates/logging/typescript.md`.

## Summary

- 2 files scanned
- 3 findings (2 print/console.log, 1 message-interpolation)
- Language templates: see `templates/logging/{python,typescript}.md`
- This audit is read-only. Apply fixes incrementally — start with the
  highest-traffic event types where structured logs pay off fastest.

## Out of scope

- Already-structured logs that just use the wrong field name conventions
  (e.g., `userId` vs `user_id`) — that's a separate harmonization pass.
- Logger choice / library swap — this audit assumes you'll wire a
  structured logger per the template; it doesn't force a specific library.
```

## Hard rules

- **Read-only.** No Edit/Write in the tool list. If asked to "just fix
  the prints" — refuse. The user picks which findings matter; some
  scripts have `print` legitimately (CLI output).
- **Never assume the logger import.** Each finding references the
  language template, which documents the logger initialization. Don't
  hallucinate `from app.logger import logger` if the project doesn't
  have one.
- **Skip tests by default.** Test files often print intentionally for
  debugging. If user passes `--include-tests`, then scan them too.
- **One finding per line.** Don't bundle multiple patterns on the same
  line into one finding — file:line citation must be precise.

## Tunables

- `--lang <name>` — restrict scan to one language.
- `--include-tests` — scan test files too.
- `--max-findings <N>` — cap output (default 100; large repos can
  produce thousands of findings, most are noise after the first 50).

## When to run

- Onboarding into a legacy codebase that pre-dates the convention.
- After AGENTS.md adoption — run once to see baseline.
- Before a structured-logging migration to size the work.
- After major refactoring of logging code, to catch regressions.

Pairs naturally with `/init-repo` (which can drop the language template
into a new project) and with the AIDEV-NOTE convention (anchor the
non-obvious logging decisions in code).
