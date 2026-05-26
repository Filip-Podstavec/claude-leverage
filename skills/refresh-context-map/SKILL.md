---
name: refresh-context-map
description: USE WHEN AIDEV anchors / per-dir AGENTS.md / ADRs have changed in this repo and the smart-context-surfacing PreToolUse hook needs an updated manifest. Rebuilds `.claude-leverage-context-map.json` at the repo root by running `scripts/build-context-map.py`. Read-only on source — only writes the manifest.
---

# refresh-context-map

Rebuild the smart-context-surface manifest used by the PreToolUse hook
(`scripts/hooks/context-surface.sh`). See
[`docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md`](../../docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md)
for the design rationale.

## When to invoke

- After adding / moving / deleting `AIDEV-NOTE` / `AIDEV-TODO` / `AIDEV-QUESTION` anchors.
- After adding / removing per-directory `AGENTS.md` files.
- After adding new ADRs in `docs/adr/` that reference specific source files.
- After a `git merge` that touched anchor-bearing files (`.gitattributes` keeps
  the local manifest on conflict via `merge=ours`, but it'll be stale relative
  to the merged tree until rebuilt).
- When `/stack-check` flags drift between the manifest and `git ls-files`.
- Once per significant refactor that moved a lot of files.

## When NOT to invoke

- On every commit — opt-in pre-commit hook (`.githooks/`) does it automatically
  if enabled. If you've enabled it, manual `/refresh-context-map` is redundant.
- When you have not adopted the smart-context-surfacing stack in this repo
  (no `.claude-leverage-context-map.json` present means the PreToolUse hook
  silently no-ops — nothing to refresh).

## What it does

Runs:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/build-context-map.py
```

from the repo root. The script:

1. Walks every git-tracked file (via `git ls-files`), skipping binaries (NUL-byte sniff).
2. For each file with `AIDEV-*` anchors, indexes:
   - Anchors inside the file
   - Anchors in sibling files (same directory)
   - The chain of `AGENTS.md` from `dirname(file)` to repo root
   - ADR files (`docs/adr/*.md`) that mention this file path verbatim (word-boundary match)
3. Writes `.claude-leverage-context-map.json` at the repo root, **atomically** (`.tmp` + rename).

The PreToolUse hook reads this manifest on every `Read/Edit/Write/MultiEdit`
and injects a per-file context slice via `hookSpecificOutput.additionalContext`.

## Verifying the rebuild

After running, the script prints a summary line:

```
Wrote ./.claude-leverage-context-map.json (234 files, 89 anchors)
```

Higher numbers than last time → you've added anchors / ADR references.
Lower numbers → anchors were deleted or files removed from `git ls-files`.

To check drift without writing (CI use):

```bash
python scripts/build-context-map.py --check
# exit 0 if up to date, exit 1 with "DRIFT:" line on stderr if regen would differ
```

## Opting out per-session

Set `CLAUDE_LEVERAGE_CTX_DISABLE=1` in the environment to disable the hook
entirely without removing the manifest. Useful for one-off diagnostic sessions
where the context injection is noise.

## Verbose mode

By default the hook surfaces only `AIDEV-*` anchors (the trap-catching content
per the Run-3 token-tax finding). Set `CLAUDE_LEVERAGE_CTX_VERBOSE=1` to also
include per-dir `AGENTS.md` references and related ADR paths in every
injection. Useful in repos where the per-dir AGENTS.md surface is dense and
worth the extra tokens; off by default to keep the tax minimal in the common
case.
