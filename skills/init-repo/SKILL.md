---
name: init-repo
description: |
  Bootstrap a project with the claude-leverage conventions: drop an
  AGENTS.md from templates/AGENTS.md.example (per-language), add
  recommended .gitignore patterns for the stack's state directories,
  and optionally install a structured-logging template per detected
  language. Interactive — confirms each addition before writing.
  Idempotent — re-running detects existing claude-leverage blocks via
  marker comments and offers update-in-place.
  Cross-tool (Claude Code and Codex).
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash(test:*)
  - Bash(ls:*)
  - Bash(git rev-parse:*)
argument-hint: "[target-dir] [--lang python|typescript|go|rust|none] [--noninteractive]"
---

# /init-repo

## What it does

Sets up a fresh (or existing) repository to use the claude-leverage
stack's conventions:

1. **AGENTS.md** — drops a customized copy of
   [`templates/AGENTS.md.example`](../../templates/AGENTS.md.example),
   with placeholders filled in from the detected project name, stack,
   and conventions.
2. **CLAUDE.md** — creates a one-line `@AGENTS.md` import file so Claude
   Code sees the canonical guidance.
3. **.gitignore** — appends a block (between markers) ignoring the
   stack's local state dirs (`.last-stack-check`, session-nudge files)
   and per-language artifacts that would otherwise show up in `/repo-map`
   noise.
4. **Logging template** (optional, per detected language) — drops the
   matching `templates/logging/<lang>.md` body into a sensible path in
   the project (e.g., `src/<pkg>/logging_setup.py`).
5. **AIDEV-NOTE convention reminder** — a single line at the top of the
   new AGENTS.md pointing at the spec.

Each step is **confirmed before write**. Re-running detects already-
installed sections via marker comments and offers update-in-place.

## Workflow

1. **Resolve target dir.** Default cwd. If `$ARGUMENTS` has a path, use
   that. Verify it's a git repo (`git rev-parse --show-toplevel` from
   the target). If not, ask the user: "this isn't a git repo — `git
   init` first, or proceed anyway?"

2. **Detect language** from file presence. Check in order:
   - `package.json` → TypeScript / Node.js
   - `pyproject.toml` / `setup.py` / `requirements.txt` → Python
   - `go.mod` → Go
   - `Cargo.toml` → Rust
   - Mixed / none → ask the user, default `none`.
   - Override with `--lang` flag.

3. **Read project name** from manifest (`package.json#name`,
   `pyproject.toml [project] name`, `go.mod` first line, `Cargo.toml
   [package] name`). Fall back to directory name.

4. **Plan the changes** as a numbered list. Show the user:
   ```
   I'll add the following to <target-dir>:
     1. AGENTS.md       — customized for <lang>, project name <name>
     2. CLAUDE.md       — single @AGENTS.md import line
     3. .gitignore      — append claude-leverage state patterns (~5 lines)
     4. <pkg>/logging_setup.<ext>  — structured-logging starter
   Proceed? (y / n / select-subset)
   ```
   Unless `--noninteractive`, wait for confirmation. With
   `--noninteractive`, write all 4.

5. **For each accepted change:**

   ### 5a. AGENTS.md
   - Read `templates/AGENTS.md.example`.
   - Substitute placeholders:
     - `<project-name>` → resolved name
     - `<one-line purpose>` → ask user (or "TODO: fill in")
     - `<languages, primary frameworks>` → detected
     - `<install-cmd>`, `<test-cmd>`, etc. → ask user, infer from
       manifest if possible
   - Per-language extras section:
     - For Python: add `pytest` test command, ruff/black lint guidance
     - For TS: add `npm test`, eslint guidance
     - For Go: add `go test ./...`, `golangci-lint` guidance
     - For Rust: add `cargo test`, `cargo clippy` guidance
   - Wrap the file body in marker comments:
     `<!-- claude-leverage:agents-md START -->` / `... END -->` so
     future re-runs can detect and offer update-in-place.
   - Write to `<target>/AGENTS.md`. If a non-managed AGENTS.md exists,
     STOP and ask: "an unmanaged AGENTS.md exists; merge / overwrite /
     skip?"

   ### 5b. CLAUDE.md
   - If exists with `@AGENTS.md` already: skip (idempotent).
   - If exists without `@AGENTS.md`: ask "prepend `@AGENTS.md` to your
     existing CLAUDE.md?"
   - If absent: write `@AGENTS.md\n`.

   ### 5c. .gitignore
   - Wrap appended block in markers:
     ```
     # <!-- claude-leverage:gitignore START -->
     # claude-leverage local state (per-machine, do not commit)
     .last-stack-check
     session-nudges-*.txt
     security-nudges-*.txt
     # <!-- claude-leverage:gitignore END -->
     ```
   - If markers exist already: replace block in place (rules may have
     evolved across plugin versions).
   - If no `.gitignore`: create one with just this block.

   ### 5d. Logging template
   - Read `templates/logging/<lang>.md`.
   - Extract the language-specific code block (between the first
     "```<lang>" fence and matching close).
   - Suggest target path:
     - Python: `src/<pkg_name>/logging_setup.py` (or
       `<pkg_name>/logging_setup.py` if no `src/` layout)
     - TypeScript: `src/lib/logging.ts`
     - Go: `internal/logging/logging.go`
     - Rust: `src/logging.rs`
   - Ask user to confirm or override the path.
   - Write only if file doesn't exist (don't overwrite working code).

6. **Summarize.** Report what was written, what was skipped, what
   needs human follow-up (e.g., placeholder `<one-line purpose>`).

## Hard rules

- **Confirm before write.** Default is interactive. `--noninteractive`
  is for scripted use only.
- **Idempotent.** Re-running finds marker blocks and offers update-in-
  place rather than appending duplicates.
- **Never overwrite working logging code.** If `logging_setup.<ext>`
  already exists at the target path, skip and report it.
- **Never invent project metadata.** Fields like "purpose" or
  "stack details" get a `TODO: fill in` placeholder if the user
  cannot answer.
- **Refuse on non-git dirs unless explicitly allowed.** Random
  directory bootstrap is a foot-gun; require the user to opt in if
  they really want it.

## Tunables

- `--lang <name>` — skip detection, use this language.
- `--lang none` — no logging template, just AGENTS.md / CLAUDE.md /
  .gitignore.
- `--noninteractive` — confirm nothing, write all 4. Use in
  install-time scripts.
- `--dry-run` — print what would be written, write nothing.

## When to run

- First time setting up a new repo where you want this stack's
  conventions to apply.
- Onboarding an existing repo to the conventions (skill detects
  existing AGENTS.md and offers merge).
- After a major plugin version bump that ships new convention sections
  (skill detects drift via markers and offers update).

Pairs with `/log-structured` (audit existing logs against the spec)
and `/security-review` (audit changes once the conventions are in
place).

## What this skill does NOT do

- **Configure CI.** Adding GitHub Actions / Codex hooks / etc. is too
  project-specific; this skill just sets up the AGENTS.md guidance.
- **Run `git init`.** That's a user-level decision; we offer to
  proceed-anyway if missing.
- **Install language toolchains.** If you're on a Python project
  without `pyproject.toml`, this skill won't `pip install` anything —
  it just suggests what to add.
