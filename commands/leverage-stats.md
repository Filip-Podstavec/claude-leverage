---
description: Show claude-leverage delegation stats — counts, real token usage by tier, and estimated savings vs all-Opus baseline. Reads ~/.claude/claude-leverage-stats.jsonl populated by the track-delegations hook.
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(python:*), Bash(test:*), Bash(wc:*), Bash(tail:*), Bash(date:*), Bash(command:*), Bash(tr:*)
---

<!--
  Security note for future reviewers:
  - $F = $HOME/.claude/claude-leverage-stats.jsonl is always passed via the
    STATS_FILE env var or as a quoted positional argument. Never interpolated
    into jq filter strings or Python -c script bodies.
  - The Python -c body is single-quoted at the shell level; the path is read
    inside Python via os.environ['STATS_FILE'], not via shell expansion.

  Maintenance note for future contributors:
  - The inline Python in the "Tier breakdown" preamble line mirrors the logic
    in hooks/leverage_stats_agg.py. The slash command uses inline because the
    helper file's path resolution was unreliable in slash command context.
    If you change one, change the other (same fields, same sort order, same
    encoding handling). The jq fallback below also produces the same
    pipe-separated output format - keep all three in sync.
-->

## Context

Stats file present: !`test -f "$HOME/.claude/claude-leverage-stats.jsonl" && echo "yes" || echo "no"`
Total delegations: !`if [ -f "$HOME/.claude/claude-leverage-stats.jsonl" ]; then wc -l < "$HOME/.claude/claude-leverage-stats.jsonl" | tr -d ' '; else echo "0"; fi`
Parser available: !`if command -v jq >/dev/null 2>&1; then echo "jq"; elif command -v python3 >/dev/null 2>&1; then echo "python3"; elif command -v python >/dev/null 2>&1; then echo "python"; else echo "none"; fi`
Tier breakdown: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "(no data)"; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c 'import json, os
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
    raise SystemExit(0)
for tier in sorted(t, key=lambda x: (-t[x]["count"], x)):
    v = t[tier]
    print("%s|count=%d|total=%d|input=%d|output=%d|cread=%d|ccreate=%d|dur_ms=%d" % (tier, v["count"], v["total"], v["input"], v["output"], v["cread"], v["ccreate"], v["dur"]))
