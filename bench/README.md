# bench/

Two evaluation suites live here:

- [`eval/`](eval/) — **current** A/B benchmark behind the headline numbers
  in the top-level README. Endpoint-implementation task on a real client
  codebase, four Opus 4.7 runs plus one Sonnet 4.6 run on a different task
  type. Plot script + methodology + generated chart.
- [`archive-token-savings-thesis/`](archive-token-savings-thesis/) —
  **archived** harness from the v0.x token-savings hypothesis that
  motivated the v1.0.0 pivot. Frozen: raw data, charts, retired agents
  stay as honest evidence of what was tested. Referenced from the top-
  level README's "Honest history" section.

To reproduce the archived experiment see
[`archive-token-savings-thesis/HOWTO.md`](archive-token-savings-thesis/HOWTO.md).
To reproduce the current one see [`eval/README.md`](eval/README.md).
