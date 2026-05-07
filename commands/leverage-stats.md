---
description: Show claude-leverage delegation stats — lifetime totals, breakdown by tier and subagent, recent activity. Reads ~/.claude/claude-leverage-stats.jsonl populated by the track-delegations hook.
allowed-tools: Bash(jq:*), Bash(test:*), Bash(wc:*), Bash(tail:*), Bash(date:*)
---

## Context

Stats file present: !`test -f "$HOME/.claude/claude-leverage-stats.jsonl" && echo "yes" || echo "no"`
Total delegations: !`wc -l < "$HOME/.claude/claude-leverage-stats.jsonl" 2>/dev/null | tr -d ' ' || echo "0"`
By tier: !`jq -s -r 'group_by(.tier) | map("\(.[0].tier): \(length)") | join(", ")' "$HOME/.claude/claude-leverage-stats.jsonl" 2>/dev/null || echo "(jq missing or no data)"`
By subagent: !`jq -s -r 'group_by(.subagent) | map({s: .[0].subagent, n: length}) | sort_by(-.n) | map("\(.s): \(.n)") | join("\n")' "$HOME/.claude/claude-leverage-stats.jsonl" 2>/dev/null || echo "(jq missing or no data)"`
Last 7 days: !`jq -s --arg since "$(date -u -d '7 days ago' +%FT%TZ 2>/dev/null || date -u -v-7d +%FT%TZ 2>/dev/null || echo "0000-00-00T00:00:00Z")" 'map(select(.ts >= $since)) | length' "$HOME/.claude/claude-leverage-stats.jsonl" 2>/dev/null || echo "0"`
Last 5 entries: !`tail -5 "$HOME/.claude/claude-leverage-stats.jsonl" 2>/dev/null | jq -r '"\(.ts)  \(.subagent) [\(.tier)]"' 2>/dev/null || echo "(no entries)"`

## Your role

Format the stats above as a concise human-readable summary. The bash preamble already aggregated everything — your job is to present it cleanly and add light interpretation.

## Output

Produce a short markdown report with these sections:

1. **Lifetime totals** — total delegations, breakdown by tier (sonnet / haiku / other). One line per tier.
2. **By subagent** — sorted descending by count. Highlight any agent that is conspicuously missing from claude-leverage (e.g., if `git-committer-quick` has 0 delegations and the user has `git-committer` activity, note that ultra-trivial routing is not engaging).
3. **Last 7 days** — count + the last 5 individual delegations.
4. **Quick interpretation** — 1-2 sentences. Examples:
   - "Sonnet dominates — typical for review/test/research-heavy sessions."
   - "Haiku tier unused — either no ultra-trivial commits, or `git-committer-quick` not installed."
   - "Heavy `code-reviewer` use, no `context-gatherer` — consider running `/gather-context` before non-trivial work to save more tokens up front."

## Edge cases

- If `Stats file present: no`: emit ONLY this friendly message and stop:

```
_No stats recorded yet._

The track-delegations hook writes to `~/.claude/claude-leverage-stats.jsonl` after each subagent delegation.

If you have already used `/code-review`, `/test`, `/commit-smart`, etc. in claude-leverage and still see this:
- Verify `jq` is installed (the hook needs it; without it the hook silently exits without logging).
- Verify your platform supports the bash hooks (native Windows requires WSL2 or Git Bash; macOS/Linux/WSL2 work out of the box).
- After installing `jq`, future delegations will start populating the stats file.
```

- If `Total delegations: 0` but the file exists: same as above but with a note that the file is empty (might mean the hook ran but logged nothing — usually means non-leverage subagents only, or jq present but case statement did not match).

- If any breakdown shows `(jq missing or no data)`: tell the user `jq` is missing on the system running the bash preamble. Without `jq`, the stats hook also cannot log new entries — recommend installing it.

## Hard rules

- Do not modify the stats file.
- Do not invent numbers. If a metric is missing, surface that honestly rather than guessing.
- Do not estimate token savings in dollars or percentages. The log records counts, not tokens. Use phrases like "N delegations to Sonnet" not "saved $X".
- The raw log is at `~/.claude/claude-leverage-stats.jsonl` (one JSON record per line). Mention this once at the bottom for users who want to do their own analysis (e.g., pipe into `jq` for custom queries).