' 2>/dev/null || echo "(python error)"; elif command -v jq >/dev/null 2>&1; then jq -s -r 'group_by(.tier) | map({k: .[0].tier, count: length, total: (map(.total_tokens // 0) | add), input: (map(.input_tokens // 0) | add), output: (map(.output_tokens // 0) | add), cread: (map(.cache_read_input_tokens // 0) | add), ccreate: (map(.cache_creation_input_tokens // 0) | add), dur: (map(.duration_ms // 0) | add)}) | sort_by(-.count) | map("\(.k)|count=\(.count)|total=\(.total)|input=\(.input)|output=\(.output)|cread=\(.cread)|ccreate=\(.ccreate)|dur_ms=\(.dur)") | join("\n")' "$F" 2>/dev/null || echo "(jq error)"; else echo "(install python or jq for breakdown)"; fi`
By subagent: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "(no data)"; elif command -v jq >/dev/null 2>&1; then jq -s -r 'group_by(.subagent) | map({s: .[0].subagent, n: length}) | sort_by(-.n) | map("\(.s): \(.n)") | join("\n")' "$F" 2>/dev/null || echo "(jq error)"; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c "import json,os; from collections import Counter; rs=[json.loads(l) for l in open(os.environ['STATS_FILE']) if l.strip()]; c=Counter(r.get('subagent','?') for r in rs); print(chr(10).join(f'{k}: {v}' for k,v in c.most_common()))" 2>/dev/null || echo "(python error)"; else echo "(no parser)"; fi`
Last 7 days: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "0"; elif command -v jq >/dev/null 2>&1; then SINCE=$(date -u -d '7 days ago' +%FT%TZ 2>/dev/null || date -u -v-7d +%FT%TZ 2>/dev/null); if [ -z "$SINCE" ]; then echo "?"; else jq -s --arg since "$SINCE" 'map(select(.ts >= $since)) | length' "$F" 2>/dev/null || echo "0"; fi; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c "import json,os; from datetime import datetime, timedelta, timezone; cutoff=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat(); n=sum(1 for l in open(os.environ['STATS_FILE']) if l.strip() and json.loads(l).get('ts','')>=cutoff); print(n)" 2>/dev/null || echo "?"; else echo "?"; fi`
Last 5 entries: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ -f "$F" ]; then tail -5 "$F" 2>/dev/null; else echo "(no entries)"; fi`

## Your role

Format the stats above into a concise human-readable report. The bash preamble already aggregated everything — your job is to present the data, parse the pipe-separated `Tier breakdown` lines, and add light interpretation including a heuristic estimated-savings calculation.

The `Tier breakdown` line emits zero or more pipe-separated lines:

```
<tier>|count=N|total=N|input=N|output=N|cread=N|ccreate=N|dur_ms=N
```

Where `cread` = cache reads (~10% of fresh-input cost), `ccreate` = cache writes (full input cost), `total` = total tokens for that tier, `dur_ms` = total wall-clock duration.

## Output

Produce a markdown report with these sections:

### 1. Lifetime totals

- Total delegations: `<Total delegations>`
- Parser in use: `<Parser available>`. If `none`, surface that prominently — token breakdown will be unavailable for new entries.

### 2. By tier

For each tier line in `Tier breakdown`:

- delegation count
- total tokens (sum of `total_tokens` field across delegations in that tier)
- output tokens
- cache hit ratio (cread / (cread + ccreate + input)) if denominator > 0, expressed as a percentage
- total wall-clock duration in seconds (dur_ms / 1000)

Note that `unknown` tier means the hook fired without a parser (anonymous logging). `other` tier means non-claude-leverage subagent.

If any tier shows `total=0` for all 3+ delegations, mention that older entries (pre-v0.9.0) do not include token fields and only count toward the delegation total.

### 3. By subagent (top 10)

Sorted descending by delegation count from `By subagent` line above.

### 4. Last 7 days

Count from `Last 7 days` line + the 5 most-recent entries (parse the JSONL in `Last 5 entries`).

### 5. Estimated savings vs all-Opus baseline

**Always include this heuristic disclaimer verbatim:**

> _Heuristic estimate, not a measurement. Assumes Opus would have produced the same output token count as the cheaper tier did — which is unknowable. Real savings depend on whether Opus would have used more or fewer tokens, current Anthropic API pricing, and cache hit rates. Use as a directional signal._

Calculation:
- Take only sonnet and haiku tier rows where `total > 0`.
- Reference cost ratios vs Opus 4.x output-token pricing (current Anthropic public pricing as of 2026):
  - **Sonnet → Opus**: ~5× cheaper (output)
  - **Haiku → Opus**: ~25× cheaper (output)
- For each qualifying tier, compute "Opus-equivalent tokens" as `total × ratio`. The difference (`total × (ratio − 1)`) is the rough savings count.
- Skip the `other` tier entirely (uncertain model).

Format:

```
- Sonnet: actually consumed 130 000 tokens; Opus equivalent ~650 000 tokens (saved ~520 000 vs all-Opus)
- Haiku: actually consumed 35 000 tokens; Opus equivalent ~875 000 tokens (saved ~840 000 vs all-Opus)
- Combined heuristic savings: ~1 360 000 tokens at Opus output-cost rates
```

Skip this entire section if every tier has `total=0` (all entries are pre-Path-B).

### 6. Quick interpretation

1-2 sentences. Examples:
- "Sonnet dominates — typical for review/test/research-heavy sessions."
- "Cache hit ratio above 50 % — main session is reusing context efficiently."
- "Haiku tier unused — either no ultra-trivial commits, or `git-committer-quick` not installed."
- "Old entries make up most of the log; rerun more delegations to populate token data."

## Edge cases

- **`Stats file present: no`**: emit ONLY this friendly fallback and stop:

```
_No stats recorded yet._

The track-delegations hook writes to `~/.claude/claude-leverage-stats.jsonl` after each subagent delegation.

If you have already used `/code-review`, `/test`, `/commit-smart`, etc. in claude-leverage and still see this:
- Verify `jq` OR `python` (3 or 2) is installed. The hook prefers jq but falls back to python.
- Verify your platform supports the bash hooks (native Windows requires WSL2 or Git Bash; macOS/Linux/WSL2 work out of the box).
- Without any parser, the hook still logs anonymously — but the file would still exist. If it does not exist at all, the hook is not firing.
```

- **`Total delegations: 0` but file exists**: explain the file is empty.
- **`Parser available: none`**: surface prominently. Hook is logging anonymously. Recommend installing jq or python3.
- **`Tier breakdown` empty or `(install python or jq for breakdown)`**: token breakdown skipped, only counts available.
- **`Last 7 days: ?`**: the `date` binary did not support GNU or BSD relative-date syntax. Surface this rather than reporting a wrong number.
- **All tiers `total=0`**: all entries pre-Path-B. Mention this and skip the savings section.

## Hard rules

- Do not modify the stats file.
- Do not invent numbers. If a metric is missing, surface that honestly.
- Estimated savings MUST always carry the heuristic disclaimer, every time. Never present them as measurements.
- Do not estimate dollar costs unless current pricing of all relevant Anthropic models is known. Token-equivalent counts are safer.
- Mention the raw log location once at the bottom for users who want their own analysis.
