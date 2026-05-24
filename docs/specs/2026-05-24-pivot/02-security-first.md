# 02 — Security-first workflow

## Goal

Make security review part of the default development loop without making it
annoying. Two-layer defense:

- **Always-on (hooks)** — keep the current `block-secrets-precommit` and
  `block-dangerous-git`. These are deterministic, can't be bypassed by
  prompt injection, and don't depend on a model running.
- **On-demand-but-prompted (skill + subagent)** — a `/security-review` skill
  that audits the working diff against OWASP-Top-10-shaped patterns. Opus
  inline could do this, but a dedicated read-only Sonnet subagent gives:
  - Deterministic Markdown output (Critical / Important / Nice tiers)
  - Isolation from the main session's context (no risk of "fixing" findings
    by accident mid-review)
  - Codex parity (same skill, same subagent contract, different definition
    file)

## What gets caught

The skill is scoped to **what a coding agent might introduce on a single
diff** — not a full pentest. From OWASP Top 10 and the common AI-coding
failure modes:

| Category | Examples |
|----------|----------|
| Injection | SQL string interp, shell command injection, unescaped HTML/template, eval-on-user-input |
| AuthN/AuthZ | Missing auth checks on new routes, hardcoded credentials, weak token comparison (`==` instead of constant-time) |
| Secrets | API keys / private keys / tokens in source, .env not in .gitignore, secrets logged |
| SSRF / Path traversal | User input flowing to fetch URL or filesystem path without allowlist |
| Insecure deserialization | `pickle.loads` / `yaml.load` / `eval` on untrusted input |
| Crypto misuse | Insecure random for security, weak hash for passwords (MD5/SHA1), missing IV/nonce |
| Output encoding | XSS via unescaped user data into HTML/JS, log injection |
| Dependency footguns | Adding a package with known active CVE (best-effort; not a SAST replacement) |

The skill explicitly **does not** try to be Semgrep / CodeQL — it's a model
review focused on what would be embarrassing to ship. For deep static
analysis, the recommended pattern (documented in the skill) is to wire
Semgrep into pre-commit / CI separately.

## Trigger model

Three ways the skill can run:

1. **Explicit:** user types `/security-review`.
2. **Auto-suggested at `Stop`:** A `Stop` hook (`scripts/hooks/security-nudge.sh`)
   inspects the diff since session start. If net-new code crosses a
   threshold (default 80 LOC) AND touches files matching a sensitive-path
   pattern (`*auth*`, `*login*`, `routes/`, `api/`, `*crypto*`, `*payment*`,
   `templates/`, etc.), it prints a non-blocking stderr note:
   `(claude-leverage: 142 LOC of new code touched routes/ — run /security-review before committing)`.
   Never blocks. Never auto-runs.
3. **Pre-commit suggestion:** `block-secrets-precommit` already runs at
   `Bash(git commit:*)`. When the staged diff matches the same sensitive
   paths and exceeds the LOC threshold, the hook adds one extra line to its
   stderr suggesting `/security-review`. Still doesn't block — the existing
   secrets scan is the blocker.

Why not PreToolUse on Write/Edit? Too noisy. Per `research_ai_first_code.md`,
Cursor's data shows rules followed ~70% of the time, hooks 100% — but
notifications that fire on every file save train the user to ignore them.

## Skill + subagent contract

`skills/security-review/SKILL.md` (frontmatter):

```yaml
---
name: security-review
description: |
  Audits the current diff for OWASP Top 10 patterns and AI-coding failure
  modes. Use BEFORE committing security-sensitive changes (auth, crypto,
  user input handling, secret loading). Read-only — never modifies code.
allowed-tools: [Read, Grep, Glob, Bash(git diff:*), Bash(git status:*), Bash(git log:*)]
disable-model-invocation: false
---
```

Body: prompt that loads diff, walks each chunk, emits report in this shape:

```markdown
# Security review — <date>, <branch>, <files-changed-count> files

## Critical (must fix before commit)
- [file:line] <title> — <one-paragraph explanation + suggested fix>

## Important (fix before PR)
- [file:line] <title> — <explanation>

## Nice to have (next iteration)
- [file:line] <title> — <explanation>

## Out of scope (noted, not audited)
- <e.g. "third-party dependencies — run `npm audit` separately">
```

The skill delegates to the `security-reviewer` subagent for the actual
review pass — main session just orchestrates and presents.

`agents/security-reviewer.md`:
- Model: `sonnet` (cost vs accuracy tradeoff; Haiku misses too many).
- Tools: read-only — `Read`, `Grep`, `Glob`, `Bash(git diff:*)`,
  `Bash(git status:*)`. **No Edit/Write/MultiEdit.**
- Prompt enforces: cite file:line for every finding, no findings without a
  concrete suggested fix, max 1 paragraph per finding, prefer false-negative
  over false-positive on Nice-to-have tier.

Codex parity: `scripts/gen-codex-agents.py` produces
`.codex/agents/security-reviewer.toml` with equivalent fields.

## Existing skill in the ecosystem

The user already has `superpowers:security-review` and a built-in
`security-review` skill listed (both from official plugins). Question for
the user: **do we want to reuse one of those, or ship our own?**

My recommendation: ship our own as `claude-leverage:security-review` because:

- It's part of the personal stack identity — security review is the user's
  stated requirement.
- The existing ones may or may not delegate to a subagent the way we want;
  the cost/latency profile is different.
- The auto-suggest at `Stop` is the new piece that's not in the existing
  skills — that needs to live in this plugin.

If the existing skills turn out to be a superset, the right move is "remove
ours, depend on superpowers:security-review." That's a v1.1 cleanup
question; for v1.0 ship our own to keep the plugin self-contained.

## Open questions for review

1. **LOC threshold** for the Stop nudge. I propose 80 LOC of net-new code +
   sensitive-path match. Too aggressive (every feature triggers)? Too
   conservative (only big diffs)? Easy to tune; defaults matter for "out
   of the box" feel.
2. **Sensitive-path patterns.** I listed a generic set. Should this be
   per-project configurable via `.claude-leverage.toml` in the repo root?
   Adds complexity; might be worth it.
3. **Reuse vs ship-our-own.** See above. Recommendation: ship our own for
   v1.0, audit against existing for v1.1.
4. **Should the security skill also touch `package.json` / `requirements.txt`
   diffs** to flag newly-added deps for cross-checking against known CVE
   feeds? Genuinely useful but adds network dependency. Recommendation:
   defer to v1.1; v1.0 sticks to source-code patterns.
