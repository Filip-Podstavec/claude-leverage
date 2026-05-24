# claude-leverage v0.11.0 — long-session benchmark (2026-05-24_v0.11.0-long-opus47)

- Plugin version: **v0.11.0**
- Turns per session: **12**
- N runs per condition: **2**
- Total cost (subscription): **$3.236**

## Headline

**No crossover in 12 turns.** By turn 12, leveraged is still **$0.596 more expensive** than baseline ($1.107 vs $0.511, +117%).

To estimate when leveraged might cross over, look at the *last-half slope*: in turns 7–12, the gap changed by $+0.264. If the trend is the leveraged gap shrinking, extrapolation gives a crossover at ~turn N (calculation below).

![cumulative](cumulative.png)

![per-turn](per-turn.png)

## Per-turn detail (median across N runs)

| Turn | Prompt (preview) | Baseline cost | Leveraged cost | Cumulative B | Cumulative L | Δ cumulative |
|---:|---|---:|---:|---:|---:|---:|
| 1 | look around. what is this service? | $0.026 | $0.078 | $0.026 | $0.078 | +$0.052 |
| 2 | add a /health endpoint that returns {"status":"ok","ver… | $0.026 | $0.080 | $0.051 | $0.158 | +$0.107 |
| 3 | run the tests | $0.026 | $0.079 | $0.078 | $0.237 | +$0.160 |
| 4 | add a test for the new /health endpoint matching the ex… | $0.027 | $0.062 | $0.104 | $0.299 | +$0.195 |
| 5 | commit what we have so far using /commit-smart if avail… | $0.027 | $0.089 | $0.131 | $0.389 | +$0.258 |
| 6 | the validator module looks suspicious. review it for bu… | $0.028 | $0.103 | $0.159 | $0.492 | +$0.332 |
| 7 | fix the issues the reviewer flagged | $0.029 | $0.046 | $0.189 | $0.538 | +$0.349 |
| 8 | add a POST /users endpoint that creates a user. validat… | $0.030 | $0.079 | $0.219 | $0.617 | +$0.398 |
| 9 | write tests for POST /users covering happy path and inv… | $0.032 | $0.081 | $0.251 | $0.698 | +$0.448 |
| 10 | run all tests | $0.033 | $0.100 | $0.284 | $0.798 | +$0.515 |
| 11 | the auth module is a stub. what would real token valida… | $0.034 | $0.081 | $0.318 | $0.879 | +$0.561 |
| 12 | commit the user endpoint + tests as one commit with a g… | $0.193 | $0.228 | $0.511 | $1.107 | +$0.596 |

## Delegations observed (leveraged)

- `claude-leverage:test-runner` — 5 invocation(s) across all leveraged runs
- `claude-leverage:code-reviewer` — 3 invocation(s) across all leveraged runs
- `claude-leverage:git-committer` — 1 invocation(s) across all leveraged runs

## Methodology

- ONE `claude -p --input-format stream-json` session per cell, 12 user turns sent sequentially. Same `bench/fixtures/long-session/` cwd for all turns (Claude Code cannot change cwd mid-session).
- Turns mix: 5 Opus-inline (orientation, small edits, fixes, architectural), 5 explicit subagent delegations (`test-runner`×2, `git-committer`×2, `code-reviewer`×1), 2 hybrid (context-gather + implement).
- Cost is `result.total_cost_usd` from the final stream-json `result` event (cumulative across all turns). Per-turn approximation: total cost split proportionally to per-assistant-event token volume — exact when each turn produces one final-text event, approximate when multi-step turns (e.g. commits with multiple bash calls) produce several text events.
- Crossover detection: 1-indexed turn `N` where `cumulative_lev[N] <= cumulative_base[N]`.
