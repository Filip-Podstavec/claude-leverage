"""Tests for hooks/leverage_stats_agg.py.

The aggregator is the read-side of the telemetry path written by
hooks/track-delegations.sh. It is invoked by the /leverage-stats slash
command and emits a pipe-separated breakdown that downstream tooling
parses. Output format and graceful handling of malformed lines are
load-bearing — these tests pin the contract.

Edge cases pinned here mirror real bugs hit during v0.9.x releases:
    - float-valued token fields (sanitize_int returned empty -> aggregator
      must skip the float silently, not coerce 0.0 into "0")
    - non-string tier (defensive coercion to "?")
    - bool int-subtype trap (True is not 1)
    - invalid JSON line (skip, don't abort)
    - empty / missing stats file (exit 0, no output)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
AGG_SCRIPT = REPO_ROOT / "scripts" / "hooks" / "leverage_stats_agg.py"


def run_agg(stats_path: Path | None) -> tuple[int, str, str]:
    """Invoke the aggregator as a subprocess with STATS_FILE pointing at
    the given path (or unset/nonexistent if path is None or missing).

    Subprocess isolation is deliberate: import-time changes in the script
    would otherwise leak across tests, and we want to exercise the exact
    Python entry point users invoke from the slash command.
    """
    env = os.environ.copy()
    if stats_path is not None:
        env["STATS_FILE"] = str(stats_path)
    else:
        env.pop("STATS_FILE", None)
    result = subprocess.run(
        [sys.executable, str(AGG_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    """Write records as JSONL. One record per line."""
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def parse_line(line: str) -> dict:
    """Parse a single aggregator output line into a dict for assertion.

    Format: <tier>|count=N|total=N|input=N|output=N|cread=N|ccreate=N|dur_ms=N
    """
    parts = line.split("|")
    out = {"tier": parts[0]}
    for kv in parts[1:]:
        k, _, v = kv.partition("=")
        out[k] = int(v)
    return out


# ---------------------------------------------------------------------------
# Empty / missing input
# ---------------------------------------------------------------------------


def test_missing_stats_file_exits_clean(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does-not-exist.jsonl"
    rc, out, _ = run_agg(nonexistent)
    assert rc == 0
    assert out == ""


def test_empty_stats_file_exits_clean(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    rc, out, _ = run_agg(empty)
    assert rc == 0
    assert out == ""


# ---------------------------------------------------------------------------
# Single-record aggregation
# ---------------------------------------------------------------------------


def test_single_complete_record(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [{
        "ts": "2026-05-12T10:00:00Z",
        "subagent": "code-reviewer",
        "tier": "sonnet",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_input_tokens": 8000,
        "cache_creation_input_tokens": 200,
        "total_tokens": 9700,
        "duration_ms": 4500,
    }])
    rc, out, _ = run_agg(f)
    assert rc == 0
    lines = out.strip().splitlines()
    assert len(lines) == 1
    row = parse_line(lines[0])
    assert row == {
        "tier": "sonnet",
        "count": 1,
        "total": 9700,
        "input": 1000,
        "output": 500,
        "cread": 8000,
        "ccreate": 200,
        "dur_ms": 4500,
    }


def test_multiple_records_same_tier_sums(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [
        {"tier": "haiku", "total_tokens": 1000, "input_tokens": 100,
         "output_tokens": 50, "cache_read_input_tokens": 800,
         "cache_creation_input_tokens": 50, "duration_ms": 1200},
        {"tier": "haiku", "total_tokens": 2000, "input_tokens": 200,
         "output_tokens": 100, "cache_read_input_tokens": 1600,
         "cache_creation_input_tokens": 100, "duration_ms": 2400},
    ])
    rc, out, _ = run_agg(f)
    assert rc == 0
    rows = [parse_line(l) for l in out.strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["tier"] == "haiku"
    assert rows[0]["count"] == 2
    assert rows[0]["total"] == 3000
    assert rows[0]["input"] == 300
    assert rows[0]["output"] == 150
    assert rows[0]["cread"] == 2400
    assert rows[0]["ccreate"] == 150
    assert rows[0]["dur_ms"] == 3600


# ---------------------------------------------------------------------------
# Multi-tier ordering
# ---------------------------------------------------------------------------


def test_tiers_sorted_by_count_desc(tmp_path: Path) -> None:
    """Most-used tier first. Stable secondary sort by tier name."""
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [
        {"tier": "sonnet", "total_tokens": 100},
        {"tier": "haiku", "total_tokens": 50},
        {"tier": "haiku", "total_tokens": 50},
        {"tier": "haiku", "total_tokens": 50},
        {"tier": "sonnet", "total_tokens": 100},
    ])
    rc, out, _ = run_agg(f)
    assert rc == 0
    rows = [parse_line(l) for l in out.strip().splitlines()]
    assert [r["tier"] for r in rows] == ["haiku", "sonnet"]


def test_tier_tiebreaker_alphabetical(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [
        {"tier": "sonnet", "total_tokens": 100},
        {"tier": "haiku", "total_tokens": 100},
    ])
    rc, out, _ = run_agg(f)
    rows = [parse_line(l) for l in out.strip().splitlines()]
    # Equal counts -> alphabetical: haiku before sonnet
    assert [r["tier"] for r in rows] == ["haiku", "sonnet"]


# ---------------------------------------------------------------------------
# Robustness: malformed / legacy records
# ---------------------------------------------------------------------------


def test_record_without_token_fields_counts_only(tmp_path: Path) -> None:
    """Pre-v0.9.0 logs only counts. Aggregator must still tally them."""
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [
        {"ts": "2025-01-01T00:00:00Z", "subagent": "code-reviewer", "tier": "sonnet"},
        {"ts": "2025-01-01T00:00:01Z", "subagent": "code-reviewer", "tier": "sonnet"},
    ])
    rc, out, _ = run_agg(f)
    assert rc == 0
    row = parse_line(out.strip().splitlines()[0])
    assert row["count"] == 2
    assert row["total"] == 0
    assert row["input"] == 0


def test_invalid_json_line_skipped(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    f.write_text(
        '{"tier":"sonnet","total_tokens":100}\n'
        "this is not json at all\n"
        '{"tier":"sonnet","total_tokens":200}\n',
        encoding="utf-8",
    )
    rc, out, _ = run_agg(f)
    assert rc == 0
    row = parse_line(out.strip().splitlines()[0])
    assert row["count"] == 2  # malformed line skipped, two valid remain
    assert row["total"] == 300


def test_blank_lines_skipped(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    f.write_text(
        '{"tier":"sonnet","total_tokens":100}\n'
        "\n"
        "   \n"
        '{"tier":"sonnet","total_tokens":200}\n',
        encoding="utf-8",
    )
    rc, out, _ = run_agg(f)
    rows = [parse_line(l) for l in out.strip().splitlines()]
    assert rows[0]["count"] == 2


def test_float_token_value_coerced_to_int(tmp_path: Path) -> None:
    """A float that slipped through (e.g. malformed log writer) must not
    produce 'total=1300.0' in pipe-separated output. Aggregator casts."""
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [{"tier": "sonnet", "total_tokens": 1300.0}])
    rc, out, _ = run_agg(f)
    assert rc == 0
    line = out.strip().splitlines()[0]
    assert "total=1300" in line
    assert "1300.0" not in line


def test_bool_not_treated_as_int(tmp_path: Path) -> None:
    """bool is a subtype of int in Python. The aggregator must reject it
    explicitly so a stray `true`/`false` in a token field doesn't tally as 1/0."""
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [{"tier": "sonnet", "total_tokens": True}])
    rc, out, _ = run_agg(f)
    row = parse_line(out.strip().splitlines()[0])
    assert row["count"] == 1
    assert row["total"] == 0  # True not aggregated


