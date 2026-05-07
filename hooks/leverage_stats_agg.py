#!/usr/bin/env python3
"""Aggregate claude-leverage stats JSONL into pipe-separated tier breakdown.

Reads the JSONL log and emits one line per tier with counts, token sums,
and duration sums. Used by the /leverage-stats slash command.

Source path: STATS_FILE env var, or ~/.claude/claude-leverage-stats.jsonl by default.

Output format (pipe-separated, one tier per line):
    <tier>|count=N|total=N|input=N|output=N|cread=N|ccreate=N|dur_ms=N

Where:
    cread   = cache_read_input_tokens (~10% cost of fresh input)
    ccreate = cache_creation_input_tokens (full input cost, written to cache)

Missing fields are treated as 0. Old entries (pre-v0.9.0 without token fields)
contribute to count but not to token sums.

This script lives in hooks/ alongside the bash hooks because it consumes
their output. It does NOT execute as a Claude Code hook itself.
"""
import json
import os
import sys
from collections import defaultdict


def main() -> int:
    path = os.environ.get("STATS_FILE") or os.path.expanduser(
        "~/.claude/claude-leverage-stats.jsonl"
    )

    if not os.path.isfile(path):
        return 0

    tiers = defaultdict(
        lambda: {
            "count": 0,
            "total": 0,
            "input": 0,
            "output": 0,
            "cread": 0,
            "ccreate": 0,
            "dur": 0,
        }
    )

    field_map = (
        ("total_tokens", "total"),
        ("input_tokens", "input"),
        ("output_tokens", "output"),
        ("cache_read_input_tokens", "cread"),
        ("cache_creation_input_tokens", "ccreate"),
        ("duration_ms", "dur"),
    )

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                tier = rec.get("tier", "?") or "?"
                tiers[tier]["count"] += 1
                for src, dst in field_map:
                    v = rec.get(src)
                    if isinstance(v, (int, float)):
                        tiers[tier][dst] += v
    except OSError:
        return 0

    for tier in sorted(tiers):
        v = tiers[tier]
        print(
            f"{tier}|count={v['count']}|total={v['total']}|"
            f"input={v['input']}|output={v['output']}|"
            f"cread={v['cread']}|ccreate={v['ccreate']}|dur_ms={v['dur']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
