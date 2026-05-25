# .githooks

Opt-in git hooks for this repo. **Not active until you enable them
locally** — the install is one git config line:

```bash
git config core.hooksPath .githooks
```

That points git's hook lookup at this directory instead of
`.git/hooks/`. Per-clone setting; never affects other contributors.

## What's wired

| Hook | What runs | Why |
|------|-----------|-----|
| `pre-push` | `scripts/smoke-plugin.sh --quiet` | Same 6-gate suite the AGENTS.md "Build / test" section documents (pytest, version sync, codex parity, shellcheck if installed, every hook returns 0 on minimal stdin, install-codex end-to-end). Blocks push on failure. |

The motivation: this repo's mission is "deterministic guardrails", and
having the pre-push gate be a script you have to remember to run is the
opposite of deterministic. Wiring it into `git push` itself closes the
loop.

## Why opt-in, not always-on

A plugin repo should not silently install git hooks for every cloner —
that crosses the "this is my repo" / "this is your shell" line. The
hook lives in-tree (so it travels with the repo and stays under review)
but only fires after you explicitly point `core.hooksPath` at it.

The smoke script itself remains runnable directly (`bash
scripts/smoke-plugin.sh`) whether or not the hook is installed; the
hook is a convenience for people who'd rather not remember.

## Disable

```bash
git config --unset core.hooksPath
```

## Bypass once

When the gate is wrong (e.g. shipping a docs-only change and shellcheck
flagged something pre-existing in an unrelated script), one-shot
bypass:

```bash
git push --no-verify
```

Note: the repo's `block-dangerous-git` hook treats blanket use of
`--no-verify` as a code smell — use it for the genuine one-off, not as
a routine.

## Why not `.git/hooks/pre-push`?

`.git/hooks/` is per-clone, untracked, and invisible to PR review. A
hook script that lives only there is a foot-gun: anyone joining the
project gets a different `git push` behavior than the author. Putting
the hook in `.githooks/` keeps it in version control where it can be
reviewed, evolved, and rolled back.
