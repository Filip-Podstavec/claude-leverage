# Go — structured logging template

Built on `log/slog` (stdlib since Go 1.21). No third-party deps.
`context` carries the trace_id / span_id; a tiny middleware injects
them into every event.

## Drop into your project

Save as `internal/logging/logging.go`:

```go
// AIDEV-NOTE: structured logging per the AGENTS.md JSON-lines spec.
// Do not interpolate values into the message arg — pass them as
// key-value pairs after the message (slog idiom).
package logging

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"log/slog"
	"os"
)

// traceCtxKey is unexported so callers must use the helpers below.
type traceCtxKey struct{}

type Trace struct {
	TraceID string
	SpanID  string
}

func NewTraceID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func NewSpanID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// WithTrace returns a context carrying the given trace.
func WithTrace(parent context.Context, t Trace) context.Context {
	return context.WithValue(parent, traceCtxKey{}, t)
}

// TraceFrom extracts the trace from context, returning empty values if absent.
func TraceFrom(ctx context.Context) Trace {
	if v, ok := ctx.Value(traceCtxKey{}).(Trace); ok {
		return v
	}
	return Trace{}
}

// New returns a slog.Logger configured with the spec's JSON shape and
// service-name baked in. Call once per service / module.
//
// Use the *Ctx wrapper methods below for log calls so trace fields are
// injected from context. Plain slog calls also work but won't include
// trace.
type Logger struct {
	*slog.Logger
	service string
}

// AIDEV-NOTE: ReplaceAttr fires for every record AND every key inside;
// our keys "ts" / "service" / "event" map slog's defaults (time / level
// is renamed via output key, etc.). The handler is doing one allocation
// per record — fine for production rates of ~10k req/sec; profile if
// you push higher.
func New(service string, w io.Writer) *Logger {
	if w == nil {
		w = os.Stdout
	}
	handler := slog.NewJSONHandler(w, &slog.HandlerOptions{
		Level: slog.LevelInfo,
		ReplaceAttr: func(_ []string, a slog.Attr) slog.Attr {
			switch a.Key {
			case slog.TimeKey:
				return slog.Attr{Key: "ts", Value: a.Value}
			case slog.MessageKey:
				return slog.Attr{Key: "event", Value: a.Value}
			case slog.LevelKey:
				return slog.Attr{Key: "level", Value: slog.StringValue(a.Value.String())}
			}
			return a
		},
	})
	base := slog.New(handler).With("service", service)
	return &Logger{Logger: base, service: service}
}

// InfoCtx logs at info level, injecting trace/span ids from context.
// First arg AFTER the event must be paired (key, value) — see attrs below.
func (l *Logger) InfoCtx(ctx context.Context, event string, attrs ...any) {
	l.Logger.With(traceFields(ctx)...).Info(event, attrs...)
}

func (l *Logger) WarnCtx(ctx context.Context, event string, attrs ...any) {
	l.Logger.With(traceFields(ctx)...).Warn(event, attrs...)
}

func (l *Logger) ErrorCtx(ctx context.Context, event string, attrs ...any) {
	l.Logger.With(traceFields(ctx)...).Error(event, attrs...)
}

func (l *Logger) DebugCtx(ctx context.Context, event string, attrs ...any) {
	l.Logger.With(traceFields(ctx)...).Debug(event, attrs...)
}

func traceFields(ctx context.Context) []any {
	t := TraceFrom(ctx)
	return []any{"trace_id", t.TraceID, "span_id", t.SpanID}
}
```

## First call

```go
package main

import (
	"context"
	"net/http"
	"yourapp/internal/logging"
)

func main() {
	logger := logging.New("billing", nil)

	ctx := logging.WithTrace(context.Background(), logging.Trace{
		TraceID: logging.NewTraceID(),
		SpanID:  logging.NewSpanID(),
	})

	logger.InfoCtx(ctx, "invoice_paid",
		"invoice_id", "inv_789",
		"amount_cents", 4900,
		"currency", "EUR",
	)
}
```

Output:

```json
{"ts":"2026-05-24T12:34:56.789Z","level":"INFO","event":"invoice_paid","service":"billing","trace_id":"a1b2...","span_id":"4d5e...","invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"}
```

Note slog flattens `attrs` into top-level fields. If you want a nested
`attrs` object specifically (matching the spec example exactly), wrap
via `slog.Group("attrs", ...)`:

```go
logger.InfoCtx(ctx, "invoice_paid",
	slog.Group("attrs",
		"invoice_id", "inv_789",
		"amount_cents", 4900,
		"currency", "EUR",
	),
)
```

That emits:

```json
{"ts":"...","level":"INFO","event":"invoice_paid","service":"billing","trace_id":"...","span_id":"...","attrs":{"invoice_id":"inv_789","amount_cents":4900,"currency":"EUR"}}
```

Pick whichever shape downstream tooling expects. Spec is agnostic about
flat-vs-nested; what matters is no string interpolation into `event`.

## HTTP middleware

```go
func TraceMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t := logging.Trace{
			TraceID: logging.NewTraceID(),
			SpanID:  logging.NewSpanID(),
		}
		if incoming := r.Header.Get("traceparent"); incoming != "" {
			parts := strings.Split(incoming, "-")
			if len(parts) >= 4 {
				t.TraceID = parts[1]
				// Always a fresh child span — never reuse parent's span id.
			}
		}
		ctx := logging.WithTrace(r.Context(), t)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
```

## Anti-patterns this template prevents

- `log.Printf("user %d did %s", id, action)` — value in message;
  instead `logger.InfoCtx(ctx, "user_action", "user_id", id, "action", action)`.
- `fmt.Println` calls in services — bypass JSON, bypass level filtering.
- Storing trace_id on a global var — breaks under concurrent requests;
  use `context.Context` (the Go primitive for request-scoped values).
- Passing structs as a single attr key — slog will render them
  reasonably but they're not grep-friendly; flatten the few fields
  that matter.

## Testing

```go
func TestLoggerEmitsSpecFields(t *testing.T) {
	var buf bytes.Buffer
	logger := logging.New("test_svc", &buf)
	ctx := logging.WithTrace(context.Background(), logging.Trace{
		TraceID: "tid",
		SpanID:  "sid",
	})

	logger.InfoCtx(ctx, "test_event", "k", "v")

	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if rec["event"] != "test_event" {
		t.Errorf("event=%v want test_event", rec["event"])
	}
	if rec["service"] != "test_svc" {
		t.Errorf("service=%v want test_svc", rec["service"])
	}
	if rec["trace_id"] != "tid" {
		t.Errorf("trace_id=%v want tid", rec["trace_id"])
	}
	if rec["k"] != "v" {
		t.Errorf("attr k=%v want v", rec["k"])
	}
}
```

## Why slog over zap / zerolog

- Standard library since Go 1.21 — no external dep.
- The handler abstraction makes swapping output / format trivial later.
- API is unchanged across Go versions.

If you already use zap or zerolog, adapt the field-name mapping above
to your handler — the spec is what matters, the library is incidental.
