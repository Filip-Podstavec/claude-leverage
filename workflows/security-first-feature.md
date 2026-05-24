# Workflow: shipping a security-sensitive feature

The scenario: you're adding a new endpoint that handles authentication,
authorization, payments, secrets, or user input that touches sensitive
state. You want to ship it without (a) leaking secrets, (b) introducing
an OWASP-Top-10-shaped bug, or (c) leaving the next agent (human or AI)
without enough context to safely extend it.

This guide walks through how the stack helps at each step. Most of it
runs automatically; you invoke a skill explicitly twice (once for
context, once for review).

## Before you start

If the repo doesn't yet have an `AGENTS.md` documenting the conventions
this stack assumes:

```
/init-repo
```

The skill walks you through dropping in a per-language `AGENTS.md`, a
`.gitignore` block for the stack's state files, and (optionally) a
structured-logging starter kit. The new `AGENTS.md` includes the
`AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION` convention and the
JSON-lines logging spec — both of which the next agent will be looking
for. Skip this if the repo already has an AGENTS.md you maintain.

## While you write the code

Three things happen passively, without you doing anything:

### 1. Security hooks intercept dangerous Bash calls

- **`block-secrets-precommit`** runs before every `git commit`. If the
  staged diff contains anything matching API key / token / private key
  patterns (Stripe, AWS, GitHub PAT, Anthropic, OpenAI-style, etc.), the
  commit is **blocked**. Per-line allowlist via the
  `claude-leverage-allow-secret` marker comment for fixture / mock
  strings that look like secrets.
- **`block-dangerous-git`** blocks `git push --force`, `git commit
  --no-verify`, and `git reset --hard` on protected branches
  (`main` / `master`).

You don't invoke these. They run on every Bash tool call. If one of
them blocks, the model sees the exit-2 error and has to find a
non-bypassing path.

### 2. AI-first nudges flag missing context as you write

After each `Write` / `Edit` / `MultiEdit` of ≥50 net-new LOC in a
non-test file, the `ai-first-nudge` hook checks whether the change
contains any `AIDEV-NOTE:` anchor. If not, you see one line on stderr:

```
(claude-leverage: 73 LOC of net-new code in services/billing/charge.py
 with no AIDEV-NOTE anchor — consider anchoring load-bearing parts)
```

Non-blocking. Frequency-capped to once per file per day. Aimed at
load-bearing decisions — regulatory carve-outs, ordering dependencies,
idempotency tricks, perf workarounds. Don't decorate every function.

A parallel check fires when a new file lands inside a recognized source
root (`src/`, `lib/`, `app/`, `apps/`, `pkg/`, `internal/`, `services/`,
`api/`, `cmd/`, `crates/`, `packages/`, including monorepo-nested) AND
the parent dir has 8+ source files AND no `AGENTS.md` is present
anywhere up to the repo root:

```
(claude-leverage: services/billing has 11 source files but no AGENTS.md
 anywhere up to repo root — as the module grows, an AGENTS.md helps
 next agents orient)
```

Cap: once per dir per day. The signal is "this module is getting
substantial; consider a module-level AGENTS.md."

### 3. Optionally, prepare logging discipline upfront

If the feature involves any logging that another service or an agent
will later need to read (most do), use the structured-logging spec from
`AGENTS.md`. Drop-in starter kits per language in
`templates/logging/{python,typescript,go,rust}.md`. `/init-repo` can
install the matching one. The audit skill `/log-structured` can later
find non-conforming logs in the surrounding codebase if you want to
harmonize.

## When the feature is ready

You've finished the implementation. Two passes before commit:

### 1. Run `/security-review`

```
/security-review
```

