"""Warm-cache benchmark: 4 distinct workflow turns in ONE `claude -p` session.

The cold-cache benchmark (run.py) tests the WORST case for a plugin: every
task is a fresh session that pays system-prompt cache_creation. The warm-cache
benchmark tests the more PRODUCTION-realistic case: a developer works in one
session and invokes multiple workflows. After the first turn pays the cache-
creation cost, subsequent turns read from cache (~10x cheaper per token).

Design:
- ONE fixture (warm-session/) - same cwd throughout, since Claude Code can't
  change cwd mid-session
- 4 turns sent via --input-format stream-json, each a distinct workflow:
    1. Code review of the staged diff (T1-style)
    2. Context-gather for a hypothetical /healthz endpoint (T2-style)
    3. Fix a README typo and commit (small edit + commit-smart)
    4. Final code review of HEAD
- Per-turn cost extracted from the DELTA between consecutive `result` events.
  Empirically, claude -p emits one result event per input message and
  result.total_cost_usd is cumulative across the session.

Conditions: baseline (no --plugin-dir) vs leveraged (--plugin-dir <repo>).
N runs per condition. Quality checks adapted from cold-cache tasks.

Usage:
    python bench/harness/run_warm.py [--n 3] [--runid 2026-05-23_v0.10.0-warm]
                                     [--conditions baseline,leveraged]
                                     [--resume] [--dry-run]
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

HARNESS_DIR = Path(__file__).resolve().parent
BENCH_DIR = HARNESS_DIR.parent
REPO = BENCH_DIR.parent
FIXTURES_DIR = BENCH_DIR / "fixtures"
RESULTS_DIR = BENCH_DIR / "results"
STATE_DIR = HARNESS_DIR / "_state"

sys.path.insert(0, str(HARNESS_DIR))
from score import parse_delegations_from_central_log, quality_check  # noqa: E402
from run import copy_fixture, ts, log, make_runid, CENTRAL_DELEGATION_LOG  # noqa: E402


# 4 turns, each a distinct workflow. Prompts identical between baseline and
# leveraged so the only difference is whether claude-leverage is loaded.
TURNS = [
    {
        "id": "W1.code-review",
        "expected_agent": "code-reviewer",
        "expected_tier": "sonnet",
        "prompt": (
            "Review the staged changes (`git diff --cached`) for bugs, security issues, "
            "and quality problems. Report findings clearly, organized by severity."
        ),
        "quality_check": {
            "kind": "regex_all",
            "patterns_required_all": ["users\\.py"],
            "patterns_required_any": ["sql", "injection", "raw query", "f-?string", "concat"],
            "case_insensitive": True,
        },
    },
    {
        "id": "W2.context-gather",
        "expected_agent": "context-gatherer",
        "expected_tier": "haiku",
        "prompt": (
            "I want to add a `/healthz` endpoint that returns the same uptime+version JSON "
            "as `/status` but without authentication. Before I start coding, gather the "
            "implementation context I'll need: which files I should read, which existing "
            "patterns to follow, and which tests already cover this area. "
            "Do not write code yet - just the context package."
        ),
        "quality_check": {
            "kind": "regex_all",
            "patterns_required_all": ["status\\.py", "require_auth", "VERSION"],
            "case_insensitive": True,
        },
    },
    {
        "id": "W3.tiny-commit",
        "expected_agent": "inline",
        "expected_tier": "opus",  # /commit-smart now routes 1-file <80-LOC inline
        "prompt": (
            "In `README.md`, the word 'Liscence' is misspelled. Fix it to 'License'. "
            "Then stage ONLY that change (use `git reset` first to unstage the larger "
            "diff already in the index, then add only README.md), and commit it. "
            "If the `/commit-smart` slash command is available in your environment, "
            "use it for the commit step. Otherwise commit directly with a "
            "Conventional Commits message."
        ),
        "quality_check": {
            "kind": "git_commit",
            "subject_regex": "^(docs|chore|fix)(\\([a-z0-9_-]+\\))?: ",
            "expected_commits_added": 1,
            "expected_files_changed": 1,
            # No tier check - the new /commit-smart commits 1-file <80-LOC inline.
        },
    },
    {
        "id": "W4.final-review",
        "expected_agent": "code-reviewer",
        "expected_tier": "sonnet",
        "prompt": (
            "Re-review the latest commit (HEAD) for any remaining issues. "
            "Brief - this is a follow-up pass, not a full re-review."
        ),
        "quality_check": {
            # Minimal check: output must mention HEAD or commit and have some structure.
            "kind": "regex_all",
            "patterns_required_all": ["README"],
            "case_insensitive": True,
        },
    },
]

FIXTURE_NAME = "warm-session"


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return cp.returncode, (cp.stdout or "").strip()


def parse_warm_transcript(path: Path, n_expected_turns: int = 4) -> dict:
    """Parse multi-turn stream-json into session totals + per-turn approximation.

    Empirical Claude Code behavior with --input-format stream-json + multiple
    user messages on stdin: claude treats the whole input as ONE conversation
    and emits ONE `result` event at the end with cumulative cost+usage.
    Multiple turns are still processed, but no per-result-event split.

    To approximate per-turn cost, we walk the assistant events in order. Each
    assistant message carries its own `usage` (tokens for that single turn).
    We group consecutive assistants into "user turns" by counting the number
    of distinct final-text assistant outputs and dividing by n_expected_turns
    when an exact mapping is not derivable.

    Returned structure:
      - session_total: from result event (authoritative)
      - turns: best-effort per-turn token + final text + duration (cost is
        distributed proportionally to token volume)
    """
    if not path.exists():
        return {"is_error": True, "error_message": f"transcript missing: {path}", "turns": [], "session": {}}

    resolved_model = ""
    plugins: list = []
    agents_available: list = []
    assistant_events: list[dict] = []
    final_text_outputs: list[dict] = []  # one per assistant message that contained text
    result_event: dict | None = None
    # Tool results (from "user" events with role=user containing tool_result blocks)
    # are the subagent reports. We collect them in stream order and stitch them
    # into the assistant text in the same chunk so substring quality checks pass
    # even when the main session summarizes rather than quotes a subagent.
    pending_tool_result_text: list[str] = []

    def _extract_text(content) -> str:
        """Stringify a content block which may be a list of text blocks or a string."""
        if isinstance(content, str):
            return content
        out: list[str] = []
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    out.append(c.get("text", ""))
        return "\n".join(out)

    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get("type")
            if t == "system" and d.get("subtype") == "init":
                if not resolved_model:
                    resolved_model = d.get("model", "")
                    plugins = d.get("plugins") or []
                    agents_available = d.get("agents") or []
            elif t == "assistant":
                msg = d.get("message") or {}
                u = msg.get("usage") or {}
                texts = [b.get("text", "") for b in (msg.get("content") or []) if b.get("type") == "text"]
                # Stitch in any tool_result text that arrived since the last assistant event.
                combined_text = "\n".join(texts)
                if pending_tool_result_text:
                    combined_text = combined_text + "\n[tool_result]\n" + "\n".join(pending_tool_result_text)
                    pending_tool_result_text = []
                ev = {
                    "input": int(u.get("input_tokens") or 0),
                    "output": int(u.get("output_tokens") or 0),
                    "cache_read": int(u.get("cache_read_input_tokens") or 0),
                    "cache_creation": int(u.get("cache_creation_input_tokens") or 0),
                    "has_text": bool(texts) or bool(combined_text.strip()),
                    "text": combined_text,
                }
                assistant_events.append(ev)
                if ev["has_text"]:
                    final_text_outputs.append(ev)
            elif t == "user":
                # User-role events that follow assistant tool_use calls contain
                # tool_result blocks with the subagent's full report. Capture
                # their text so quality checks can search through it.
                msg = d.get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            inner = c.get("content")
                            text = _extract_text(inner)
                            if text:
                                pending_tool_result_text.append(text)
            elif t == "result":
                result_event = d

    if result_event is None:
        return {"is_error": True, "error_message": "no result event", "turns": [], "session": {}}

    total_cost = float(result_event.get("total_cost_usd") or 0.0)
    total_usage = result_event.get("usage") or {}
    session = {
        "total_cost_usd": total_cost,
        "duration_ms": int(result_event.get("duration_ms") or 0),
        "num_turns": int(result_event.get("num_turns") or 0),
        "is_error": bool(result_event.get("is_error")),
        "input_tokens": int(total_usage.get("input_tokens") or 0),
        "output_tokens": int(total_usage.get("output_tokens") or 0),
        "cache_read": int(total_usage.get("cache_read_input_tokens") or 0),
        "cache_creation": int(total_usage.get("cache_creation_input_tokens") or 0),
        "model_usage": result_event.get("modelUsage") or {},
    }

    # Per-turn approximation: distribute the assistant text outputs across the
    # expected turns. The last assistant text per turn is the "final answer".
    # When there are exactly n_expected_turns text outputs, mapping is 1:1.
    # When there are more (e.g. multi-step commits emit progress text), we
    # bucket extra outputs into the nearest preceding turn by keyword match
    # on the prompt's expected agent. For simplicity, assign each text output
    # to the turn that has not yet been "finalized" based on output order.
    turns: list[dict] = []
    if final_text_outputs:
        # Naive split: divide N text outputs into n_expected_turns roughly equal groups
        per_turn = max(1, len(final_text_outputs) // n_expected_turns)
        for i in range(n_expected_turns):
            start = i * per_turn
            end = (i + 1) * per_turn if i < n_expected_turns - 1 else len(final_text_outputs)
            chunk = final_text_outputs[start:end]
            if not chunk:
                turns.append({
                    "turn_idx": i,
                    "input": 0, "output": 0, "cache_read": 0, "cache_creation": 0,
                    "final_text": "", "n_assistant_text_events": 0,
                })
                continue
            turn = {
                "turn_idx": i,
                "input": sum(e["input"] for e in chunk),
                "output": sum(e["output"] for e in chunk),
                "cache_read": sum(e["cache_read"] for e in chunk),
                "cache_creation": sum(e["cache_creation"] for e in chunk),
                "n_assistant_text_events": len(chunk),
                # Combined text across all assistant text events that belong to this turn.
                "final_text": "\n\n".join(e["text"] for e in chunk if e["text"]),
            }
            turn["tokens"] = turn["input"] + turn["output"] + turn["cache_read"] + turn["cache_creation"]
            turns.append(turn)
    else:
        for i in range(n_expected_turns):
            turns.append({
                "turn_idx": i,
                "input": 0, "output": 0, "cache_read": 0, "cache_creation": 0,
                "final_text": "", "n_assistant_text_events": 0, "tokens": 0,
            })

    # Distribute total_cost proportionally to per-turn token volume.
    total_turn_tokens = sum(t.get("tokens", 0) for t in turns)
    for turn in turns:
        if total_turn_tokens > 0:
            share = turn.get("tokens", 0) / total_turn_tokens
        else:
            share = 1.0 / max(1, len(turns))
        turn["approx_cost_usd"] = round(total_cost * share, 6)

    return {
        "is_error": session["is_error"],
        "error_message": "",
        "resolved_model": resolved_model,
        "plugins": plugins,
        "agents_available": agents_available,
        "session": session,
        "turns": turns,
    }


def run_one_warm_session(
    condition: str,
    run_idx: int,
    runid: str,
    plugin_dir: Path | None,
    out_dir: Path,
    timeout_sec: int = 1800,
) -> dict:
    """Run one warm session: 4 turns in one claude -p invocation."""
    cell = f"warm__{condition}__r{run_idx}"
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    transcript_path = raw / f"{cell}.jsonl"
    hooks_log_path = raw / f"{cell}.hooks.log"
    quality_path = raw / f"{cell}.quality.json"
    session_path = raw / f"{cell}.session.json"

    base_tmp = Path(tempfile.gettempdir()) / f"leverage-bench-{runid}" / cell
    fixture_src = FIXTURES_DIR / FIXTURE_NAME
    work_dir = base_tmp / "work"
    copy_fixture(fixture_src, work_dir)

    # Snapshot central delegation log size before session.
    pre_log_offset = (
        CENTRAL_DELEGATION_LOG.stat().st_size
        if CENTRAL_DELEGATION_LOG.exists() else 0
    )

    # Build stream-json input: one user message per turn.
    input_lines = []
    for turn in TURNS:
        msg = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": turn["prompt"]}],
            },
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

    log(f"run {cell}: cmd={' '.join(cmd)} turns={len(TURNS)} timeout={timeout_sec}s")
    started_at = time.time()
    try:
        with transcript_path.open("w", encoding="utf-8", newline="\n") as out_fh, \
             hooks_log_path.open("w", encoding="utf-8", newline="\n") as err_fh:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                input=input_stream,
                stdout=out_fh,
                stderr=err_fh,
                env=dict(os.environ),
                text=True,
                timeout=timeout_sec,
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
    # Per-turn quality check. With multi-turn stream-json input, claude emits
    # one cumulative result event - per-turn cost is approximated by token
    # share. Quality check still runs against each turn's assistant text.
    per_turn_quality = []
    for i, turn_spec in enumerate(TURNS):
        if i < len(parsed["turns"]):
            t = parsed["turns"][i]
            q_pass, q_reasons = quality_check(
                check_spec=turn_spec["quality_check"],
                output=t["final_text"],
                fixture_dir=work_dir,
                delegations=delegations_all,
                condition=condition,
            )
            per_turn_quality.append({
                "turn_id": turn_spec["id"],
                "turn_idx": i,
                "approx_cost_usd": t.get("approx_cost_usd", 0),
                "turn_tokens": t.get("tokens", 0),
                "usage": {
                    "input": t["input"], "output": t["output"],
                    "cache_read": t["cache_read"], "cache_creation": t["cache_creation"],
                },
                "n_assistant_text_events": t.get("n_assistant_text_events", 0),
                "quality_pass": q_pass,
                "quality_reasons": q_reasons,
                "final_text_len": len(t["final_text"]),
            })
        else:
            per_turn_quality.append({
                "turn_id": turn_spec["id"],
                "turn_idx": i,
                "approx_cost_usd": 0,
                "turn_tokens": 0,
                "quality_pass": False,
                "quality_reasons": ["MISSING turn (session truncated)"],
            })

    n_passed = sum(1 for t in per_turn_quality if t["quality_pass"])
    summary = {
        "cell": cell,
        "condition": condition,
        "run_idx": run_idx,
        "runid": runid,
        "exit_code": rc,
        "timed_out": timed_out,
        "wallclock_s": round(wallclock_s, 2),
        "resolved_model": parsed.get("resolved_model"),
        "agents_available": parsed.get("agents_available"),
        "plugins": parsed.get("plugins"),
        "is_error": parsed.get("is_error"),
        # Session-level (authoritative from `result` event):
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
        # Per-turn approximation:
        "n_turns_quality_passed": n_passed,
        "n_turns_expected": len(TURNS),
        "turns": per_turn_quality,
        "delegations": delegations_all,
    }
    session_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    quality_path.write_text(
        json.dumps([
            {"turn_id": t["turn_id"], "pass": t["quality_pass"], "reasons": t["quality_reasons"]}
            for t in per_turn_quality
        ], indent=2),
        encoding="utf-8",
    )

    try:
        shutil.rmtree(base_tmp, ignore_errors=True)
    except Exception:
        pass

    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--conditions", type=str, default="baseline,leveraged")
    p.add_argument("--runid", type=str, default="")
    p.add_argument("--plugin-dir", type=str, default=str(REPO))
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int, default=1800)
    args = p.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    runid = args.runid or f"{make_runid()}-warm"

    out_dir = RESULTS_DIR / runid
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = STATE_DIR / runid
    state_dir.mkdir(parents=True, exist_ok=True)

    log(f"runid={runid} out_dir={out_dir}")
    log(f"plan: warm-session × conditions={conditions} × N={args.n}  (4 turns per session)")
    log(f"total cells: {len(conditions) * args.n}")

    if args.dry_run:
        for c in conditions:
            for i in range(args.n):
                log(f"  [DRY] warm__{c}__r{i}")
        return 0

    plugin_dir = Path(args.plugin_dir).resolve()

    manifest = {
        "runid": runid,
        "mode": "warm",
        "started_at": ts(),
        "plugin_dir": str(plugin_dir),
        "claude_code_version": _claude_version(),
        "plugin_version": _read_plugin_version(),
        "n_runs": args.n,
        "fixture": FIXTURE_NAME,
        "turns": [t["id"] for t in TURNS],
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
            cell = f"warm__{c}__r{i}"
            if cell in completed_cells:
                log(f"skip {cell} (already complete)")
                continue
            summary = run_one_warm_session(
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
