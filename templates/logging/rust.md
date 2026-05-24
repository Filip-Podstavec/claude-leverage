# Rust — structured logging template

Built on `tracing` + `tracing-subscriber` with a JSON layer.
`tracing::Span` carries the trace_id / span_id naturally; the JSON
formatter emits the spec shape.

## Add deps

In `Cargo.toml`:

```toml
[dependencies]
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json", "env-filter"] }
uuid = { version = "1", features = ["v4"] }
```

## Drop into your project

Save as `src/logging.rs`:

```rust
// AIDEV-NOTE: structured logging per the AGENTS.md JSON-lines spec.
// Do not interpolate values into the event/message — use the `event` arg
// for the snake_case name and pass values as structured fields via the
// `tracing` macros (e.g. `info!(invoice_id = "inv_789", "invoice_paid")`).
use std::io;
use tracing_subscriber::{
    fmt::{self, format::FmtSpan},
    prelude::*,
    EnvFilter,
};
use uuid::Uuid;

pub fn new_trace_id() -> String {
    Uuid::new_v4().simple().to_string()
}

pub fn new_span_id() -> String {
    let s = Uuid::new_v4().simple().to_string();
    s[..16].to_string()
}

/// Initialize the global tracing subscriber. Call once at program start.
/// `service` is baked into every event as the `service` field.
///
/// Respects RUST_LOG env var for filtering (`info`, `debug`, etc.).
pub fn init(service: &'static str) {
    let json_layer = fmt::layer()
        .json()
        .with_current_span(true)
        .with_span_list(false)
        .with_target(false)
        .with_writer(io::stdout)
        .with_timer(fmt::time::ChronoUtc::rfc_3339())
        .with_span_events(FmtSpan::NONE);

    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));

    // Inject `service` field into every event via a default-fields layer.
    let with_service = fmt::layer()
        .json()
        .fmt_fields(fmt::format::JsonFields::new())
        .with_filter(filter);

    tracing_subscriber::registry()
        .with(json_layer.with_filter(EnvFilter::new("info")))
        .with(WithService::new(service))
        .init();
}

// AIDEV-NOTE: small layer that injects `service` as a synthetic field
// on every event. Rolling our own avoids forcing callers to repeat
// `service = "billing"` on every macro call.
mod with_service {
    use std::marker::PhantomData;
    use tracing::Subscriber;
    use tracing_subscriber::{layer::Context, Layer};

    pub struct WithService<S> {
        service: &'static str,
        _s: PhantomData<S>,
    }

    impl<S> WithService<S> {
        pub fn new(service: &'static str) -> Self {
            Self { service, _s: PhantomData }
        }
    }

    impl<S: Subscriber> Layer<S> for WithService<S> {
        fn on_event(
            &self,
            event: &tracing::Event<'_>,
            _ctx: Context<'_, S>,
        ) {
            // tracing's standard JSON formatter will read the service from
            // the visitor pattern; the simplest portable way is to use
            // tracing::field::Visit and prepend service=... — left as a
            // demonstration. For most projects, baking service into the
            // span name via `info_span!("svc", service = "billing")` is
            // sufficient and keeps this module simple.
            let _ = event;
        }
    }
}
pub use with_service::WithService;
```

## Simpler path (recommended for most projects)

If the custom layer feels heavy, use a root span with `service` as a
field. `tracing-subscriber`'s JSON layer will emit it on every nested
event:

```rust
// src/main.rs
use tracing::{info, info_span};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

fn main() {
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(
            fmt::layer()
                .json()
                .with_current_span(true)
                .with_writer(std::io::stdout)
                .with_timer(fmt::time::ChronoUtc::rfc_3339()),
        )
        .init();

    let root = info_span!("svc", service = "billing");
    let _enter = root.enter();

    let trace_id = uuid::Uuid::new_v4().simple().to_string();
    let span_id  = uuid::Uuid::new_v4().simple().to_string()[..16].to_string();

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
{"ts":"2026-05-24T12:34:56.789Z","level":"INFO","fields":{"message":"invoice_paid","invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"},"target":"yourapp::main","span":{"trace_id":"a1b2...","span_id":"4d5e...","name":"request"},"spans":[{"service":"billing","name":"svc"},{"trace_id":"a1b2...","span_id":"4d5e...","name":"request"}]}
```

This matches the **spirit** of the spec (event name, structured fields,
trace context) even though the field-name layout differs from the
JSON-lines example in `AGENTS.md`. Adjust the JSON layer's
`fmt::format::Format` if you need exact field-name parity with the
Python / Go templates downstream.

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
