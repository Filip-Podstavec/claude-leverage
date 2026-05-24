"""Audit default agents (code-reviewer, test-runner) vs baseline.

The original benchmarks measured "leveraged with all agents loaded" against
baseline, but never isolated whether the agents themselves are doing work or
whether the plugin is just paying tax with no behavioral change. This script
does the isolation:

For each default agent we care about:
  baseline:       no plugin, Opus does the task inline
  leveraged-natural: plugin loaded, prompt is realistic (doesn't force agent use)
  leveraged-forced:  plugin loaded, prompt explicitly invokes the subagent

If leveraged-forced wins vs baseline, the agent has real value when used.
If leveraged-natural wins vs baseline, the agent gets picked up automatically.
If both lose, the agent isn't earning its keep even at best case.

Uses warm-session fixture (Python service with staged SQL-injection diff).
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

FIXTURE_NAME = "warm-session"

# Each task defines a baseline prompt, leveraged-natural prompt (often same as
# baseline), and leveraged-forced prompt (explicitly invokes the subagent).
# Quality check is substrings that must all appear in the final output.
TASKS = [
    {
        "id": "A.test-runner",
        "baseline_prompt": "Run python -m pytest tests/ -v and tell me which tests pass and which fail. Give me a structured per-test summary.",
        "leveraged_natural_prompt": "Run python -m pytest tests/ -v and tell me which tests pass and which fail. Give me a structured per-test summary.",
        "leveraged_forced_prompt": "Use the test-runner subagent to run python -m pytest tests/ -v and give me a structured per-test summary.",
        "expected_substrings": ["test_status", "test_users"],
    },
    {
        "id": "C.code-reviewer",
        "baseline_prompt": "Review the staged changes (git diff --cached) for bugs, security issues, and quality problems. Organize findings by severity (Critical, Important, Nice to have). Be specific - file and line number.",
        "leveraged_natural_prompt": "Review the staged changes (git diff --cached) for bugs, security issues, and quality problems. Organize findings by severity (Critical, Important, Nice to have). Be specific - file and line number.",
        "leveraged_forced_prompt": "Use the code-reviewer subagent to review the staged changes (git diff --cached). Critical/Important/Nice to have format.",
        "expected_substrings": ["users.py", "Critical"],
    },
]


def run_one(task: dict, condition: str, run_idx: int, runid: str, out_dir: Path) -> dict:
    cell = f"{task['id']}__{condition}__r{run_idx}"
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    session_path = raw / f"{cell}.session.json"

    base_tmp = Path(tempfile.gettempdir()) / f"leverage-audit-default-{runid}" / cell
    fixture_src = FIXTURES_DIR / FIXTURE_NAME
    work_dir = base_tmp / "work"
    copy_fixture(fixture_src, work_dir)

    if condition == "baseline":
        prompt = task["baseline_prompt"]
        plugin = False
    elif condition == "leveraged-natural":
        prompt = task["leveraged_natural_prompt"]
        plugin = True
    elif condition == "leveraged-forced":
        prompt = task["leveraged_forced_prompt"]
        plugin = True
    else:
        raise ValueError(f"unknown condition: {condition}")

    cmd = [
        "claude", "-p",
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--dangerously-skip-permissions",
    ]
    if plugin:
        cmd += ["--plugin-dir", str(REPO)]

    log(f"run {cell}")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd, cwd=work_dir, input=prompt,
                stdout=out_fh, stderr=err_fh,
                env=dict(os.environ), text=True, timeout=900,
            )
            rc = proc.returncode
            timed_out = False
    except subprocess.TimeoutExpired:
        rc, timed_out = -1, True
    wallclock_s = time.time() - started_at

    score = parse_transcript(transcript_path)
    quality_pass = all(
        sub.lower() in score.final_text.lower() for sub in task["expected_substrings"]
    )
    log(f"  -> exit={rc} cost=${score.total_cost_usd:.3f} tokens={score.total_tokens} pass={quality_pass}")

    summary = {
        "cell": cell, "task": task["id"], "condition": condition,
        "run_idx": run_idx, "exit_code": rc, "timed_out": timed_out,
        "wallclock_s": round(wallclock_s, 2),
        "total_cost_usd": score.total_cost_usd,
        "total_tokens": score.total_tokens,
        "tokens": {
            "input": score.input_tokens, "output": score.output_tokens,
            "cache_read": score.cache_read, "cache_creation": score.cache_creation,
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
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--runid", type=str, default="")
    args = p.parse_args()

    runid = args.runid or f"audit-default-{ts()[:10]}"
    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"runid={runid}")

    cells: list[dict] = []
    for task in TASKS:
        for cond in ["baseline", "leveraged-natural", "leveraged-forced"]:
            for i in range(args.n):
                s = run_one(task, cond, i, runid, out_dir)
                cells.append(s)

    print()
    print("=== AUDIT SUMMARY ===")
    print(f"{'Task':22s} {'Condition':22s} {'Median cost':>13s} {'Range':>22s} {'Quality':>10s}")
    print("-" * 95)
    for task in TASKS:
        for cond in ["baseline", "leveraged-natural", "leveraged-forced"]:
            subset = [c for c in cells if c["task"] == task["id"] and c["condition"] == cond and not c.get("timed_out") and c.get("exit_code") == 0]
            if not subset:
                continue
            costs = [c["total_cost_usd"] for c in subset]
            q = sum(c["quality_pass"] for c in subset)
            print(f"{task['id']:22s} {cond:22s} ${median(costs):>11.3f} ${min(costs):>7.3f}-${max(costs):>7.3f} {q}/{len(subset):>6}")
        bl = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "baseline" and c.get("exit_code") == 0]
        nat = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "leveraged-natural" and c.get("exit_code") == 0]
        forced = [c["total_cost_usd"] for c in cells if c["task"] == task["id"] and c["condition"] == "leveraged-forced" and c.get("exit_code") == 0]
        if bl and nat and forced:
            bl_m, nat_m, forced_m = median(bl), median(nat), median(forced)
            if forced_m < bl_m:
                verdict = f"AGENT WINS WHEN FORCED — saves {(bl_m-forced_m)/bl_m*100:.0f}% vs baseline"
            elif forced_m > bl_m:
                verdict = f"AGENT LOSES EVEN WHEN FORCED — costs {(forced_m-bl_m)/bl_m*100:.0f}% MORE than baseline"
            else:
                verdict = "neutral"
            print(f"  -> {verdict}")
            if nat_m < bl_m:
                print(f"  -> natural-leveraged also saves {(bl_m-nat_m)/bl_m*100:.0f}% vs baseline (Opus delegated automatically)")
            elif nat_m > bl_m + 0.005:
                print(f"  -> natural-leveraged costs {(nat_m-bl_m)/bl_m*100:.0f}% more (Opus didn't delegate, just paid plugin tax)")
        print()

    manifest = {
        "runid": runid, "n_runs": args.n, "fixture": FIXTURE_NAME,
        "tasks": [t["id"] for t in TASKS], "cells": cells,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"manifest: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