Delegates to the read-only `security-reviewer` subagent (Sonnet). Walks
the staged diff (falls back to unstaged if nothing's staged) against
OWASP-Top-10-shaped patterns:

- Injection (SQL string interp, shell injection, eval-on-user-input)
- AuthN/AuthZ (missing auth check on new route, hardcoded creds, weak
  token compare)
- Secrets (keys/tokens in source, secrets in logs)
- SSRF / path traversal
- Insecure deserialization (`pickle.loads`, `yaml.load` without
  SafeLoader, etc.)
- Crypto misuse (insecure RNG for security, MD5/SHA1 for passwords,
  ECB mode, nonce reuse)
- Output encoding (XSS, log injection, open redirects)
- Newly added dependencies that look like typosquats (1-char distance
  from popular package names) or use suspicious version pins (`*`,
  `latest`, unpinned git URLs)
- Misc (disabled TLS verification, broad CORS with credentials, debug
  endpoints in prod paths)

Returns a deterministic Markdown report with Critical / Important /
Nice / Out-of-scope tiers, each finding cited at `file:line`. The skill
relays the report verbatim and asks "fix all Critical, fix one, commit
as-is."

### 2. The Stop hook may suggest /security-review automatically

If you forgot to run it explicitly, the `security-nudge` Stop hook
fires when the session-wide diff crosses 80 net-new LOC AND at least
one changed file matches a sensitive-path pattern (`*auth*`,
`*crypto*`, `routes/`, `payment*`, `templates/`, `*.env*`, etc.).
One line on stderr:

```
(claude-leverage: 142 LOC of net-new code touches services/auth/handlers.py
 — consider running /security-review before commit)
```

Non-blocking, one-per-branch-per-day cap. The hook is the safety net
for the case where you got tunnel-vision and forgot the explicit
review.

## Commit

```
/commit-smart
```

All-inline (no subagent dispatch). Reads the staged diff, scans for
problems the secrets hook didn't already catch (debug prints, broken
syntax), checks for unsafe path patterns, writes a Conventional Commits
message in the repo's existing style, commits, and pushes (with
upstream tracking if missing).

Hard rules built into the command (and reinforced by the hooks):
- Refuses to commit `.env`, API keys, tokens, anything that looks like
  a credential.
- Never force-pushes.
- Never uses `--no-verify`.
- Never amends or rebases.
- Never writes code (commits what's staged; you decide what to write).

## After commit

### 1. Anchor your AIDEV decisions for the next agent

If `/security-review` flagged Important findings that you decided NOT
to fix in this PR (because they need broader refactor or the risk is
contained), drop an `AIDEV-TODO(by: 2026-08-01):` anchor with the
deadline. Example:

```python
# AIDEV-TODO(by: 2026-08-01): replace the string-concat SQL in
# legacy_search() with parameterized query — flagged Important by
# /security-review on commit a1b2c3d
def legacy_search(term: str) -> list[Row]:
    ...
```

`/stack-check`'s anchor walk will surface this as **overdue** after
the deadline passes, even if you haven't touched the file. The skill
runs naturally every ~30 days (the SessionStart `stack-freshness`
nudge prompts it).

### 2. Open the PR / share the change

```
/explain-diff --for pr
```

Generates a `Summary / Why / How to verify` block to paste into the PR
description. Optionally `--for review` for a load-bearing vs
mechanical breakdown if a teammate is reviewing.

## What this workflow does NOT do for you

- **Static analysis** (Semgrep, CodeQL, Bandit) — wire one of those
  into CI separately. `/security-review` is a model review, not SAST.
- **Dependency CVE scanning** — use `npm audit` / `pip-audit` /
  `cargo audit` / `govulncheck` per ecosystem. The security skill
  reports typosquatting heuristics, not the CVE database.
- **End-to-end / integration testing** — write your own tests; this
  stack helps with `/flaky-test` once tests exist.
- **Architecture review** — out of scope for a diff-shaped review.
  Pair with the `superpowers` plugin's brainstorming/planning skills
  for the bigger picture.

## Recap (commands you actually type)

For a typical sensitive-feature PR, you invoke the stack ~3 times:

```
/init-repo            # only once per project, if it doesn't have AGENTS.md yet
# ... write code ...  # hooks fire passively
/security-review      # before commit
/commit-smart         # commit + push
/explain-diff --for pr # generates PR description block
```

Everything else (hook checks, nudge cap tracking, dep-diff scan inside
the security review, anchor age tracking) runs automatically.
