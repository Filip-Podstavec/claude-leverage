"""Score one benchmark session.

Reads:
  - stream-json transcript (stdout of `claude -p`)
  - hooks.log (stderr - parsed for track-delegations records)
  - working-copy state (for git-based quality checks)

Returns a dict with:
  - tokens (input, output, cache_read, cache_creation, total)
  - model usage (per-model dict from result event)
  - total_cost_usd
  - duration_ms
  - delegations (list of (subagent, tier, total_tokens))
  - quality (pass: bool, reasons: list[str])
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# track-delegations.sh emits "(claude-leverage: <agent> -> <tier>, <N> tok)" on stderr.
# Pattern matches both with-and-without the token count to be safe.
_DELEGATION_RE = re.compile(
    r"\(claude-leverage:\s*([\w.:-]+)\s*->\s*(\w+)(?:,\s*(\d+)\s*tok)?\)"
)


@dataclass
class SessionScore:
    """Result of scoring one session."""
    # tokens
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    total_tokens: int = 0
    # cost & duration
    total_cost_usd: float = 0.0
    duration_ms: int = 0
    # per-model breakdown from result.modelUsage
    model_usage: dict[str, dict[str, Any]] = field(default_factory=dict)
    # delegations parsed from stderr
    delegations: list[dict[str, Any]] = field(default_factory=list)
    # session metadata
    resolved_model: str = ""
    plugins: list[dict[str, Any]] = field(default_factory=list)
    agents_available: list[str] = field(default_factory=list)
    is_error: bool = False
    error_message: str = ""
    # final assistant text (concatenated)
    final_text: str = ""
    # quality check outcome
    quality_pass: bool = False
    quality_reasons: list[str] = field(default_factory=list)


def parse_transcript(path: Path) -> SessionScore:
    """Parse a stream-json file into a SessionScore.

    The file contains one JSON object per line. Last `result` event holds
    the final usage totals. `system.init` holds resolved_model + agents
    + plugins (used to verify isolation).
    """
    score = SessionScore()
    if not path.exists():
        score.is_error = True
        score.error_message = f"transcript missing: {path}"
        return score

    final_texts: list[str] = []
    saw_result = False

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
                score.resolved_model = d.get("model", "")
                score.plugins = d.get("plugins") or []
                score.agents_available = d.get("agents") or []
            elif t == "assistant":
                msg = d.get("message") or {}
                for block in msg.get("content") or []:
                    if block.get("type") == "text":
                        final_texts.append(block.get("text", ""))
            elif t == "result":
                saw_result = True
                score.is_error = bool(d.get("is_error"))
                if d.get("api_error_status"):
                    score.error_message = str(d.get("api_error_status"))
                score.duration_ms = int(d.get("duration_ms") or 0)
                score.total_cost_usd = float(d.get("total_cost_usd") or 0.0)
                usage = d.get("usage") or {}
                score.input_tokens = int(usage.get("input_tokens") or 0)
                score.output_tokens = int(usage.get("output_tokens") or 0)
                score.cache_read = int(usage.get("cache_read_input_tokens") or 0)
                score.cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
                score.total_tokens = (
                    score.input_tokens
                    + score.output_tokens
                    + score.cache_read
                    + score.cache_creation
                )
                score.model_usage = d.get("modelUsage") or {}
                # `result.result` holds the final assistant text directly when output_format=stream-json.
                result_text = d.get("result")
                if isinstance(result_text, str) and result_text:
                    # Prefer the explicit final text over concatenated assistant turns
                    final_texts = [result_text]

    if not saw_result:
        score.is_error = True
        score.error_message = "no `result` event in transcript (session crashed or truncated)"
    score.final_text = "\n".join(final_texts).strip()
    return score


def parse_delegations(hooks_log_path: Path) -> list[dict[str, Any]]:
    """Parse track-delegations.sh notes from captured stderr.

    Fallback path: the hook also writes to the central JSONL log, which is
    more reliable (see parse_delegations_from_central_log). This stderr
    parse is kept for forensics but rarely returns anything in practice -
    Claude Code's hook stderr is not piped to the harness's stderr redirect.

    Each note: '(claude-leverage: <agent> -> <tier>, <N> tok)'.
    Returns list of {'agent', 'tier', 'tokens'} dicts.
    """
    out: list[dict[str, Any]] = []
    if not hooks_log_path.exists():
        return out
    with hooks_log_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            for m in _DELEGATION_RE.finditer(line):
                agent, tier, tok = m.group(1), m.group(2), m.group(3)
                out.append({
                    "agent": agent,
                    "tier": tier,
                    "tokens": int(tok) if tok else None,
                })
    return out


def parse_delegations_from_central_log(
    central_log: Path,
    start_offset: int,
) -> list[dict[str, Any]]:
    """Read new lines from ~/.claude/claude-leverage-stats.jsonl since `start_offset`.

    The track-delegations.sh hook writes a JSONL record per delegation. We
    capture file size before each session and read the delta after. Records
    are decoded directly - no regex needed.

    Returns list of dicts with: agent, tier, tokens (=total_tokens), and the
    full record under '_raw' for the per-agent report (so we have per-tier
    breakdown if needed).
    """
    out: list[dict[str, Any]] = []
    if not central_log.exists():
        return out
    try:
        with central_log.open("rb") as f:
            f.seek(start_offset)
            new_bytes = f.read()
    except OSError:
        return out
    try:
        new_text = new_bytes.decode("utf-8", errors="replace")
    except Exception:
        return out
    for line in new_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        agent = rec.get("subagent")
        if not isinstance(agent, str) or not agent:
            continue
        out.append({
            "agent": agent,
            "tier": rec.get("tier") or "unknown",
            "tokens": rec.get("total_tokens"),
            "input_tokens": rec.get("input_tokens"),
            "output_tokens": rec.get("output_tokens"),
            "cache_read_input_tokens": rec.get("cache_read_input_tokens"),
            "cache_creation_input_tokens": rec.get("cache_creation_input_tokens"),
            "duration_ms": rec.get("duration_ms"),
            "_raw": rec,
        })
    return out


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def quality_check(
    check_spec: dict[str, Any],
    output: str,
    fixture_dir: Path,
    delegations: list[dict[str, Any]],
    condition: str,
    fixture_base_ref: str = "fixture-base",
) -> tuple[bool, list[str]]:
    """Run the configured quality check. Return (pass, reasons).

    `reasons` always contains a short message per assertion (pass or fail).
    """
    kind = check_spec.get("kind")
    if kind == "regex_all":
        return _check_regex_all(check_spec, output)
    if kind == "git_commit":
        return _check_git_commit(check_spec, fixture_dir, delegations, condition, fixture_base_ref)
    return False, [f"unknown quality_check kind: {kind!r}"]


def _check_regex_all(spec: dict[str, Any], output: str) -> tuple[bool, list[str]]:
    """Pass iff output matches all of `patterns_required_all` AND at least one of `patterns_required_any`.

    Patterns are Python regexes. `case_insensitive` defaults True.
    """
    reasons: list[str] = []
    if not output:
        return False, ["empty output"]
    flags = re.IGNORECASE if spec.get("case_insensitive", True) else 0
    required_all = spec.get("patterns_required_all") or []
    required_any = spec.get("patterns_required_any") or []

    all_ok = True
    for pat in required_all:
        if re.search(pat, output, flags):
            reasons.append(f"OK required: /{pat}/")
        else:
            reasons.append(f"MISSING required: /{pat}/")
            all_ok = False

    any_ok = True
    if required_any:
        matched = [pat for pat in required_any if re.search(pat, output, flags)]
        if matched:
            reasons.append(f"OK any-of matched: {matched}")
        else:
            reasons.append(f"MISSING any-of: {required_any}")
            any_ok = False

    return (all_ok and any_ok), reasons


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return cp.returncode, (cp.stdout or "").strip()


def _check_git_commit(
    spec: dict[str, Any],
    fixture_dir: Path,
    delegations: list[dict[str, Any]],
    condition: str,
    base_ref: str,
) -> tuple[bool, list[str]]:
    """Verify post-session git state: subject regex, commit count, file count, optional tier."""
    reasons: list[str] = []
    ok = True

    # 1. Count commits added since fixture-base.
    rc, out = _git(["rev-list", "--count", f"{base_ref}..HEAD"], fixture_dir)
    if rc != 0:
        return False, [f"git rev-list failed: {out}"]
    added = int(out or "0")
    expected = spec.get("expected_commits_added")
    if expected is not None:
        if added == expected:
            reasons.append(f"OK commits_added={added}")
        else:
            reasons.append(f"FAIL commits_added={added}, expected {expected}")
            ok = False

    if added == 0:
        # No commit -> nothing else to check.
        return False, reasons + ["FAIL: no commit was created"]

    # 2. Subject regex.
    rc, subject = _git(["log", "-1", "--format=%s"], fixture_dir)
    if rc != 0:
        return False, reasons + [f"git log failed: {subject}"]
    pat = spec.get("subject_regex")
    if pat:
        if re.match(pat, subject):
            reasons.append(f"OK subject: {subject!r}")
        else:
            reasons.append(f"FAIL subject: {subject!r} does not match /{pat}/")
            ok = False

    # 3. Files changed in latest commit.
    rc, names = _git(["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], fixture_dir)
    files = [n for n in names.splitlines() if n.strip()] if rc == 0 else []
    if "expected_files_changed" in spec:
        want = int(spec["expected_files_changed"])
        if len(files) == want:
            reasons.append(f"OK files_changed={len(files)}")
        else:
            reasons.append(f"FAIL files_changed={len(files)}, expected {want} ({files})")
            ok = False
    if "min_files_changed" in spec:
        want = int(spec["min_files_changed"])
        if len(files) >= want:
            reasons.append(f"OK files_changed={len(files)} >= {want}")
        else:
            reasons.append(f"FAIL files_changed={len(files)} < {want} ({files})")
            ok = False

    # 4. Tier check (leveraged condition only).
    if condition == "leveraged":
        expected_tier = spec.get("leveraged_expected_tier")
        if expected_tier:
            tiers_seen = {d.get("tier") for d in delegations}
            if expected_tier in tiers_seen:
                reasons.append(f"OK tier {expected_tier!r} engaged (delegations: {sorted(tiers_seen)})")
            elif not delegations:
                reasons.append(f"WARN no delegations logged - hook may not have fired")
                # Don't fail on this alone; the commit itself is the primary signal.
            else:
                reasons.append(f"FAIL expected tier {expected_tier!r}, saw {sorted(tiers_seen)}")
                ok = False

    return ok, reasons
