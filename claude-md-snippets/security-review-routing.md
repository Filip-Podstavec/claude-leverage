# Security-review routing

Drop-in CLAUDE.md / AGENTS.md snippet that promotes `/security-review`
from "the Stop hook might suggest it" to "the project mandates it
before commit" on diffs touching sensitive paths.

`/init-repo` offers to install this snippet for projects with auth,
crypto, payment, or template code.

## Snippet

Append the block between the markers below into your project's
`AGENTS.md` (preferred — both Claude Code and Codex see it) or
`CLAUDE.md` / `~/.claude/CLAUDE.md`. The markers are load-bearing for
the future-`/install-snippets`-style auto-update story; keep them
byte-identical when copying.

```markdown
<!-- claude-leverage:security-review-routing START -->

## Security review routing

Before committing changes in any of the following paths, run
`/security-review` and address Critical findings before push:

- `auth/`, `*/auth/*`, `login/`, `signup/`, `session/`
- `crypto/`, `encrypt/`, `decrypt/`, `hash/`, `password/`, `passwd/`
- `secret/`, `token/`, `credential/`, `.env*`, `*.pem`, `*.key`
- `payment/`, `billing/`, `invoice/`, `charge/`, `stripe/`
- `routes/`, `*/routes/*`, `api/`, `*/api/*`, `controllers/`
- `templates/`, `views/`, `middleware/`

These are the same patterns that power the `security-nudge` Stop hook,
which suggests `/security-review` automatically when net-new code in
these paths crosses 80 LOC in a session. This routing rule promotes
that *suggestion* to *required before push*.

If `/security-review` reports Important findings that won't be fixed
in this PR, anchor them with a deadline so they don't quietly
accumulate:

```python
# AIDEV-TODO(by: YYYY-MM-DD): <finding> — flagged by /security-review on <commit>
```

`/stack-check` will surface overdue anchors automatically.

<!-- claude-leverage:security-review-routing END -->
```

## When to install

- New project where the codebase touches user auth, payments, or
  templated output that could be XSS-vector.
- Existing project after a security incident (post-mortem usually
  identifies the convention you wished you'd had).
- Hand-off from one contractor to another — the routing rule encodes
  the security review as project policy, not individual discipline.

## When NOT to install

- Internal tools / scripts with no sensitive surface (just adds noise).
- Projects where you've wired Semgrep / CodeQL / etc. into CI as the
  primary gate — the stack's `/security-review` is a model review and
  is meant to complement, not replace, those.
