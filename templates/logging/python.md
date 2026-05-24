# Python — structured logging template

Wraps stdlib `logging` with a JSON formatter and `contextvars` for
trace-id propagation. No third-party deps.

## Drop into your project

Save the module below as `<your_pkg>/logging_setup.py` (or wherever your
app initializes logging). Wire it once on startup; then import the
`logger` from anywhere.

```python
# logging_setup.py
# AIDEV-NOTE: structured logging per the AGENTS.md JSON-lines spec.
# Do not interpolate values into the `message` arg — put them in `attrs=`.
"""
Structured logging compliant with the AGENTS.md spec.

Usage:
    from logging_setup import get_logger, set_trace_context

    logger = get_logger("billing")

    # Set context (typically in your request middleware)
    set_trace_context(trace_id="a1b2c3", span_id="4d5e6f")

    # Log events
    logger.info("invoice_paid", extra={"attrs": {
        "invoice_id": "inv_789",
        "amount_cents": 4900,
    }})

    # Errors
    try:
        ...
    except Exception as e:
        logger.error("charge_failed", extra={"attrs": {
            "error_type": type(e).__name__,
            "error_message": str(e),
        }})
"""
from __future__ import annotations

import contextvars
import datetime as _dt
import json
import logging
import sys
import uuid


# AIDEV-NOTE: contextvars are per-task in asyncio, per-thread otherwise —
# the right primitive for trace propagation that does NOT leak across
# concurrent requests. Don't refactor to a module-global.
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_span_id_var:  contextvars.ContextVar[str] = contextvars.ContextVar("span_id",  default="")


def set_trace_context(*, trace_id: str = "", span_id: str = "") -> None:
    """Set the trace context for the current task/thread.

    Call this at request entry (middleware) with the incoming
    `traceparent` header values, or generate fresh ids if absent.
    """
    if trace_id:
        _trace_id_var.set(trace_id)
    if span_id:
        _span_id_var.set(span_id)


def new_trace_id() -> str:
    """Generate a fresh 16-byte hex trace id (W3C-style)."""
    return uuid.uuid4().hex


def new_span_id() -> str:
    """Generate a fresh 8-byte hex span id (W3C-style)."""
    return uuid.uuid4().hex[:16]


class _JsonFormatter(logging.Formatter):
    """Format every record as a JSON line matching the spec.

    Looked-up fields:
        record.msg          -> event (snake_case event name; required)
        record.levelname    -> level (lower-cased)
        record.name         -> service (logger name acts as service id)
        extra={'attrs': {}} -> attrs dict
        contextvars         -> trace_id, span_id

    Anything in `extra` that is NOT 'attrs' is also folded into the
    top-level event for backward compat with stdlib idioms — but the
    canonical home for user payload is `attrs`.
    """

    # AIDEV-NOTE: stdlib LogRecord puts our extra dict's keys directly on
    # the record object (no namespace). The set below is what stdlib adds
    # itself, so we can subtract it to find user-provided extras.
    _STD_LOGRECORD_FIELDS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "taskName",
        "message",
    })

    def format(self, record: logging.LogRecord) -> str:
        ts = (
            _dt.datetime
            .fromtimestamp(record.created, tz=_dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"
        )
        event = record.getMessage()  # message arg is the event name

        attrs: dict = {}
        # Prefer the explicit 'attrs' key in extra; merge stray extras as fallback.
        if isinstance(record.__dict__.get("attrs"), dict):
            attrs = dict(record.__dict__["attrs"])
        for k, v in record.__dict__.items():
            if k in self._STD_LOGRECORD_FIELDS or k == "attrs":
                continue
            attrs.setdefault(k, v)

        payload: dict = {
            "ts": ts,
            "level": record.levelname.lower(),
            "trace_id": _trace_id_var.get(),
            "span_id": _span_id_var.get(),
            "service": record.name,
            "event": event,
        }
        if attrs:
            payload["attrs"] = attrs
        if record.exc_info:
            payload["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "stack": self.formatException(record.exc_info),
            }

        return json.dumps(payload, default=str, ensure_ascii=False)


def get_logger(service: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger pre-wired with the JSON formatter.

    Pass the service name (your component / module). Idempotent — calling
    twice for the same service does not duplicate handlers.
    """
    logger = logging.getLogger(service)
    if logger.handlers:
        return logger  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False  # avoid duplicate emission through root
    return logger
```

## First call

```python
from logging_setup import get_logger, set_trace_context, new_trace_id, new_span_id

# At request entry (e.g., Flask before_request, FastAPI middleware):
set_trace_context(trace_id=new_trace_id(), span_id=new_span_id())

# In your handler:
logger = get_logger("billing")
logger.info("invoice_paid", extra={"attrs": {
    "invoice_id": "inv_789",
    "amount_cents": 4900,
    "currency": "EUR",
}})
```

Expected output:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"info","trace_id":"a1b2c3...","span_id":"4d5e6f...","service":"billing","event":"invoice_paid","attrs":{"invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"}}
```

## Middleware example (FastAPI)

```python
from fastapi import FastAPI, Request
from logging_setup import set_trace_context, new_trace_id, new_span_id

app = FastAPI()

@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    # Honor an incoming traceparent if present, else generate fresh.
    incoming = request.headers.get("traceparent")
    if incoming:
        # traceparent format: 00-<trace_id>-<span_id>-<flags>
        parts = incoming.split("-")
        trace_id = parts[1] if len(parts) > 1 else new_trace_id()
        span_id = new_span_id()  # new child span
    else:
        trace_id = new_trace_id()
        span_id = new_span_id()
    set_trace_context(trace_id=trace_id, span_id=span_id)
    return await call_next(request)
```

## Anti-patterns this template prevents

- `logger.info(f"user {id} did X")` — value in message → grep cannot
  isolate by event name.
- `print(...)` calls in services — bypasses both formatter and level
  filtering.
- Per-request trace_id as a module global — leaks across concurrent
  requests under asyncio.
- Double formatting (using `format()` on a logger that already has a
  JSON formatter).

## Testing

```python
import io, json, logging
from logging_setup import get_logger, _JsonFormatter

def test_json_output_shape():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(_JsonFormatter())
    logger = logging.getLogger("test_svc")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.info("event_name", extra={"attrs": {"k": "v"}})
    record = json.loads(buf.getvalue())
    assert record["event"] == "event_name"
    assert record["service"] == "test_svc"
    assert record["attrs"] == {"k": "v"}
    assert "ts" in record and record["ts"].endswith("Z")
```
