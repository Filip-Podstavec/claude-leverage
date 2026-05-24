# tests

Pytest suite for plugin internals. Run locally with:

```bash
pytest tests/ -v
```

CI runs this on every PR and push to main (see `.github/workflows/ci.yml`).

## Coverage

- `test_leverage_stats_agg.py` — pins the contract of
  `scripts/hooks/leverage_stats_agg.py`: output format, tier sorting,
  graceful handling of malformed JSONL, encoding robustness, and
  the specific edge cases that caused v0.9.x patch releases.
- `test_agent_command_frontmatter.py` — structural validation of every
  agent and command file shipped at the top level (frontmatter shape,
  required fields, filename/name parity, no duplicate names).
