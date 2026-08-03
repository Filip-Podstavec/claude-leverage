# Workflow: onboarding a legacy repo you just inherited

You opened a repo for the first time. It has no claude-leverage conventions —
maybe no `AGENTS.md` at all, sparse comments, `print()` logging, no `docs/adr/`.
It might be large and messy. You need to start working in it *and* leave it more
AI-ready than you found it.

The trap is the heroic first PR: a sweep that adds anchors everywhere, rewrites
all the logging, and refactors the architecture before you've shipped a single
real change. That's slop in the other direction — it's high-risk, reviewers
can't read it, and it fights the
[`Write less, fit in`](../AGENTS.md#write-less-fit-in) principle. **Onboarding is
incremental: the repo gets AI-ready as you touch it, not in one heroic PR.**

This guide splits the work into two buckets:

- **One-time setup** (steps 1–4) — cheap, additive, safe to do up front in one
  sitting. They create files; they don't touch existing code.
- **As you touch code** (steps 5–6) — done gradually, in the same commits as
  the actual feature/bugfix work that brings you into each part of the repo.

## Step 1 — Audit first (read-only): `/repo-doctor`

Before changing anything, get the map. `/repo-doctor` is read-only on the repo
(writes only local state for its score trend) and scores ~24 dimensions
(Foundation / Why / What / In-code / Hygiene / Sync), each with a
concrete fix action.

```
/repo-doctor
```

You get a score and a gap list: missing `AGENTS.md`, no ADRs, no glossary, low
anchor density, unstructured logging, code↔docs drift. **Don't act on all of it
at once.** Use it as the to-do list the rest of this workflow works through, and
as the baseline you'll re-measure against at the end.

## Step 2 — Lay the foundation: `/init-repo`

```
/init-repo
```

Drops an `AGENTS.md` (from the per-language template, with build/test commands
filled in), a one-line `@AGENTS.md` import in `CLAUDE.md`, and `.gitignore`
patterns for the stack's state dirs. Idempotent via marker blocks.

**If the repo already has an `AGENTS.md`, `CONTRIBUTING.md`, or similar:** do not
clobber it. `/init-repo`'s markers let it coexist — merge the stack's conventions
into the existing guidance rather than replacing what the previous maintainers
wrote. Their notes are load-bearing context you don't want to lose.

The first thing to fill in by hand is the **Project** section (what this repo is
and for whom) and **Repo layout** (top-level dirs). That single paragraph is the
highest-leverage thing you'll write all day — it's what the next agent reads
first.

## Step 3 — Capture the vocabulary: `/glossary-init`

```
/glossary-init
```

Surfaces candidate domain terms by identifier frequency and asks you for a
one-sentence definition each. Writes `GLOSSARY.md` at the repo root.

This **reduces domain-term misreads** — when an agent sees `Lead` or `Tenant` or
`Settlement`, it reads your repo's meaning instead of guessing the generic one.
The skill never invents definitions; if you don't know a term yet, skip it and
add it later (re-running is additive).

## Step 4 — Mark what's safe to touch: `/arch-map`

```
/arch-map
```

Writes `architecture.yml` at the root: per-module `role` / `stability` /
`public_surface` / `depends_on`. The stability field is what matters most on a
legacy repo — labelling a module `stable`, `evolving`, `experimental`, or
`legacy` tells the next agent (and you, next month) which code is load-bearing
and which is safe to change freely. The skill drafts; you confirm.

## Step 5 — Logging, opportunistically: `/log-structured`

```
/log-structured
```

Read-only audit: finds `print()` / `console.log` / interpolated logger calls and
suggests spec-compliant JSON-lines replacements per `file:line`. **Do not
mass-rewrite.** A repo-wide logging migration is its own project with its own
risk. Instead, treat the report as a backlog: when you're already editing a file
for a real reason, fix the logging in that file as part of the same commit.

## Step 6 — Anchor as you discover, not in a sweep

As you work through actual tasks, you'll learn the non-obvious things: the
ordering dependency, the regulatory carve-out, the reason a function looks weird.
That's the moment to drop an `AIDEV-NOTE` — right where you discovered it, in the
commit that touches that code. The `ai-first-nudge` hook will remind you when a
large change ships with no anchor.

Resist the urge to retro-anchor the whole codebase. An anchor is only worth its
line if it captures a *load-bearing fact you had to dig for*. An anchor on every
function is the same noise as a comment on every line.

## Step 7 — Confirm progress, then keep going

After a few sessions of real work with steps 5–6 woven in:

```
/repo-doctor          # did the score move? what gaps remain?
/refresh-context-map  # only if you adopted the context-surface hook (step 2
                      # left a manifest); rebuilds it now that anchors exist
```

Commit each piece as you go — the foundation (steps 1–4) as one or two setup
commits, the code-level improvements (steps 5–6) folded into the feature commits
that touched those areas. You should never have a single giant "make the repo
AI-ready" PR.

## What this workflow does NOT cover

- **Fixing bugs or refactoring architecture.** Making a repo AI-ready is
  orthogonal to making it correct or well-designed. This workflow adds the
  scaffolding agents need; it does not change behavior.
- **Adding test coverage.** If the repo has thin tests, that's a separate effort
  (and a reason to be extra careful with steps 5–6).
- **Reviewing security.** Run `/security-review` when you touch sensitive paths
  — see [`security-first-feature.md`](security-first-feature.md).

## See also

- [`maintaining-as-it-grows.md`](maintaining-as-it-grows.md) — what comes after
  onboarding: how the stack keeps the repo healthy as it grows, mostly via
  passive nudges.
- [`security-first-feature.md`](security-first-feature.md) — shipping one
  PR-shaped feature safely once the repo is set up.
- [`../AGENTS.md`](../AGENTS.md) — canonical guidance, including the
  `Write less, fit in` and AIDEV-NOTE conventions referenced above.