def test_non_string_tier_normalized(tmp_path: Path) -> None:
    """Defensive: a future log writer that emits tier as a non-string
    (list/dict/int) must not garble pipe-separated output."""
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [
        {"tier": 42, "total_tokens": 100},
        {"tier": ["sonnet"], "total_tokens": 200},
    ])
    rc, out, _ = run_agg(f)
    rows = [parse_line(l) for l in out.strip().splitlines()]
    assert len(rows) == 1  # both collapse into "?"
    assert rows[0]["tier"] == "?"
    assert rows[0]["count"] == 2
    assert rows[0]["total"] == 300


def test_null_tier_normalized(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [{"tier": None, "total_tokens": 100}])
    rc, out, _ = run_agg(f)
    row = parse_line(out.strip().splitlines()[0])
    assert row["tier"] == "?"


def test_missing_tier_normalized(tmp_path: Path) -> None:
    f = tmp_path / "stats.jsonl"
    write_jsonl(f, [{"total_tokens": 100}])
    rc, out, _ = run_agg(f)
    row = parse_line(out.strip().splitlines()[0])
    assert row["tier"] == "?"


# ---------------------------------------------------------------------------
# Encoding robustness
# ---------------------------------------------------------------------------


def test_bad_utf8_byte_does_not_kill_aggregation(tmp_path: Path) -> None:
    """A stray non-UTF-8 byte (cp1252 paste, log corruption) must not
    crash the whole run. The bad line is skipped; surrounding lines tally."""
    f = tmp_path / "stats.jsonl"
    payload = (
        b'{"tier":"sonnet","total_tokens":100}\n'
        b'{"tier":"sonnet","total_tokens":\xff\xfe broken}\n'
        b'{"tier":"sonnet","total_tokens":200}\n'
    )
    f.write_bytes(payload)
    rc, out, _ = run_agg(f)
    assert rc == 0
    row = parse_line(out.strip().splitlines()[0])
    assert row["count"] == 2
    assert row["total"] == 300
