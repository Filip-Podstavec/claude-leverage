# Rust — structured logging template

Built on `tracing` + `tracing-subscriber` with a JSON layer.
`tracing::Span` carries the trace_id / span_id naturally; the JSON
formatter emits the spec shape.

## Add deps

In `Cargo.toml`:

```toml
[dependencies]
tracing = "0.1"
# Note: "chrono" feature is REQUIRED for fmt::time::ChronoUtc used below.
tracing-subscriber = { version = "0.3", features = ["json", "env-filter", "chrono"] }
uuid = { version = "1", features = ["v4"] }
```

`tracing-subscriber`'s `chrono` feature pulls in the `chrono` crate
transitively. If your project already uses `time` or wants to avoid
chrono, swap `ChronoUtc` below for `time::format_description::well_known::Iso8601`
plus the `time` crate (and drop the `chrono` feature).

## Drop into your project

Save as `src/logging.rs`:

```rust
// AIDEV-NOTE: structured logging per the AGENTS.md JSON-lines spec.
// Do not interpolate values into the event/message — use the `event` arg
// for the snake_case name and pass values as structured fields via the
// `tracing` macros (e.g. `info!(invoice_id = "inv_789", "invoice_paid")`).
use tracing_subscriber::{
    fmt::{self},
    prelude::*,
    EnvFilter,
};
use uuid::Uuid;

pub fn new_trace_id() -> String {
    Uuid::new_v4().simple().to_string()
}

pub fn new_span_id() -> String {
    let mut s = Uuid::new_v4().simple().to_string();
    s.truncate(16);
    s
}

/// Initialize the global tracing subscriber. Call once at program start.
/// The returned guard is the root span carrying `service`; keep it alive
/// (typically by binding to `_root_guard` in `main`) for the duration of
/// the program — when it drops, `service` stops appearing on events.
///
/// Respects RUST_LOG env var for filtering (`info`, `debug`, etc.).
pub fn init(service: &'static str) -> tracing::span::EnteredSpan {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));

    tracing_subscriber::registry()
        .with(filter)
        .with(
            fmt::layer()
                .json()
                .with_current_span(true)
                .with_span_list(true)        // emit the full span stack — service shows up here
                .with_writer(std::io::stdout)
                .with_timer(fmt::time::ChronoUtc::rfc_3339()),
        )
        .init();

    // Root span carrying the service name. Returned to the caller as an
    // EnteredSpan so it stays active until dropped.
    tracing::info_span!("svc", service = service).entered()
}
```

## First call

```rust
// src/main.rs
use tracing::{info, info_span};
use yourapp::logging::{init, new_trace_id, new_span_id};

fn main() {
    let _root_guard = init("billing");  // keep alive for program duration

    let trace_id = new_trace_id();
    let span_id  = new_span_id();

    let request_span = info_span!(
        "request",
        trace_id = %trace_id,
        span_id = %span_id,
    );
    let _enter = request_span.enter();

    info!(
        invoice_id = "inv_789",
        amount_cents = 4900,
        currency = "EUR",
        "invoice_paid",
    );
}
```

Output (sample):

```json
{"timestamp":"2026-05-24T12:34:56.789Z","level":"INFO","fields":{"message":"invoice_paid","invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"},"target":"yourapp::main","span":{"trace_id":"a1b2...","span_id":"4d5e...","name":"request"},"spans":[{"service":"billing","name":"svc"},{"trace_id":"a1b2...","span_id":"4d5e...","name":"request"}]}
```

This matches the **spirit** of the spec (event name, structured fields,
service identity, trace context) — the field layout differs slightly
from the Python / Go templates because tracing-subscriber renders span
context as a nested `span` / `spans` object rather than flat
`trace_id` / `span_id` top-level keys.

If you need exact field-name parity with the other language templates
downstream (e.g., for a shared log aggregator), write a custom
`tracing_subscriber::fmt::format::FormatEvent` impl that flattens
span context into top-level `trace_id` / `span_id` / `service` fields.
That's an advanced customization — the default emitted shape above is
fine for most aggregators (Loki / OTEL / Datadog all handle the
nested layout).

## HTTP middleware (axum)

```rust
use axum::{http::Request, middleware::Next, response::Response};
use tracing::info_span;

pub async fn trace_layer<B>(req: Request<B>, next: Next<B>) -> Response {
    let trace_id = req
        .headers()
        .get("traceparent")
        .and_then(|h| h.to_str().ok())
        .and_then(|s| s.split('-').nth(1))
        .map(str::to_string)
        .unwrap_or_else(|| uuid::Uuid::new_v4().simple().to_string());

    let span_id = uuid::Uuid::new_v4().simple().to_string()[..16].to_string();

    let span = info_span!(
        "request",
        trace_id = %trace_id,
        span_id = %span_id,
        method = %req.method(),
        path = %req.uri().path(),
    );
    let _enter = span.enter();
    next.run(req).await
}
```

## Anti-patterns this template prevents

- `println!("user {} did {}", id, action)` — bypasses tracing entirely.
- `info!("user {} logged in", id)` — interpolates value into message;
  use `info!(user_id = id, "user_logged_in")` so downstream tooling can
  grep by `user_id`.
- Per-request trace_id stored in a `static Mutex` — breaks under async
  concurrency; tracing's span context is the right primitive.
- Forgetting `_enter` — drop happens at end of scope, so a bare
  `span.enter()` is effectively a no-op.

## Testing

`tracing-test` crate or a custom `Writer` capture:

```rust
#[cfg(test)]
mod tests {
    use std::sync::{Arc, Mutex};
    use tracing::info;

    #[derive(Clone)]
    struct CaptureWriter(Arc<Mutex<Vec<u8>>>);
    impl std::io::Write for CaptureWriter {
        fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
            self.0.lock().unwrap().extend_from_slice(buf);
            Ok(buf.len())
        }
        fn flush(&mut self) -> std::io::Result<()> { Ok(()) }
    }

    #[test]
    fn emits_structured_fields() {
        let buf = Arc::new(Mutex::new(Vec::new()));
        let writer = CaptureWriter(Arc::clone(&buf));
        // ...wire writer into a non-global subscriber for the test...
        // assert on JSON shape
    }
}
```

## Why tracing over alternatives

- De-facto standard for structured logging + observability in modern
  Rust (used by tokio, axum, hyper).
- Compatible with OpenTelemetry exporters (`tracing-opentelemetry`) if
  you later wire OTel.
- Async-aware — span context follows `tokio::spawn`ed futures correctly
  via `tracing::Instrument`.

If you use `log` + `env_logger` instead, the spec still applies; the
implementation just looks different. The core discipline (event name +
structured fields, trace context propagation) is library-agnostic.
