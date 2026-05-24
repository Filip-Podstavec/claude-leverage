"""Audit whether the 4 agents moved to extras/ are actually net-negative
on their target use cases under the current Claude Code default model.

We moved them based on intuition (CC built-ins cover them / low frequency)
without measuring. After observing on T2 that our context-gatherer (Haiku)
substantially beat baseline-Explore (also Haiku) on a structured task —
89k tokens vs 322k — the same MIGHT be true for repo-explorer and
research-agent. This script measures it.

Tests:
  E1 repo-explorer-task:  "List every file that imports requireAuth.
                           Just file paths, no explanations."
  E2 research-agent-task: "How does the auth flow work end to end:
                           request → require_auth → route handler?
                           Trace the actual code paths."
  E3 docs-updater-task:   (skipped — no built-in equivalent; the agent
                           wins by default if it works at all)
  E4 flaky-test-task:     (skipped — no built-in equivalent)

For E1 and E2 we measure three conditions:
  - baseline:    vanilla Claude Code (CC built-ins Explore, general-purpose available)
  - leveraged:   current default plugin (no extras loaded)
  - extras-on:   plugin + ONE extras agent at a time copied into agents/ for the run

If `extras-on` beats both baseline AND leveraged, the agent was moved
unfairly and should come back. If it costs ≥ baseline, the move was correct.

Usage:
    python bench/harness/audit_extras.py [--n 3] [--runid <name>]
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
from statistics import median

HARNESS_DIR = Path(__file__).resolve().parent
BENCH_DIR = HARNESS_DIR.parent
REPO = BENCH_DIR.parent
FIXTURES_DIR = BENCH_DIR / "fixtures"
RESULTS_DIR = BENCH_DIR / "results"

sys.path.insert(0, str(HARNESS_DIR))
from score import parse_transcript  # noqa: E402
from run import copy_fixture, ts, log  # noqa: E402


# We reuse the warm-session fixture (small Python service with require_auth +
# /status route + /users route) — it's the same shape both agents care about.
FIXTURE_NAME = "warm-session"

TASKS = [
    {
        "id": "E1.repo-explorer",
        "extras_agent": "repo-explorer.md",
        "prompt": (
            "List every file in this repo that uses the `require_auth` decorator. "
            "Just file paths with one-line context for each, no architectural "
            "discussion, no recommendations. If the same file uses it multiple "
            "times, mention it once."
        ),
        # Quality check: output must mention status.py + users.py (both files use require_auth)
        "expected_substrings": ["status.py", "users.py"],
    },
    {
        "id": "E2.research-agent",
        "extras_agent": "research-agent.md",
        "prompt": (
            "Explain how the authentication flow works end-to-end in this codebase. "
            "Trace the path: a request comes in, hits a route handler, the "
            "require_auth decorator checks something, and the handler runs or "
            "returns 401. Be specific about which files do what."
        ),
        "expected_substrings": ["require_auth", "auth.py", "Authorization"],
    },
]


def _build_plugin_dir_with_extra(extra_agent_filename: str | None) -> Path:
    """Return a path that can be passed to --plugin-dir.

    If extra_agent_filename is None, returns the repo path as-is.
    Otherwise creates a temp copy of the repo where the named extras agent
    is also placed in agents/ — simulating "plugin + this one extras
    agent installed at user scope".
    """
    if extra_agent_filename is None:
        return REPO
    tmp_plugin = Path(tempfile.gettempdir()) / f"leverage-audit-plugin-{extra_agent_filename}"
    if tmp_plugin.exists():
        shutil.rmtree(tmp_plugin, ignore_errors=True)
    shutil.copytree(REPO, tmp_plugin, ignore=shutil.ignore_patterns("bench", ".git", "node_modules", "__pycache__"))
    src = REPO / "extras" / "agents" / extra_agent_filename
    dst = tmp_plugin / "agents" / extra_agent_filename
    shutil.copy2(src, dst)
    return tmp_plugin


def run_one(task: dict, condition: str, run_idx: int, runid: str, out_dir: Path) -> dict:
    """Run a single (task × condition × run) cell.

    condition is one of: baseline, leveraged, extras-on
    """
    cell = f"{task['id']}__{condition}__r{run_idx}"
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    session_path = raw / f"{cell}.session.json"

    base_tmp = Path(tempfile.gettempdir()) / f"leverage-audit-{runid}" / cell
    fixture_src = FIXTURES_DIR / FIXTURE_NAME
    work_dir = base_tmp / "work"
    copy_fixture(fixture_src, work_dir)

    cmd = [
        "claude", "-p",
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--dangerously-skip-permissions",
    ]
    if condition == "leveraged":
        cmd += ["--plugin-dir", str(REPO)]
    elif condition == "extras-on":
        plugin_dir = _build_plugin_dir_with_extra(task["extras_agent"])
        cmd += ["--plugin-dir", str(plugin_dir)]

    log(f"run {cell}")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd, cwd=work_dir, input=task["prompt"],
                stdout=out_fh, stderr=err_fh,
                env=dict(os.environ), text=True, timeout=900,
            )
            rc = proc.returncode
            timed_out = False
    except subprocess.TimeoutExpired:
        rc = -1
        timed_out = True
    wallclock_s = time.time() - started_at

    score = parse_transcript(transcript_path)
    quality_pass = all(
        sub.lower() in score.final_text.lower()
        for sub in task["expected_substrings"]
    )
    log(f"  -> exit={rc} cost=${score.total_cost_usd:.3f} tokens={score.total_tokens} pass={quality_pass}")

    summary = {
        "cell": cell,
        "task": task["id"],
        "condition": condition,
        "run_idx": run_idx,
        "exit_code": rc,
        "timed_out": timed_out,
        "wallclock_s": round(wallclock_s, 2),
        "total_cost_usd": score.total_cost_usd,
        "total_tokens": score.total_tokens,
        "tokens": {
            "input": score.input_tokens,
            "output": score.output_tokens,
            "cache_read": score.cache_read,
            "cache_creation": score.cache_creation,
        },
        "model_usage": score.model_usage,
        "quality_pass": quality_pass,
        "final_text_len": len(score.final_text),
    }
    session_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    try:
        shutil.rmtree(base_tmp, ignore_errors=True)
    except Exception:
        pass
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--runid", type=str, default="")
    args = p.parse_args()

    runid = args.runid or f"audit-extras-{ts()[:10]}"
    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"runid={runid} out_dir={out_dir}")
    cells: list[dict] = []
    for task in TASKS:
        for cond in ["baseline", "leveraged", "extras-on"]:
            for i in range(args.n):
                s = run_one(task, cond, i, runid, out_dir)
                cells.append(s)

    # Aggregate and print summary.
    print()
    print("=== AUDIT SUMMARY ===")
    print(f"{'Task':25s} {'Condition':12s} {'Median cost':>12s} {'Range':>20s} {'Quality':>10s}")
    print("-" * 85)
    for task in TASKS:
        for cond in ["baseline", "leveraged", "extras-on"]:
            subset = [c for c in cells if c["task"] == task["id"] and c["condition"] == cond and not c.get("timed_out") and c.get("exit_code") == 0]
            if not subset:
                continue
            costs = [c["total_cost_usd"] for c in subset]
            q = sum(c["quality_pass"] for c in subset)
            print(f"{task['id']:25s} {cond:12s} ${median(costs):>10.3f} ${min(costs):>7.3f}-${max(costs):>7.3f} {q}/{len(subset):>6}")
        # Verdict for this task
        bl = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "baseline" and c.get("exit_code") == 0]
        lv = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "leveraged" and c.get("exit_code") == 0]
        ex = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "extras-on" and c.get("exit_code") == 0]
        if bl and lv and ex:
            bl_m, lv_m, ex_m = median(bl), median(lv), median(ex)
            verdict = ""
            if ex_m < bl_m and ex_m < lv_m:
                verdict = "BRING BACK — extras-on cheapest"
            elif ex_m >= bl_m:
                verdict = "KEEP IN EXTRAS — no advantage over baseline"
            else:
                verdict = "ambiguous — beats leveraged but not baseline"
            print(f"  -> verdict: {verdict}")
        print()

    # Save manifest.
    manifest = {
        "runid": runid,
        "n_runs": args.n,
        "fixture": FIXTURE_NAME,
        "tasks": [t["id"] for t in TASKS],
        "cells": cells,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"manifest written: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
