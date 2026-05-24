# TypeScript / Node.js — structured logging template

Two implementations: **pino** (preferred for production; fast, schema-aware)
and **native console + JSON wrapper** (zero deps; fine for small services).
Both use `AsyncLocalStorage` for trace propagation.

## Option A: pino-based (preferred)

Install:

```bash
npm install pino
# Optional: pino-pretty for dev-mode pretty printing
npm install --save-dev pino-pretty
```

Save as `src/lib/logging.ts`:

```typescript
// AIDEV-NOTE: structured logging per the AGENTS.md JSON-lines spec.
// Do not interpolate values into the event/message arg — put them in
// the attrs object (passed as the FIRST arg to the log methods below).
import pino from "pino";
import { AsyncLocalStorage } from "node:async_hooks";
import { randomBytes } from "node:crypto";

type TraceContext = {
  trace_id: string;
  span_id: string;
};

const traceStore = new AsyncLocalStorage<TraceContext>();

export function newTraceId(): string {
  return randomBytes(16).toString("hex");
}

export function newSpanId(): string {
  return randomBytes(8).toString("hex");
}

export function runWithTrace<T>(
  ctx: TraceContext,
  fn: () => T,
): T {
  return traceStore.run(ctx, fn);
}

export function getTrace(): TraceContext {
  return traceStore.getStore() ?? { trace_id: "", span_id: "" };
}

const base = pino({
  // Spec field names override pino defaults.
  timestamp: () => `,"ts":"${new Date().toISOString()}"`,
  // base: null disables pino's default `pid` / `hostname` bindings AND
  // suppresses the numeric `level` field — otherwise the output would
  // contain BOTH a numeric level (pino default) and our string level
  // (from formatters.level below), which downstream parsers find
  // confusing.
  base: null,
  formatters: {
    level(label) {
      return { level: label };
    },
    log(obj) {
      // Inject current trace context into every record.
      const trace = getTrace();
      return { ...obj, trace_id: trace.trace_id, span_id: trace.span_id };
    },
  },
  // Mirror Python template's behavior: pino calls .msg the message;
  // we want `event` as the canonical field. We always pass the event as
  // the first string arg to logger.info(), so pino puts it under `msg`.
  // messageKey renames it to `event` in the output.
  messageKey: "event",
});

export function getLogger(service: string) {
  return base.child({ service });
}

// First-call example:
//
//   import { getLogger, runWithTrace, newTraceId, newSpanId } from "./lib/logging";
//
//   const logger = getLogger("billing");
//
//   runWithTrace({ trace_id: newTraceId(), span_id: newSpanId() }, () => {
//     logger.info({ attrs: { invoice_id: "inv_789", amount_cents: 4900 } }, "invoice_paid");
//   });
//
// Output:
//   {"level":"info","ts":"2026-05-24T12:34:56.789Z","attrs":{"invoice_id":"inv_789","amount_cents":4900},"trace_id":"...","span_id":"...","service":"billing","event":"invoice_paid"}
```

## Express / Fastify middleware

```typescript
import type { Request, Response, NextFunction } from "express";
import { runWithTrace, newTraceId, newSpanId } from "./lib/logging";

export function traceMiddleware(req: Request, _res: Response, next: NextFunction) {
  const incoming = req.header("traceparent");
  let trace_id = newTraceId();
  let span_id = newSpanId();
  if (incoming) {
    // traceparent: 00-<trace_id>-<span_id>-<flags>
    const parts = incoming.split("-");
    if (parts.length >= 4) {
      trace_id = parts[1];
      // Generate a NEW child span; do not reuse parent's span id.
      span_id = newSpanId();
    }
  }
  runWithTrace({ trace_id, span_id }, () => next());
}
```

## Option B: zero-dependency native console wrapper

For small CLIs or services that don't want a runtime dependency:

```typescript
// src/lib/logging.ts (no-deps variant)
import { AsyncLocalStorage } from "node:async_hooks";
import { randomBytes } from "node:crypto";

type TraceContext = { trace_id: string; span_id: string };
const traceStore = new AsyncLocalStorage<TraceContext>();

export const newTraceId = (): string => randomBytes(16).toString("hex");
export const newSpanId  = (): string => randomBytes(8).toString("hex");

export const runWithTrace = <T>(ctx: TraceContext, fn: () => T): T =>
  traceStore.run(ctx, fn);
const getTrace = (): TraceContext =>
  traceStore.getStore() ?? { trace_id: "", span_id: "" };

type Level = "debug" | "info" | "warn" | "error";
type Attrs = Record<string, unknown>;

function emit(service: string, level: Level, event: string, attrs?: Attrs): void {
  const trace = getTrace();
  const payload: Record<string, unknown> = {
    ts: new Date().toISOString(),
    level,
    trace_id: trace.trace_id,
    span_id: trace.span_id,
    service,
    event,
  };
  if (attrs && Object.keys(attrs).length > 0) payload.attrs = attrs;
  // stdout for info/debug; stderr for warn/error (Unix convention).
  const sink = level === "warn" || level === "error" ? process.stderr : process.stdout;
  sink.write(JSON.stringify(payload) + "\n");
}

export function getLogger(service: string) {
  return {
    debug: (event: string, attrs?: Attrs) => emit(service, "debug", event, attrs),
    info:  (event: string, attrs?: Attrs) => emit(service, "info",  event, attrs),
    warn:  (event: string, attrs?: Attrs) => emit(service, "warn",  event, attrs),
    error: (event: string, attrs?: Attrs) => emit(service, "error", event, attrs),
  };
}

// First-call example:
//
//   const logger = getLogger("billing");
//   runWithTrace({ trace_id: newTraceId(), span_id: newSpanId() }, () => {
//     logger.info("invoice_paid", { invoice_id: "inv_789", amount_cents: 4900 });
//   });
```

## Anti-patterns this template prevents

- `` console.log(`user ${id} ...`) `` — value in message; instead pass
  `{ user_id: id }` as `attrs`.
- `logger.info("user " + id + " logged in")` — same problem; the event
  arg is for the snake_case event name, attrs is for values.
- Trace_id stored on `req.locals` or `globalThis` — breaks under async
  concurrency. `AsyncLocalStorage` is the right primitive.
- Logging the full request object (`logger.info("req", { req })`) —
  pollutes logs with circular refs and large bodies; pick fields.

## Testing

```typescript
import { test, expect, vi } from "vitest";  // or jest
import { getLogger, runWithTrace, newTraceId, newSpanId } from "./lib/logging";

test("native variant emits valid JSON with spec fields", () => {
  const writes: string[] = [];
  vi.spyOn(process.stdout, "write").mockImplementation((s) => {
    writes.push(s.toString());
    return true;
  });

  const logger = getLogger("test_svc");
  runWithTrace({ trace_id: newTraceId(), span_id: newSpanId() }, () => {
    logger.info("test_event", { k: "v" });
  });

  const record = JSON.parse(writes[0].trim());
  expect(record.event).toBe("test_event");
  expect(record.service).toBe("test_svc");
  expect(record.attrs).toEqual({ k: "v" });
  expect(record.ts).toMatch(/Z$/);
  expect(record.trace_id).toBeTruthy();
});
```

## Which to pick

- **Pino**: production services, especially HTTP/RPC. Battle-tested,
  schema-aware, redaction support, dev-mode pretty printer.
- **Native**: CLIs, small Lambdas, anywhere you want zero runtime deps
  and full visibility into what gets emitted.
