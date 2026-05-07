---
description: Show how much claude-leverage saved you (heuristic token estimate vs all-Opus baseline). One-line answer; cheap to invoke.
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(python:*), Bash(test:*), Bash(command:*)
---

<!--
  Design note:
  This command's bash preamble computes the final user-facing summary text
  itself and prints it. The Opus body just relays the output verbatim.
  Goal: keep the slash command extremely cheap to invoke - no multi-section
  report, no LLM-level analysis. The pipe-separated breakdown that earlier
  versions exposed for LLM parsing is intentionally gone; if a user wants
  the raw breakdown they can run hooks/leverage_stats_agg.py directly.

  Security note:
  STATS_FILE is passed via env var, never interpolated into the Python -c
  body. Path resolution stays within the user's home directory.
-->

## Result

!`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "No delegations tracked yet. Use /code-review, /test, /commit-smart etc. to start populating savings data."; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c 'import json, os
from collections import defaultdict
t = defaultdict(lambda: {"count":0,"total":0,"input":0,"output":0,"cread":0,"ccreate":0,"dur":0})
fmap = [("total_tokens","total"),("input_tokens","input"),("output_tokens","output"),("cache_read_input_tokens","cread"),("cache_creation_input_tokens","ccreate"),("duration_ms","dur")]
try:
    with open(os.environ["STATS_FILE"], encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln: continue
            try: r = json.loads(ln)
            except Exception: continue
            tier = r.get("tier","?") or "?"
            if not isinstance(tier, str): tier = "?"
            t[tier]["count"] += 1
            for s,d in fmap:
                v = r.get(s)
                if isinstance(v,(int,float)) and not isinstance(v,bool): t[tier][d] += int(v)
except Exception:
    print("Could not read stats file.")
    raise SystemExit(0)
total_delegations = sum(v["count"] for v in t.values())
ratios = {"sonnet": 5, "haiku": 25}
savings = 0
total_consumed = 0
parts = []
for tier, ratio in ratios.items():
    if tier in t and t[tier]["total"] > 0:
        savings += t[tier]["total"] * (ratio - 1)
        total_consumed += t[tier]["total"]
        parts.append("%d %s" % (t[tier]["count"], tier))
all_cread = sum(v["cread"] for v in t.values())
all_input = sum(v["input"] for v in t.values())
all_ccreate = sum(v["ccreate"] for v in t.values())
denom = all_cread + all_input + all_ccreate
hit = (all_cread / denom * 100) if denom > 0 else 0
def fmt(n): return "%s" % "{:,}".format(n).replace(",", " ")
if savings > 0:
    print("You have saved approximately %s tokens by delegating to cheaper model tiers instead of Opus." % fmt(savings))
    print("")
    print("Heuristic estimate based on %s tokens actually consumed by %s delegations (%.1f%% cache hit ratio) at ~5x Opus output-cost ratio (Sonnet) and ~25x (Haiku). %d total delegations tracked. Real savings depend on Opus hypothetical handling, which is unknowable." % (fmt(total_consumed), " + ".join(parts), hit, total_delegations))
    print("")
    print("Raw breakdown: STATS_FILE=~/.claude/claude-leverage-stats.jsonl python3 hooks/leverage_stats_agg.py")
else:
    print("%d delegations tracked but no token data yet." % total_delegations)
    print("Older entries (pre-v0.9.0) only logged delegation counts; run more delegations to populate token tracking.")
' 2>/dev/null || echo "(python error - try: STATS_FILE=$F python3 hooks/leverage_stats_agg.py for raw data)"; elif command -v jq >/dev/null 2>&1; then echo "Token aggregation requires Python (3 or 2). jq alone cannot do the savings calculation."; echo "Delegations tracked: $(jq -s 'length' "$F" 2>/dev/null || echo "?")"; echo "Install python3 for the savings estimate."; else echo "No JSON parser available. Install python3 or jq to see savings."; fi`

## Output

Display the **Result** block above verbatim, exactly as printed by the bash preamble. Do not add headers, restructure, expand, or interpret. The preamble already produced the final answer.

If the bash output starts with "(python error" or "No JSON parser", surface it as-is - it is already a complete diagnostic message for the user.
