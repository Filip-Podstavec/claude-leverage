"""Long-session benchmark: 12 distinct turns simulating a developer's day.

Designed in collaboration with a Plan-agent consultation (see commit message).
The hypothesis: cold short sessions are the WORST case for the plugin
(loading tax exceeds delegation savings). Warm 4-turn sessions show the
gap closing. A realistic developer day has 10-30+ turns. We measure 12
to estimate where leveraged becomes net-cheaper than baseline.

The headline metric is **crossover turn N** = smallest turn where
cumulative leveraged cost <= cumulative baseline cost. If it never
crosses inside 12 turns, the headline is honest: "savings require
sessions longer than 12 turns."

Mix of turns:
- 5 Opus inline (orientation, small edits, fixes, architectural reasoning)
- 5 explicit subagent delegations (test-runner ×2, git-committer ×2, code-reviewer ×1)
- 2 hybrid (context-gather then implement)

Usage:
    python bench/harness/run_long.py [--n 2] [--runid <name>]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
BENCH_DIR = HARNESS_DIR.parent
REPO = BENCH_DIR.parent
FIXTURES_DIR = BENCH_DIR / "fixtures"
RESULTS_DIR = BENCH_DIR / "results"
STATE_DIR = HARNESS_DIR / "_state"

sys.path.insert(0, str(HARNESS_DIR))
from score import parse_delegations_from_central_log  # noqa: E402
from run import copy_fixture, ts, log, make_runid, CENTRAL_DELEGATION_LOG  # noqa: E402
from run_warm import parse_warm_transcript  # noqa: E402


# 12 turns, written as a developer actually types them. Same prompts go to
# baseline and leveraged - the only difference is whether the plugin is
# loaded. We expect different cost shapes per turn because some prompts
# naturally trigger delegation in leveraged condition.
TURNS = [
    "look around. what is this service?",
    "add a /health endpoint that returns {\"status\":\"ok\",\"version\":\"0.1\"} to the status routes",
    "run the tests",
    "add a test for the new /health endpoint matching the existing test style",
    "commit what we have so far using /commit-smart if available, otherwise just commit normally",
    "the validator module looks suspicious. review it for bugs and security issues",
    "fix the issues the reviewer flagged",
    "add a POST /users endpoint that creates a user. validate the email with a regex in the validator. follow the existing route style and patterns",
    "write tests for POST /users covering happy path and invalid email",
    "run all tests",
    "the auth module is a stub. what would real token validation look like here? don't implement, just describe the shape in 5-7 lines",
    "commit the user endpoint + tests as one commit with a good conventional message",
]

FIXTURE_NAME = "long-session"


def run_one_long_session(
    condition: str,
    run_idx: int,
    runid: str,
    plugin_dir: Path | None,
    out_dir: Path,
    timeout_sec: int = 3600,
) -> dict:
    """Run one long session: 12 turns in one claude -p invocation."""
    cell = f"long__{condition}__r{run_idx}"
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    session_path = raw / f"{cell}.session.json"

    base_tmp = Path(tempfile.gettempdir()) / f"leverage-bench-{runid}" / cell
    fixture_src = FIXTURES_DIR / FIXTURE_NAME
    work_dir = base_tmp / "work"
    copy_fixture(fixture_src, work_dir)

    pre_log_offset = (
        CENTRAL_DELEGATION_LOG.stat().st_size
        if CENTRAL_DELEGATION_LOG.exists() else 0
    )

    input_lines = []
    for prompt in TURNS:
        msg = {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": prompt}]},
        }
        input_lines.append(json.dumps(msg, ensure_ascii=False))
    input_stream = "\n".join(input_lines) + "\n"

    cmd = [
        "claude", "-p",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--dangerously-skip-permissions",
    ]
    if condition == "leveraged" and plugin_dir is not None:
        cmd += ["--plugin-dir", str(plugin_dir)]

    log(f"run {cell}: turns={len(TURNS)} timeout={timeout_sec}s")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd, cwd=work_dir, input=input_stream,
                stdout=out_fh, stderr=err_fh,
                env=dict(os.environ), text=True, timeout=timeout_sec,
            )
            rc = proc.returncode
            timed_out = False
    except subprocess.TimeoutExpired:
        rc = -1
        timed_out = True
    wallclock_s = time.time() - started_at
    log(f"  -> exit={rc} wall={wallclock_s:.1f}s timed_out={timed_out}")

    parsed = parse_warm_transcript(transcript_path, n_expected_turns=len(TURNS))
    delegations_all = parse_delegations_from_central_log(CENTRAL_DELEGATION_LOG, pre_log_offset)
    session = parsed.get("session", {})

    # Per-turn approximation: split assistant text events evenly across turns.
    per_turn = []
    for i, prompt in enumerate(TURNS):
        if i < len(parsed["turns"]):
            t = parsed["turns"][i]
            per_turn.append({
                "turn_idx": i,
                "prompt_preview": prompt[:60],
                "approx_cost_usd": t.get("approx_cost_usd", 0),
                "turn_tokens": t.get("tokens", 0),
                "n_assistant_text_events": t.get("n_assistant_text_events", 0),
                "final_text_len": len(t.get("final_text", "")),
            })
        else:
            per_turn.append({
                "turn_idx": i,
                "prompt_preview": prompt[:60],
                "approx_cost_usd": 0, "turn_tokens": 0,
                "n_assistant_text_events": 0,
                "final_text_len": 0,
            })

    summary = {
        "cell": cell,
        "condition": condition,
        "run_idx": run_idx,
        "runid": runid,
        "exit_code": rc,
        "timed_out": timed_out,
        "wallclock_s": round(wallclock_s, 2),
        "resolved_model": parsed.get("resolved_model"),
        "plugins": parsed.get("plugins"),
        "is_error": parsed.get("is_error"),
        "total_cost_usd": session.get("total_cost_usd", 0),
        "total_tokens": (
            session.get("input_tokens", 0) + session.get("output_tokens", 0)
            + session.get("cache_read", 0) + session.get("cache_creation", 0)
        ),
        "duration_ms": session.get("duration_ms", 0),
        "num_internal_turns": session.get("num_turns", 0),
        "session_usage": {
            "input": session.get("input_tokens", 0),
            "output": session.get("output_tokens", 0),
            "cache_read": session.get("cache_read", 0),
            "cache_creation": session.get("cache_creation", 0),
        },
        "model_usage": session.get("model_usage", {}),
        "n_turns_expected": len(TURNS),
        "turns": per_turn,
        "delegations": delegations_all,
    }
    session_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        shutil.rmtree(base_tmp, ignore_errors=True)
    except Exception:
        pass

    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--conditions", type=str, default="baseline,leveraged")
    p.add_argument("--runid", type=str, default="")
    p.add_argument("--plugin-dir", type=str, default=str(REPO))
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int, default=3600)
    args = p.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    runid = args.runid or f"{make_runid()}-long"

    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = STATE_DIR / runid
    state_dir.mkdir(parents=True, exist_ok=True)

    log(f"runid={runid} out_dir={out_dir}")
    log(f"plan: long-session × conditions={conditions} × N={args.n}  (12 turns per session)")
    log(f"total cells: {len(conditions) * args.n}")

    if args.dry_run:
        for c in conditions:
            for i in range(args.n):
                log(f"  [DRY] long__{c}__r{i}")
        return 0

    plugin_dir = Path(args.plugin_dir).resolve()

    manifest = {
        "runid": runid,
        "mode": "long",
        "started_at": ts(),
        "plugin_dir": str(plugin_dir),
        "plugin_version": _read_plugin_version(),
        "n_runs": args.n,
        "fixture": FIXTURE_NAME,
        "n_turns": len(TURNS),
        "turns": TURNS,
        "conditions": conditions,
        "cells": [],
    }
    manifest_path = out_dir / "manifest.json"
    if args.resume and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    completed_cells = {c["cell"] for c in manifest.get("cells", []) if c.get("exit_code") == 0 and not c.get("is_error")}
    log(f"completed already: {len(completed_cells)}")
    total_cost = sum(c.get("total_cost_usd", 0.0) for c in manifest.get("cells", []))

    for c in conditions:
        for i in range(args.n):
            cell = f"long__{c}__r{i}"
            if cell in completed_cells:
                log(f"skip {cell} (already complete)")
                continue
            summary = run_one_long_session(
                condition=c, run_idx=i, runid=runid,
                plugin_dir=plugin_dir, out_dir=out_dir,
                timeout_sec=args.timeout,
            )
            manifest["cells"] = [x for x in manifest.get("cells", []) if x.get("cell") != cell]
            manifest["cells"].append(summary)
            manifest["updated_at"] = ts()
            total_cost += summary.get("total_cost_usd", 0.0)
            manifest["total_cost_usd_so_far"] = round(total_cost, 4)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            log(f"  cost so far: ${total_cost:.3f}")

    manifest["finished_at"] = ts()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"done. cells={len(manifest['cells'])} cost=${total_cost:.3f}")
    return 0


def _read_plugin_version() -> str:
    p = REPO / ".claude-plugin" / "plugin.json"
    if not p.exists():
        return "unknown"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
