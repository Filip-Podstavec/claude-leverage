# tests

Pytest suite for plugin internals. Run locally with:

```bash
pytest tests/ -v
```

CI runs this on every PR and push to main (see `.github/workflows/ci.yml`).

## Coverage

- `test_leverage_stats_agg.py` — pins the contract of
  `hooks/leverage_stats_agg.py`: output format, tier sorting,
  graceful handling of malformed JSONL, encoding robustness, and
  the specific edge cases that caused v0.9.x patch releases.
