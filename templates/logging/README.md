# Structured-logging templates

Drop-in starter kits implementing the AGENTS.md JSON-lines logging spec
per language. Each template is a self-contained, copy-paste-able module
that wraps the language's standard logger to emit:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3","span_id":"4d5e6f","service":"billing","event":"invoice_paid","attrs":{"invoice_id":"inv_789"}}
```

## Available templates

| Template | Stack | Library used |
|---|---|---|
| [`python.md`](python.md) | Python ≥3.10 | stdlib `logging` + custom JSON formatter + `contextvars` for trace propagation |
| [`typescript.md`](typescript.md) | Node.js ≥20 / TypeScript | Either `pino` (preferred for prod) or native `console` + JSON wrapper |
| [`go.md`](go.md) | Go ≥1.21 | stdlib `log/slog` with `JSONHandler` + `context` for trace propagation |
| [`rust.md`](rust.md) | Rust (any recent edition) | `tracing` + `tracing-subscriber` with JSON layer |

## How to use

**With `/init-repo`** (recommended): the skill walks you through
language detection and drops the right template into your project,
along with example usage.

**Manually**: open the template for your language, copy the logger init
module into your project, and follow the per-template "first call"
example. Adjust the `service` name and any project-specific fields.

**With `/log-structured`**: run an audit to find non-structured logging
in an existing codebase; the audit references these templates by path
for the suggested logger setup.

## Spec recap

Required fields on every log event:

- `ts` — ISO-8601 UTC, millisecond precision
- `level` — `debug | info | warn | error`
- `trace_id` — W3C-style trace id, propagated across request boundaries
- `span_id` — operation-scoped id within a trace
- `service` — the producing service / component (short snake_case)
- `event` — short snake_case event name (e.g., `invoice_paid`,
  `user_authenticated`)
- `attrs` — typed object for structured payload (no string interpolation
  into `message`)

Optional but useful: `message` (short human-readable summary; do NOT
interpolate values into it), `error` (object with `type`, `message`,
`stack`).

The core discipline: **put values in `attrs`, never in `message`**.
That's what makes logs grep-able by event type and reconstructable per
trace by a future agent.
