---
description: Show how much claude-leverage saved you (heuristic token estimate vs all-Opus baseline). Visual one-shot summary with tier bars; cheap to invoke.
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(python:*), Bash(test:*), Bash(command:*)
---

<!--
  Design note:
  Bash preamble computes a final markdown-ready summary with visual tier bars
  and emits it directly. Body just relays - no LLM-level analysis.
  The pipe-separated raw breakdown is available via hooks/leverage_stats_agg.py
  for users who want machine-readable output.

  Output uses Claude Code's markdown rendering: **bold**, fenced code blocks
  for the breakdown (preserves bar alignment), and italics for the disclaimer.
  Unicode block characters (block-full and light-shade) render reliably in
  modern terminals.

  IMPORTANT: do NOT put literal backticks anywhere in the bash preamble below
  (or in this comment). Claude Code's slash-command parser scans the markdown
  source for the bang-then-backtick boundary by literal-backtick match - even
  backslash-escaped backticks inside bash strings, AND backticks inside HTML
  comments like this one, terminate the preamble prematurely. Backticks
  needed in the OUTPUT (markdown code fences, inline code) are constructed
  at runtime via Python's chr(96).

  Security note:
  STATS_FILE is passed via env var, never interpolated into Python -c body.
-->

## Result

!`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "_No delegations tracked yet._"; echo; echo "Use /code-review, /test, /commit-smart etc. to start populating savings data."; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); PYTHONIOENCODING=utf-8 STATS_FILE="$F" "$PY" -c 'import json, os
from collections import defaultdict
BT = chr(96)
FENCE = BT * 3
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
def fmt(n):
    return "{:,}".format(int(n)).replace(",", " ")
def bar(value, total, width=18):
    if total <= 0: return "░" * width
    filled = max(0, min(width, int(round(width * value / total))))
    return "█" * filled + "░" * (width - filled)
def plural(n):
    return "delegation" if n == 1 else "delegations"
total_count = sum(v["count"] for v in t.values())
ratios = {"sonnet": 5, "haiku": 25}
savings = 0
for tier, ratio in ratios.items():
    if tier in t and t[tier]["total"] > 0:
        savings += t[tier]["total"] * (ratio - 1) // ratio
if total_count == 0:
    print("_No delegations tracked yet._")
    raise SystemExit(0)
if savings <= 0:
    print("**%d delegations tracked but no token data yet.**" % total_count)
    print("")
    print("Older entries (pre-v0.9.0) logged only counts. Run more delegations and the next run will show token-based savings.")
    raise SystemExit(0)
print("**You have saved approximately %s tokens with claude-leverage** ✨" % fmt(savings))
print("")
print(FENCE + "text")
shown = set()
for tier in ["sonnet", "haiku", "other", "unknown"]:
    if tier not in t and tier in ratios:
        b = bar(0, total_count)
        print("  %-7s %s  not engaged" % (tier, b))
        shown.add(tier)
        continue
    if tier not in t: continue
    shown.add(tier)
    v = t[tier]
    b = bar(v["count"], total_count)
    if v["count"] == 0:
        print("  %-7s %s  not engaged" % (tier, b))
    elif v["total"] > 0:
        denom = v["cread"] + v["ccreate"] + v["input"]
        hit = (v["cread"] / denom * 100) if denom > 0 else 0
        print("  %-7s %s  %d %s · %s tok · %.0f%% cache hit" % (tier, b, v["count"], plural(v["count"]), fmt(v["total"]), hit))
    else:
        print("  %-7s %s  %d %s · pre-Path-B" % (tier, b, v["count"], plural(v["count"])))
for tier in sorted(t):
    if tier in shown: continue
    v = t[tier]
    b = bar(v["count"], total_count)
    print("  %-7s %s  %d %s" % (tier, b, v["count"], plural(v["count"])))
print(FENCE)
print("")
print("_Heuristic vs all-Opus baseline (Sonnet ~5x, Haiku ~25x cheaper output). Counterfactual unknowable - directional signal only._")
print("")
print("Raw breakdown: " + BT + "STATS_FILE=~/.claude/claude-leverage-stats.jsonl python3 hooks/leverage_stats_agg.py" + BT)
' 2>/dev/null || echo "(python error - try: STATS_FILE=$F python3 hooks/leverage_stats_agg.py for raw data)"; else echo "**No JSON parser available.** Install python3 or jq to see savings."; fi`

## Output

Display the **Result** block above verbatim, exactly as printed by the bash preamble. The output is already markdown-formatted with bold headline, fenced code block (Unicode tier bars), italic disclaimer, and a raw-breakdown command. Do not add headers, restructure, expand, or reinterpret. Just relay.
