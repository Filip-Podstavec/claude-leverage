---
description: Show claude-leverage delegation stats — lifetime totals, breakdown by tier and subagent, recent activity. Reads ~/.claude/claude-leverage-stats.jsonl populated by the track-delegations hook.
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(python:*), Bash(test:*), Bash(wc:*), Bash(tail:*), Bash(date:*), Bash(command:*), Bash(tr:*)
---

<!--
  Security note for future reviewers:
  $F = $HOME/.claude/claude-leverage-stats.jsonl is always passed to jq/python
  as a double-quoted positional argument or via the STATS_FILE env var. It is
  never interpolated into the jq filter string or the Python -c script body,
  so a hostile $HOME containing shell metacharacters cannot inject commands.
  The Python -c body is single-quoted at the shell level; the path is read
  inside Python via os.environ['STATS_FILE'], not via shell expansion.
-->

## Context

Stats file present: !`test -f "$HOME/.claude/claude-leverage-stats.jsonl" && echo "yes" || echo "no"`
Total delegations: !`if [ -f "$HOME/.claude/claude-leverage-stats.jsonl" ]; then wc -l < "$HOME/.claude/claude-leverage-stats.jsonl" | tr -d ' '; else echo "0"; fi`
Parser available: !`if command -v jq >/dev/null 2>&1; then echo "jq"; elif command -v python3 >/dev/null 2>&1; then echo "python3"; elif command -v python >/dev/null 2>&1; then echo "python"; else echo "none"; fi`
By tier: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "(no data)"; elif command -v jq >/dev/null 2>&1; then jq -s -r 'group_by(.tier) | map("\(.[0].tier): \(length)") | join(", ")' "$F" 2>/dev/null || echo "(jq error)"; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c "import json,os; from collections import Counter; rs=[json.loads(l) for l in open(os.environ['STATS_FILE']) if l.strip()]; c=Counter(r.get('tier','?') for r in rs); print(', '.join(f'{k}: {v}' for k,v in sorted(c.items())))" 2>/dev/null || echo "(python error)"; else echo "(no parser)"; fi`
By subagent: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "(no data)"; elif command -v jq >/dev/null 2>&1; then jq -s -r 'group_by(.subagent) | map({s: .[0].subagent, n: length}) | sort_by(-.n) | map("\(.s): \(.n)") | join("\n")' "$F" 2>/dev/null || echo "(jq error)"; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c "import json,os; from collections import Counter; rs=[json.loads(l) for l in open(os.environ['STATS_FILE']) if l.strip()]; c=Counter(r.get('subagent','?') for r in rs); print(chr(10).join(f'{k}: {v}' for k,v in c.most_common()))" 2>/dev/null || echo "(python error)"; else echo "(no parser)"; fi`
Last 7 days: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ ! -f "$F" ]; then echo "0"; elif command -v jq >/dev/null 2>&1; then SINCE=$(date -u -d '7 days ago' +%FT%TZ 2>/dev/null || date -u -v-7d +%FT%TZ 2>/dev/null || echo '0000-00-00T00:00:00Z'); jq -s --arg since "$SINCE" 'map(select(.ts >= $since)) | length' "$F" 2>/dev/null || echo "0"; elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then PY=$(command -v python3 || command -v python); STATS_FILE="$F" "$PY" -c "import json,os; from datetime import datetime, timedelta, timezone; cutoff=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat(); n=sum(1 for l in open(os.environ['STATS_FILE']) if l.strip() and json.loads(l).get('ts','')>=cutoff); print(n)" 2>/dev/null || echo "?"; else echo "?"; fi`
Last 5 entries: !`F="$HOME/.claude/claude-leverage-stats.jsonl"; if [ -f "$F" ]; then tail -5 "$F" 2>/dev/null; else echo "(no entries)"; fi`

## Your role

Format the stats above as a concise human-readable summary. The bash preamble already aggregated everything — your job is to present it cleanly and add light interpretation.

## Output

Produce a short markdown report with these sections:

1. **Lifetime totals** — total delegations, breakdown by tier (sonnet / haiku / other / unknown). One line per tier. Note that `unknown` entries indicate a delegation was logged but the parser was unavailable when it fired (jq/python missing at hook time).
2. **By subagent** — sorted descending by count. The "Last 5 entries" raw JSON lines are above; you can mention specific subagents from those.
3. **Last 7 days** — count + the last 5 individual delegations (parse the raw JSON in "Last 5 entries").
4. **Quick interpretation** — 1-2 sentences. Examples:
   - "Sonnet dominates — typical for review/test/research-heavy sessions."
   - "Haiku tier unused — either no ultra-trivial commits, or `git-committer-quick` not installed."
   - "Heavy `code-reviewer` use, no `context-gatherer` — consider running `/gather-context` before non-trivial work to save more tokens up front."
   - "All entries are `unknown` — the track-delegations hook is firing but cannot identify subagents (no jq/python available). Install one to get detailed breakdown going forward."

## Edge cases

- **`Stats file present: no`**: emit ONLY this friendly message and stop:

```
_No stats recorded yet._

The track-delegations hook writes to `~/.claude/claude-leverage-stats.jsonl` after each subagent delegation.

If you have already used `/code-review`, `/test`, `/commit-smart`, etc. in claude-leverage and still see this:
- Verify `jq` OR `python` (3 or 2) is installed. The hook prefers jq but falls back to python.
- Verify your platform supports the bash hooks (native Windows requires WSL2 or Git Bash; macOS/Linux/WSL2 work out of the box).
- Without any parser, the hook still logs anonymously — but the file would still exist. If it does not exist at all, the hook is not firing.
```

- **`Total delegations: 0` but file exists**: explain the file is empty (might mean the hook ran but the matcher did not fire — or the hook wrote zero records, which suggests a parser issue).

- **`Parser available: none`**: surface this prominently. The hook is logging anonymously (subagent="unknown"). Recommend installing `jq` (`winget install jqlang.jq` / `brew install jq` / `sudo apt install jq`) or ensuring `python3` is on PATH so future delegations get detailed breakdown.

## Hard rules

- Do not modify the stats file.
- Do not invent numbers. If a metric is missing, surface that honestly rather than guessing.
- Do not estimate token savings in dollars or percentages. The log records counts, not tokens. Use phrases like "N delegations to Sonnet" not "saved $X".
- The raw log is at `~/.claude/claude-leverage-stats.jsonl` (one JSON record per line). Mention this once at the bottom for users who want to do their own analysis (e.g., pipe into `jq` for custom queries).
