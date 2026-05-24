"""Test "pass less + constrain output" design pattern against verbose-subagent baseline.

Tests three conditions on the code-review-large fixture (281 LOC, 7 files):

  baseline:        Opus inline does the whole review (no plugin)
  forced-reviewer: plugin + extras/agents/code-reviewer.md — Opus dispatches to
                   the verbose code-reviewer that reads files itself
  forced-focused:  plugin + agents/focused-reviewer.md — Opus extracts the
                   diff body inline (cheap, cached in main session) and PASSES
                   it to focused-reviewer which doesn't re-read and is
                   capped at 500-token output

Hypothesis: forced-focused beats baseline by passing pre-extracted snippets
(small subagent cache_creation) and constraining output (Sonnet stops
being 2x more verbose than Opus).
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

FIXTURE_NAME = "code-review-large"

PROMPTS = {
    "baseline": (
        "Review the staged changes (`git diff --cached`) for bugs, security issues, "
        "race conditions, and quality problems. This is a substantial refactor across "
        "multiple modules. Organize findings by severity (Critical, Important, Nice to "
        "have). Be specific — file and line number for each."
    ),
    "forced-reviewer": (
        "Use the code-reviewer subagent to review the staged changes (`git diff --cached`). "
        "This is a substantial refactor across multiple modules. Return its Critical/"
        "Important/Nice-to-have findings as-is."
    ),
    "forced-focused": (
        "Do this in two steps:\n"
        "1. Run `git diff --cached` yourself to get the diff text.\n"
        "2. Pass the diff body verbatim to the focused-reviewer subagent in the prompt, "
        "with a one-line instruction asking it to flag Critical/Important/Nice issues. "
        "Do NOT just say 'review the staged diff' — paste the actual diff content into "
        "the subagent's prompt so it does not need to re-read files.\n"
        "Return its findings as-is."
    ),
}

EXPECTED = ["tasks.py"]


def run_one(condition: str, run_idx: int, runid: str, out_dir: Path) -> dict:
    cell = f"focused__{condition}__r{run_idx}"
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    session_path = raw / f"{cell}.session.json"

    base_tmp = Path(tempfile.gettempdir()) / f"leverage-focused-{runid}" / cell
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
    # baseline = no plugin. Others = plugin loaded.
    if condition != "baseline":
        cmd += ["--plugin-dir", str(REPO)]

    log(f"run {cell}")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd, cwd=work_dir, input=PROMPTS[condition],
                stdout=out_fh, stderr=err_fh,
                env=dict(os.environ), text=True, timeout=900,
            )
            rc = proc.returncode
            timed_out = False
    except subprocess.TimeoutExpired:
        rc, timed_out = -1, True
    wallclock_s = time.time() - started_at

    score = parse_transcript(transcript_path)
    quality_pass = all(s.lower() in score.final_text.lower() for s in EXPECTED)
    log(f"  -> exit={rc} cost=${score.total_cost_usd:.3f} tokens={score.total_tokens} output_text={score.output_tokens} pass={quality_pass}")

    summary = {
        "cell": cell, "condition": condition, "run_idx": run_idx,
        "exit_code": rc, "timed_out": timed_out,
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

    runid = args.runid or f"audit-focused-{ts()[:10]}"
    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"runid={runid}")

    cells: list[dict] = []
    for cond in ["baseline", "forced-reviewer", "forced-focused"]:
        for i in range(args.n):
            cells.append(run_one(cond, i, runid, out_dir))

    print()
    print("=== FOCUSED-REVIEWER AUDIT ===")
    print(f"{'Condition':22s} {'Median cost':>13s} {'Range':>22s} {'Output toks (median)':>22s} {'Quality':>10s}")
    print("-" * 105)
    for cond in ["baseline", "forced-reviewer", "forced-focused"]:
        subset = [c for c in cells if c["condition"] == cond and c.get("exit_code") == 0]
        if not subset:
            continue
        costs = [c["total_cost_usd"] for c in subset]
        out_toks = [c["tokens"]["output"] for c in subset]
        q = sum(c["quality_pass"] for c in subset)
        print(f"{cond:22s} ${median(costs):>11.3f} ${min(costs):>7.3f}-${max(costs):>7.3f} {median(out_toks):>22.0f} {q}/{len(subset):>6}")
    bl = [c["total_cost_usd"] for c in cells if c["condition"] == "baseline" and c.get("exit_code") == 0]
    fr = [c["total_cost_usd"] for c in cells if c["condition"] == "forced-reviewer" and c.get("exit_code") == 0]
    ff = [c["total_cost_usd"] for c in cells if c["condition"] == "forced-focused" and c.get("exit_code") == 0]
    if bl and ff:
        bl_m, ff_m = median(bl), median(ff)
        d = (ff_m - bl_m) / bl_m * 100
        verdict = "FOCUSED WINS" if ff_m < bl_m else "FOCUSED LOSES"
        print(f"\n  -> {verdict}: forced-focused is {d:+.0f}% vs baseline (${ff_m:.3f} vs ${bl_m:.3f})")
    if bl and fr:
        fr_m = median(fr)
        d = (fr_m - bl_m) / bl_m * 100
        print(f"  -> reference: forced-reviewer is {d:+.0f}% vs baseline (${fr_m:.3f})")

    manifest = {"runid": runid, "n_runs": args.n, "fixture": FIXTURE_NAME, "cells": cells}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
