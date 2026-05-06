# Docs sync routing

This snippet is opt-in. It tells the main session to *remind* the user to run `/docs-sync` after substantial changes - it does NOT auto-route to the subagent.

## Rule

After completing a feature implementation or bug fix that adds/changes/removes:

- Public APIs or exported functions
- CLI flags, command-line arguments, or environment variables
- Configuration file schemas
- User-visible behavior (error messages, output formats)
- Build/install steps

…remind the user once: "Documentation may be stale. Run /docs-sync to check?"

Do NOT run `/docs-sync` automatically. The user decides whether docs are in scope for the current commit.

## When NOT to remind

- Internal refactors that don't change any user-visible surface
- Test-only changes
- Tooling/CI tweaks
- Doc-only commits (the loop would be circular)
- When the user explicitly said docs are out of scope for this session

## How to use

Append this snippet to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level).

This pairs with `agents/docs-updater.md` and the `/docs-sync` command. It is intentionally a reminder, not auto-routing - documentation updates often involve judgment calls about what's worth documenting, and surprising the user with auto-edits to README/CHANGELOG would violate the trust boundary.

## Why opt-in

The docs-updater agent is conservative by design - it returns confidence-labeled suggestions and the main session decides what to apply. But the *trigger* for running it is also a judgment call: small commits often don't warrant a doc check. Keeping this as a reminder rather than auto-routing avoids "the agent that cried docs" pattern, where users learn to ignore it.

If you want zero friction, you can adapt this rule to "after any commit, run /docs-sync once per session" - but most teams find the reminder pattern hits the right balance.
