# Statusline

Portable Claude Code statusline. Single Python invocation, no `jq`
dependency, works on Windows (Git Bash / MSYS / WSL) and macOS / Linux.

## What it shows

```
5h: ███████░░░ 73% (1h42m) | 7d: ████░░░░░░ 38% (3d4h) | Ctx: ██░░░░░░░░ 22% | Sonnet 4.6 | # main
```

- **5h** — 5-hour rate-limit usage with countdown to reset
- **7d** — 7-day rate-limit usage with countdown to reset
- **Ctx** — current context-window usage
- **Model** — display name (Sonnet 4.6, Opus 4.7, …)
- **# branch** — current git branch (cwd-aware)

Color thresholds: green <60 %, yellow 60-84 %, red ≥85 %.

Earlier versions appended a session $cost estimate as the last segment.
That was removed in v1.2.0 — the number was unclear ("what currency?
estimate against what plan?") and only correct against the Opus rate
card, which not every user is on. Add it back manually if you want it:
the formula was `(total_input_tokens * 3 + total_output_tokens * 15) /
1_000_000` in Opus per-MTok USD.

## Install

### Via claude-leverage plugin

If you installed `claude-leverage` as a plugin, the statusline file is
shipped at `${CLAUDE_PLUGIN_ROOT}/statusline/statusline-command.sh` — you
can wire it into `~/.claude/settings.json` directly:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ${CLAUDE_PLUGIN_ROOT}/statusline/statusline-command.sh"
  }
}
```

### Standalone copy

```bash
mkdir -p ~/.claude
cp statusline/statusline-command.sh ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
```

Then add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/statusline-command.sh"
  }
}
```

(On Windows / Git Bash, `bash ~/.claude/statusline-command.sh` works because
the shell expands `~` to the Windows home directory before passing it
through to bash.)

### Codex CLI

Codex CLI does not currently have a statusline equivalent — this script is
Claude-Code-only.

## Requirements

- Python 3 on PATH (the script uses `python`; on macOS/Linux/WSL2 this
  resolves to `python3` via shebang or system alias; on Windows install
  from python.org or Microsoft Store).
- Git on PATH (for the branch indicator). If `git` is absent, the branch
  segment is silently dropped.

The script reads JSON from stdin (Claude Code's statusline contract) and
emits a single ANSI-colored line to stdout.

## Opt-out

Remove the `statusLine` block from `~/.claude/settings.json`. The file
itself can stay; Claude Code only invokes it when the config references
it.

To opt out of the cost-estimate segment, edit the script and remove the
"Session cost estimate" block at the bottom of the Python heredoc.

## Why a Python heredoc instead of a real script

Single-file deploy: no `import` of an installed module, no `pip install`
step, works on every fresh Windows machine that has Python out of the box.
The trade-off is that editing it is a little awkward (it's a string passed
to `python -c` via heredoc); for any non-trivial change, fork it into a
proper file.

## Customization

Common tweaks:

- **Hide cost estimate** (when not on Max/Pro and the rates are wrong):
  delete the `if total_in > 0 or total_out > 0:` block.
- **Different rates** (e.g., Haiku-heavy sessions): change the
  `(total_in * 3 + total_out * 15) / 1_000_000` constants.
- **Different colors**: see the `make_bar` function. `\033[31m` red,
  `\033[33m` yellow, `\033[32m` green; `\033[36m` cyan model, `\033[34m`
  blue branch, `\033[2m` dim separator.
