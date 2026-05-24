"""Run the benchmark: tasks x conditions x N runs.

Each cell (task, condition, run_idx) is a `claude -p` subprocess invocation
with isolated profile and a fresh fixture copy in $TMPDIR/<runid>/<cell>/.
Resumable via per-cell checkpoint files in bench/harness/_state/<runid>/.

Usage:
    python bench/harness/run.py [--n 3] [--tasks T1,T2,T3,T4] [--conditions baseline,leveraged]
                                [--runid 2026-05-21_v0.10.0] [--resume]
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
from datetime import datetime, timezone
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent
BENCH_DIR = HARNESS_DIR.parent
REPO = BENCH_DIR.parent
FIXTURES_DIR = BENCH_DIR / "fixtures"
RESULTS_DIR = BENCH_DIR / "results"
STATE_DIR = HARNESS_DIR / "_state"

from score import (  # noqa: E402
    parse_transcript,
    parse_delegations,
    parse_delegations_from_central_log,
    quality_check,
)

# The track-delegations hook writes here. Read between snapshots per session
# instead of relying on captured stderr (Claude Code does not pipe hook stderr
# to the parent process's stderr).
CENTRAL_DELEGATION_LOG = Path.home() / ".claude" / "claude-leverage-stats.jsonl"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def load_tasks() -> list[dict]:
    with (HARNESS_DIR / "tasks.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["tasks"]


def copy_fixture(src: Path, dst: Path) -> None:
    """Copy fixture incl. .git/. Idempotent: removes dst first."""
    if dst.exists():
        # Force-remove read-only .git/ objects on Windows.
        def on_err(func, path, exc_info):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(dst, onerror=on_err)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    # Also copy the sibling _remotes/ dir if it exists (T3, T4 use a local bare remote).
    remotes_src = src.parent / "_remotes" / f"{src.name}.git"
    if remotes_src.exists():
        remotes_dst = dst.parent / "_remotes" / f"{src.name}.git"
        if remotes_dst.exists():
            shutil.rmtree(remotes_dst, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
        remotes_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(remotes_src, remotes_dst)
        # Update the cloned fixture's origin remote to point to the new local bare repo.
        subprocess.run(
            ["git", "remote", "set-url", "origin", str(remotes_dst)],
            cwd=dst, capture_output=True, text=True,
        )


def cell_id(task_id: str, condition: str, run_idx: int) -> str:
    return f"{task_id}__{condition}__r{run_idx}"


def run_one_session(
    task: dict,
    condition: str,
    run_idx: int,
    runid: str,
    plugin_dir: Path | None,
    out_dir: Path,
) -> dict:
    """Run one cell: claude -p subprocess with isolated profile. Return summary dict.

    Writes:
      <out_dir>/raw/<cell>.jsonl       stream-json transcript
      <out_dir>/raw/<cell>.hooks.log   captured stderr (track-delegations notes)
      <out_dir>/raw/<cell>.quality.json quality-check result
      <out_dir>/raw/<cell>.session.json summary metadata
    """
    cell = cell_id(task["id"], condition, run_idx)
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    quality_path = raw / f"{cell}.quality.json"
    session_path = raw / f"{cell}.session.json"

    # Per-run isolated working area outside the repo: $TMPDIR/leverage-bench-<runid>/<cell>/
    # We DO NOT override CLAUDE_CONFIG_DIR. The first smoke test confirmed that
    # running from a fresh temp dir with `--setting-sources project` is enough to
    # achieve isolation (no user-scope plugins or agents leak in). Overriding
    # CLAUDE_CONFIG_DIR breaks subscription auth (keychain unreadable from a fresh
    # config dir).
    base_tmp = Path(tempfile.gettempdir()) / f"leverage-bench-{runid}" / cell
    fixture_src = FIXTURES_DIR / task["fixture"]
    work_dir = base_tmp / "work"
    copy_fixture(fixture_src, work_dir)

    prompt = task["prompts"][condition]
    timeout = int(task.get("timeout_sec", 600))

    env = dict(os.environ)
    cmd = [
        "claude",
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--dangerously-skip-permissions",
    ]
    if condition == "leveraged" and plugin_dir is not None:
        cmd += ["--plugin-dir", str(plugin_dir)]

    # Snapshot central delegation log size BEFORE the session so we can read
    # the delta after.
    pre_log_offset = (
        CENTRAL_DELEGATION_LOG.stat().st_size
        if CENTRAL_DELEGATION_LOG.exists() else 0
    )

    log(f"run {cell}: cwd={work_dir.name} cmd={' '.join(cmd)} timeout={timeout}s")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                input=prompt,
                stdout=out_fh,
                stderr=err_fh,
                env=env,
                text=True,
                timeout=timeout,
            )
            rc = proc.returncode
            timed_out = False
    except subprocess.TimeoutExpired:
        rc = -1
        timed_out = True
    wallclock_s = time.time() - started_at
    log(f"  -> exit={rc} wall={wallclock_s:.1f}s timed_out={timed_out}")

    score = parse_transcript(transcript_path)
    # Primary delegation source: central log delta (the hook writes JSONL there).
    delegations = parse_delegations_from_central_log(CENTRAL_DELEGATION_LOG, pre_log_offset)
    # Stderr fallback (rarely captures anything, kept for forensics).
    stderr_delegations = parse_delegations(hooks_log_path)
    if not delegations and stderr_delegations:
        delegations = stderr_delegations
    quality_pass, quality_reasons = quality_check(
        check_spec=task["quality_check"],
        output=score.final_text,
        fixture_dir=work_dir,
        delegations=delegations,
        condition=condition,
    )

    summary = {
        "cell": cell,
        "task": task["id"],
        "task_name": task["name"],
        "condition": condition,
        "run_idx": run_idx,
        "runid": runid,
        "exit_code": rc,
        "timed_out": timed_out,
        "wallclock_s": round(wallclock_s, 2),
        "resolved_model": score.resolved_model,
        "agents_available": score.agents_available,
        "plugins": score.plugins,
        "is_error": score.is_error,
        "error_message": score.error_message,
        "tokens": {
            "input": score.input_tokens,
            "output": score.output_tokens,
            "cache_read": score.cache_read,
            "cache_creation": score.cache_creation,
            "total": score.total_tokens,
        },
        "total_cost_usd": score.total_cost_usd,
        "duration_ms": score.duration_ms,
        "model_usage": score.model_usage,
        "delegations": delegations,
        "quality_pass": quality_pass,
        "quality_reasons": quality_reasons,
        "final_text_len": len(score.final_text),
    }
    session_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    quality_path.write_text(
        json.dumps({"pass": quality_pass, "reasons": quality_reasons}, indent=2),
        encoding="utf-8",
    )

    # Clean up the work tree to save disk; keep results-relevant artifacts.
    try:
        shutil.rmtree(base_tmp, ignore_errors=True)
    except Exception:
        pass

    return summary


def make_runid() -> str:
    """Read plugin version from .claude-plugin/plugin.json and combine with date."""
    plugin_json = REPO / ".claude-plugin" / "plugin.json"
    version = "unknown"
    if plugin_json.exists():
        try:
            version = json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "unknown")
        except Exception:
            pass
    return f"{datetime.now().strftime('%Y-%m-%d')}_v{version}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=3, help="runs per (task, condition)")
    p.add_argument("--tasks", type=str, default="", help="comma-separated task IDs (default: all)")
    p.add_argument("--conditions", type=str, default="baseline,leveraged")
    p.add_argument("--runid", type=str, default="")
    p.add_argument("--plugin-dir", type=str, default=str(REPO))
    p.add_argument("--resume", action="store_true", help="skip cells already in checkpoint")
    p.add_argument("--dry-run", action="store_true", help="print plan, no claude -p")
    args = p.parse_args()

    tasks = load_tasks()
    if args.tasks:
        wanted = {x.strip() for x in args.tasks.split(",")}
        tasks = [t for t in tasks if t["id"] in wanted]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]

    runid = args.runid or make_runid()
    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = STATE_DIR / runid
    state_dir.mkdir(parents=True, exist_ok=True)

    log(f"runid={runid} out_dir={out_dir}")
    log(f"plan: tasks={[t['id'] for t in tasks]} conditions={conditions} N={args.n}")
    log(f"total cells: {len(tasks) * len(conditions) * args.n}")

    if args.dry_run:
        for t in tasks:
            for c in conditions:
                for i in range(args.n):
                    log(f"  [DRY] {cell_id(t['id'], c, i)}")
        return 0

    plugin_dir = Path(args.plugin_dir).resolve()

    manifest = {
        "runid": runid,
        "started_at": ts(),
        "plugin_dir": str(plugin_dir),
        "claude_code_version": _claude_version(),
        "plugin_version": _read_plugin_version(),
        "n_runs": args.n,
        "tasks": [t["id"] for t in tasks],
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
    for t in tasks:
        for c in conditions:
            for i in range(args.n):
                cell = cell_id(t["id"], c, i)
                if cell in completed_cells:
                    log(f"skip {cell} (already complete)")
                    continue
                summary = run_one_session(
                    task=t,
                    condition=c,
                    run_idx=i,
                    runid=runid,
                    plugin_dir=plugin_dir,
                    out_dir=out_dir,
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


def _claude_version() -> str:
    try:
        cp = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        return (cp.stdout or "").strip()
    except Exception as e:
        return f"unknown ({e})"


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
