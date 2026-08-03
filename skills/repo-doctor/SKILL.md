---
name: repo-doctor
description: >
  USE WHEN inheriting a legacy repo, when user asks "what's missing for
  AI-first work here?", "is this repo agent-ready?", "audit my repo",
  "is anything out of sync with the code?", or when the
  bare-repo-nudge / cheatsheet hook suggests a checkup. Read-only
  AI-readiness audit — scores ~24 dimensions across Foundation
  (AGENTS.md / CLAUDE.md / per-dir AGENTS.md), Why (ADRs + session
  logs), What (GLOSSARY.md + architecture.yml), In-code (AIDEV
  anchor density + overdue), Hygiene (tests, LOC ratio, structured
  logging, .gitignore, README, manifest, CI config, .env.example,
  repro env, secret guardrails), AND Sync (code↔docs
  drift: arch-map vs disk, glossary vs code, per-dir AGENTS.md vs
  dir activity, CHANGELOG vs version, README slash-refs). Each gap
  → concrete fix action. Reports a readiness level L0-L4 (gated, ADR
  0012) + local score trend; --fix walks the top gaps; --semantic adds
  an advisory truthfulness review via the readiness-reviewer subagent.
  Differentiated from /init-repo (one-shot bootstrap, writes files)
  and /stack-check (time-based freshness) — this skill answers
  completeness, drift AND (opt-in) truthfulness in one pass. See ADR
  0006 (initial design), ADR 0007 (Sync addition), ADR 0012 (levels +
  deterministic core) for rationale.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Task
  - Bash(git rev-parse:*)
  - Bash(git ls-files:*)
  - Bash(git log:*)
  - Bash(test:*)
  - Bash(ls:*)
  - Bash(wc:*)
  - Bash(stat:*)
  - Bash(date:*)
  - Bash(find:*)
  - Bash(basename:*)
  - Bash(cksum:*)
  - Bash(cut:*)
  - Bash(tail:*)
  - Bash(pwd:*)
  - Bash(grep:*)
  - Bash(head:*)
  - Bash(cat:*)
argument-hint: "[--score] [--json] [--fail-on missing|todo|stale|semantic] [--scope foundation|why|what|incode|hygiene|sync|all] [--semantic] [--quiet] [--no-history]"
---

# /repo-doctor

## What it does

Reads the current repo and answers the question prose `AGENTS.md`
doesn't cheaply answer per session: **what's missing for AI-first
work here?** Output is a Markdown report scored across ~24 dimensions,
with a concrete fix action per gap (often "invoke `/X`").

Read-only on the repo; writes only local state (see Hard rules). The
skill is an audit, not a bootstrap.

This skill complements three existing ones with clean differentiation:

| Skill | Question it answers |
|-------|---------------------|
| `/init-repo` | "Set this fresh repo up." *(writes files)* |
| `/stack-check` | "What I have — is it stale?" *(freshness audit)* |
| `/repo-doctor` | "What I *don't* have — what's missing?" *(presence + drift + opt-in truthfulness; guided handoff via `--fix`)* |
| `/security-review` | "Is this diff safe to commit?" *(orthogonal — code-level scan)* |
| `/dynamic-check` | "Do the declared commands actually run?" *(executes code — opt-in, separate skill per ADR 0013)* |

## When to invoke

- Inheriting an existing repo (legacy or new-to-you) and wondering
  what's missing for AI-first development.
- After `/init-repo` ran, to see what *else* the bootstrap didn't
  cover.
- Periodically (every few months) to catch drift.
- When the `skill-cheatsheet` SessionStart hook suggests a checkup.
- Before pitching a "make this repo agent-ready" piece of work to a
  client — output is a ready-made list of concrete improvements.

Do NOT invoke for:

- Day-to-day "is this stale" checks — that's `/stack-check`.
- Security audit of changes — that's `/security-review`.
- One-shot setup — that's `/init-repo`.

## Output format

```markdown
# Repo Doctor — <repo-name> — <YYYY-MM-DD>

## Summary

✅ 8 pass · ⚠️ 4 attention · ❌ 3 missing · **Score: 67/100** ·
**Level: L1 Instructed (L2 blocked by Hygiene: deficit 2.5 > 2.0)**

## Foundation (loaded every session)

| Check | Status | Fix |
|---|---|---|
| AGENTS.md (root) | ✅ 4.2 KiB | — |
| CLAUDE.md (one-line `@AGENTS.md` import) | ✅ present | — |
| Per-dir AGENTS.md | ⚠️ 3 source dirs >500 LOC missing | drop `templates/AGENTS.md.example` into `src/billing/`, `src/auth/`, `src/api/` |

## Why (load-bearing decisions)

| Check | Status | Fix |
|---|---|---|
| ADRs (docs/adr/) | ❌ directory absent | next load-bearing decision → invoke `/adr-new` |
| Session logs (docs/sessions/) | ⚠️ last entry 47 days old | end of next substantial session → `/session-log` |

## What (domain + structure)

| Check | Status | Fix |
|---|---|---|
| GLOSSARY.md | ❌ missing | invoke `/glossary-init` (auto-surfaces candidates) |
| architecture.yml | ❌ missing | invoke `/arch-map` |

## In-code discoverability

| Check | Status | Fix |
|---|---|---|
| AIDEV anchors | 12 anchors / 4823 LOC = 2.5/KLOC | typical (target 1–5/KLOC) |
| Overdue anchors | ⚠️ 2 past deadline | see `/stack-check` for detail |

## Engineering hygiene

| Check | Status | Fix |
|---|---|---|
| Tests present | ✅ 28 test files | — |
| Test/source LOC ratio | ⚠️ 0.18 (target 0.5–1.0) | `src/billing` largest, fewest tests — add coverage there first |
| Structured logging | ❌ `print(` 14×, no structured logger detected | invoke `/log-structured` |
| .gitignore (claude-leverage state) | ✅ present | — |
| README quickstart | ✅ present | — |
| Language manifest | ✅ pyproject.toml | — |
| CI config | ✅ .github/workflows/ci.yml | — |
| .env.example | ⚠️ env usage in 3 files, no example | add `.env.example` with the required keys |
| Reproducible env | ✅ poetry.lock (lockfile-level) | — |
| Secret guardrails | ⚠️ only `.env` gitignored | add gitleaks to pre-commit or CI |

## Sync (code ↔ docs drift)

| Check | Status | Fix |
|---|---|---|
| `architecture.yml` ↔ disk | ⚠️ 2 drifts: `public_surface: [LegacyClient]` not in code; `src/old/` orphan (on disk, not in YAML) | invoke `/arch-map` to refresh |
| `GLOSSARY.md` ↔ code | ⚠️ term `Lead` no longer ref'd in code (last seen 4 months ago) | edit `GLOSSARY.md` or `/glossary-init --add` |
| Per-dir `AGENTS.md` staleness | ✅ all in sync | — |
| `CHANGELOG` ↔ version | ❌ `plugin.json` says 1.6.0, `CHANGELOG` top is 1.5.0 | add a `## [1.6.0]` entry to `CHANGELOG.md` |
| `README` slash-refs ↔ skills | ✅ all 13 slash commands resolve | — |

## Recommended next 3 actions

1. **`/arch-map`** — biggest unblock for refactor proposals; also fixes
   sync drift on `public_surface: [LegacyClient]`; <5 min
2. **`/glossary-init`** — `Account` appears in 12 files; agent likely
   hallucinating meaning
3. Add a `## [1.6.0]` entry to `CHANGELOG.md` to close the
   version-drift gap

_Declared-command validation (executes code, opt-in): `/dynamic-check`._
```

## Dimensions

How each dimension can be gamed — and what counters it:
[`docs/repo-doctor-gaming.md`](../../docs/repo-doctor-gaming.md). Read it
before trusting a suspiciously green report.

**Predicate P (no-code repo):** the repo has zero tracked files matching
the Dim 3 code-extension list (which includes `.sh` — shell is code).
Dimensions that reference P return N/A when it holds — a docs-only repo
gets no verdict (and no free ✅) on code-shaped checks.

Prefer the dedicated Grep/Glob tools for pattern scans; the `Bash`
allowlist covers the enumerated helpers, not arbitrary pipelines.

### Foundation (3 checks — loaded every session, agent-facing)

1. **`AGENTS.md` (root)** — `test -f AGENTS.md`. Evaluate the size bands
   largest-first (a 40 KiB file is a fail, not a warn):
   - ❌ if missing.
   - ❌ if size > 32 KiB — Codex silently drops content beyond
     `project_doc.max_bytes` (32768), so part of the file is invisible to
     Codex agents. This is data loss, not a style nit.
   - ⚠️ if size > 8 KiB — lean target exceeded; extract topic depth to
     `docs/` behind a when-to-read link. See ADR 0009.
   - ✅ otherwise. Report size in KiB.

2. **`CLAUDE.md` (root)** — `test -f CLAUDE.md`.
   - ❌ if missing.
   - ⚠️ if exists but doesn't contain `@AGENTS.md` (i.e., diverges
     from canonical guidance — split surface to maintain).
   - ✅ if exists with `@AGENTS.md` import.

3. **Per-directory `AGENTS.md`** — for each top-level source dir
   (heuristic: has files matching `*.py|*.ts|*.tsx|*.js|*.jsx|*.go|*.rs|*.java|*.rb|*.php|*.cs|*.kt|*.swift`)
   compute LOC (`wc -l` aggregated). For each with > 500 LOC and no
   `AGENTS.md` at that dir root, count it.
   - ✅ if 0 such dirs.
   - ⚠️ if 1–3.
   - ❌ if ≥4 (the per-module conventions story is broken at scale).
   - Report names of the offending dirs (top 5).

### Why (2 checks — load-bearing rationale)

4. **ADRs** — `ls docs/adr/ 2>/dev/null | grep -E '^[0-9]{4}-.*\.md$'`.
   - ❌ if `docs/adr/` absent OR 0 numbered ADR files.
   - ⚠️ if 1–2 (suspiciously few for any real project).
   - ✅ if ≥3.
   - Report count.

5. **Session logs** — `ls docs/sessions/*.md 2>/dev/null` and parse
   the date from filename (`YYYY-MM-DD-topic.md`) or `mtime` fallback.
   - ❌ if `docs/sessions/` absent OR 0 logs.
   - ⚠️ if most recent log > 60 days old.
   - ✅ if most recent ≤ 60 days.
   - Report age of newest log.

### What (2 checks — v1.5.0 additions)

6. **`GLOSSARY.md`** — `test -f GLOSSARY.md`.
   - ❌ if missing.
   - ⚠️ if exists but >30% of entries are `<TODO>` placeholders
     (parse H2 sections, count those whose body contains the literal
     `<TODO>`).
   - ✅ otherwise. Report entry count.

7. **`architecture.yml`** — `test -f architecture.yml`.
   - ❌ if missing.
   - ⚠️ if exists but >30% of modules have `<TODO>` placeholders
     for `role` or `stability`.
   - ✅ otherwise. Report module count.

### In-code discoverability (2 checks)

8. **AIDEV anchor density** — `grep -rE 'AIDEV-(NOTE|TODO|QUESTION)'`
   across tracked files (skip bench archive, vendor, node_modules,
   __pycache__, .git, dist, build; exclude matches inside test files —
   there they are overwhelmingly fixture string literals, not anchors).
   Count matches. Divide by total tracked code LOC (`git ls-files`
   filtered to code extensions incl. `.sh` → `wc -l`). Express as
   anchors-per-KLOC. Bands use half-open
   intervals (`[a, b)`) so every value falls in exactly one band:
   - ❌ if density `< 0.3/KLOC` AND total LOC `> 1000` (the repo is
     big enough that the absence is signal).
   - ⚠️ if density `[0.3, 1.0)/KLOC` (sparse for an AI-first repo).
   - ✅ if density `[1.0, 10.0]/KLOC` (typical).
   - ⚠️ if density `> 10/KLOC` (anchor noise — clutter dilutes
     load-bearing ones).

9. **Overdue / due-soon anchors** — borrowed from `/stack-check`'s
   anchor walk (intentional overlap; `/stack-check` provides the
   full actionable detail, this dimension just surfaces the count
   in the completeness report). Parse `AIDEV-(TODO|QUESTION)(by:
   YYYY-MM-DD)` and compare to today. File scope mirrors the
   `overdue-todo-nudge` hook: source code only — skip markdown/json
   and the docs/templates/tests/bench/workflows trees (that's where
   the convention's own example anchors and fixture literals live),
   and apply the first-token rule (an AIDEV-NOTE quoting a TODO
   example doesn't count).
   - ✅ if 0 overdue AND 0 due-soon.
   - ⚠️ if ≥1 due-soon (next 14 days) but 0 overdue.
   - ❌ if ≥1 overdue. Report top 3 with `file:line` and days
     overdue; remind to run `/stack-check` for the rest.

### Engineering hygiene (6 checks)

10. **Tests present** — exists `tests/` dir OR ≥1 file matching
    `**/test_*.{py}`, `**/*_test.{go,py}`, `**/*.test.{ts,tsx,js,jsx}`,
    `**/*.spec.{ts,tsx,js,jsx}`, `**/*Test.{java,kt}`, etc.
    - ❌ if 0 test files found.
    - ⚠️ if 1–4 test files for repos with > 1000 LOC.
    - ✅ otherwise. Report count.

11. **Test-to-source LOC ratio** — sum LOC of test files (above
    patterns) divided by sum LOC of source files (excluding tests,
    excluding the same noise paths as anchor walk). Bands use
    half-open intervals so every value falls in exactly one band.
    Note: the ❌ floor at `0.15` is `claude-leverage`'s own
    judgment (below that the test suite is decorative); the ✅
    band of `[0.5, 1.5]` is anchored on the
    [Count.co healthy range](https://count.co/metric/repository-health-score)
    of 0.5–1.0.
    - ❌ if `ratio < 0.15`.
    - ⚠️ if `[0.15, 0.5)` (below the healthy range).
    - ✅ if `[0.5, 1.5]` (healthy).
    - ⚠️ if `ratio > 1.5` (possible over-testing of trivial code
      — judgment call).
    - If ⚠️ or ❌, also report the largest source directory by LOC
      with no tests inside it; that's the highest-ROI place to add
      coverage.

12. **Structured logging** — grep for unstructured logging patterns
    (`print(`, `console\.(log|info|warn|error)\(`, `fmt\.Print`,
    `println!`) vs structured logger imports (`structlog`, `pino`,
    `slog`, `tracing::`, `log/slog`).
    - N/A if no programming language with an app-logging convention
      is detected, OR the `print(`-style hits are CLI stdout of
      scripts/generators rather than application logging (shell-heavy
      meta-repos, build tooling — stdout IS their interface). N/A
      shrinks the divisor; don't award a ✅ for logging that doesn't
      exist.
    - ❌ if ≥10 unstructured app-logging calls AND no
      structured-logger import detected.
    - ⚠️ if mixed (both kinds present).
    - ✅ if all app logging looks structured.

13. **`.gitignore` claude-leverage state** — `grep -E
    '\.last-stack-check|claude-leverage' .gitignore`.
    - ❌ if `.gitignore` missing entirely.
    - ⚠️ if exists but no claude-leverage state patterns AND state
      files exist in the repo (would otherwise be tracked).
    - ✅ otherwise.

14. **README quickstart** — grep README.md for one of: `## Install`,
    `## Quickstart`, `## Getting started`, `## Setup`, `## Run`,
    `## Usage` (case-insensitive, first 200 lines).
    - ❌ if no README.md.
    - ⚠️ if README.md exists but no quickstart-style section.
    - ✅ otherwise.

15. **Language manifest present** — `pyproject.toml`, `package.json`,
    `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`, `pom.xml`,
    `mix.exs` (same list as `bare-repo-nudge.sh`), plus
    `.claude-plugin/plugin.json` for plugin repos — keeping this list
    consistent with Dim 19's manifest precedence.
    - ❌ if none found.
    - ✅ if found. Report which manifest(s) found.
    - N/A under predicate P (pre-v1.14.0 this returned a free ✅ on
      code-less repos — that inflated scores and is fixed).

### Sync (5 checks — code ↔ docs drift detection)

These dimensions check that the descriptive layer (architecture.yml,
GLOSSARY.md, per-dir AGENTS.md, CHANGELOG, README) is still
**synchronized with the code**. Differentiated from earlier
dimensions (which check *presence*): a repo can have all artifacts
present and still be in deep drift if those artifacts last described
a previous version of the code.

Every Sync dimension returns **N/A (excluded from divisor)** when its
target artifact does not exist — drift is meaningless when there's
nothing to drift from. The presence gap is already reported by the
relevant earlier dimension (e.g. Dim 7 for `architecture.yml`).

16. **`architecture.yml` ↔ disk + symbol drift** — parse
    `architecture.yml`. For each `modules[].path`, `test -d` it. For
    each `modules[].public_surface` entry (a string), grep its name
    in the declared `path` subtree. Walk top-level dirs on disk (same
    noise-path filter as Dim 8) and identify any plausible source dir
    (≥100 LOC, has code files) that is NOT covered by any
    `modules[].path` — those are **orphan modules**, candidates for
    `/arch-map` to add.
    - ✅ if no path drift AND no missing-symbol drift AND no orphans.
    - ⚠️ if total drifts + orphans `≤ 2`.
    - ❌ if total drifts + orphans `≥ 3`.
    - N/A if `architecture.yml` does not exist.

17. **`GLOSSARY.md` ↔ code drift** — parse `GLOSSARY.md`. For each
    `## <Term>` heading, grep the term across tracked code files
    (skip noise paths, skip the glossary itself). For each `Code:`
    bullet path in the entry body, `test -e` it. Separately:
    identify the top-5 most-referenced PascalCase / domain-shaped
    identifiers in the repo (using the same heuristic as
    `/glossary-init` step 4) that are NOT in the glossary AND
    appear ≥10 times — those are **missing terms**.
    - ✅ if no stale terms AND no broken `Code:` paths AND no
      obvious missing terms.
    - ⚠️ if `≤ 2` total issues (stale + broken + missing combined).
    - ❌ if `≥ 3`.
    - N/A if `GLOSSARY.md` does not exist.

18. **Per-dir `AGENTS.md` staleness vs dir activity** — for each
    `<dir>/AGENTS.md` (depth `≤ 3`, skip noise paths), compute:
    - `agents_md_ts = git log -1 --format=%ct -- <dir>/AGENTS.md`
    - `dir_ts = git log -1 --format=%ct -- <dir>` (any change in
      the dir; for the comparison, ignore changes that touched
      ONLY the AGENTS.md itself — see `--invert-grep` workaround
      below).
    - `gap_days = (dir_ts - agents_md_ts) / 86400`.

    If `gap_days > N` (default 30; override via
    `CLAUDE_LEVERAGE_AGENTS_MD_DRIFT_DAYS`), the AGENTS.md is
    likely **describing a stale state** of the dir.
    - ✅ if no per-dir AGENTS.md is stale (or if no per-dir
      AGENTS.md exists — Dim 3 already flagged that).
    - ⚠️ if `1–2` stale.
    - ❌ if `≥ 3` stale.
    - Report top 3 staleness offenders with `gap_days`.

    Implementation note: filtering "changes that only touched
    AGENTS.md" requires `git log -- <dir>` plus a follow-up
    `git show --name-only` per commit, or an approximation: subtract
    1 day from `agents_md_ts` before comparing. The approximation
    is fine — we're looking for month-scale drift, not hour-scale.

19. **`CHANGELOG.md` ↔ version manifest** — read the top-of-file
    `## [X.Y.Z]` heading in `CHANGELOG.md` (first match). Compare
    to the version in the **primary manifest** for this repo, in
    order of precedence:
    - `package.json#version`
    - `pyproject.toml [project] version` or `[tool.poetry] version`
    - `Cargo.toml [package] version`
    - `.claude-plugin/plugin.json#version` (this stack)
    - `composer.json#version`

    Use the first manifest found.
    - ✅ if `CHANGELOG_top == manifest_version`.
    - ⚠️ if `manifest_version > CHANGELOG_top` by exactly one minor /
      patch level (probably an unreleased version about to ship — a
      legit transient state).
    - ❌ if they differ in any other shape (unrelated versions, or
      `CHANGELOG_top > manifest_version` which is "promised but not
      shipped").
    - N/A if neither `CHANGELOG.md` nor any recognized manifest
      exists (a docs/scratch repo).

20. **`README.md` slash-refs ↔ skill availability** — grep
    `README.md` for `/[a-z][a-z0-9-]+` tokens (slash-prefixed
    identifiers). Filter to plausible skill / command references
    (drop e.g. file paths, regex examples, dates). For each `/foo`:
    - If `skills/foo/SKILL.md` exists at repo root → resolved.
    - If `commands/foo.md` exists → resolved.
    - If text within 200 chars of the reference says "external" /
      "from `<plugin>`" / "upstream" → resolved (external skill).
    - If text within 200 chars says "removed" / "renamed" /
      "deprecated" / "historical" → resolved (historical mention,
      e.g. a CHANGELOG-style "vX removed /foo" line).
    - Otherwise → unresolved.
    - ✅ if all resolved.
    - ⚠️ if `1–2` unresolved.
    - ❌ if `≥ 3` unresolved.
    - N/A if README.md has zero `/foo` slash-refs.

    Distinct from `/stack-check`'s markdown link audit (which
    checks file paths in markdown); this one checks slash-command
    references against installed skills.

### Engineering hygiene — delivery additions (4 checks, v1.14.0)

Numbered after Sync because they shipped later (numbering is
append-only, same convention as Dims 16–20); they belong to the
**Hygiene** group and `--scope hygiene`.

21. **CI config present** — glob `.github/workflows/*.{yml,yaml}`,
    `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`,
    `Jenkinsfile`, `.drone.yml`, `.gitea/workflows/*`.
    - ✅ if ≥1 config found AND it declares a push/PR trigger
      (grep `on:`, `trigger:`, `pipelines:` per system).
    - ⚠️ if a config exists but no push/PR trigger is detectable.
    - ❌ if none found.
    - N/A under predicate P.

22. **`.env.example` present** — first detect env-config usage: grep
    `os\.environ|getenv\(|process\.env|dotenv|ENV\[` across source (same
    noise-path filter as Dim 8, **excluding test files** — tests set env
    for fixtures, they don't consume config) and count distinct files
    with hits.
    - N/A if no env usage detected.
    - N/A if there is no dotenv-style loader AND every detected read
      uses a single project-prefixed override namespace (e.g.
      `CLAUDE_LEVERAGE_*`) — those are opt-in feature flags, not
      required configuration an agent must discover.
    - ✅ if `.env.example` / `.env.sample` / `.env.template` exists with
      ≥1 `KEY=`-shaped line.
    - ⚠️ if env usage in 1–4 files and no example file.
    - ❌ if env usage in ≥5 files and no example file (config surface is
      clearly load-bearing and entirely undocumented).
    - `.env`-not-gitignored is Dim 24's job — do not double-penalize here.

23. **Reproducible dev environment** — check for
    `.devcontainer/devcontainer.json`, `flake.nix`/`shell.nix`,
    `docker-compose.y*ml` (or Dockerfile paired with compose/devcontainer),
    `.tool-versions`, `mise.toml`; else for a lockfile
    (`package-lock.json`, `poetry.lock`, `uv.lock`, `Cargo.lock`,
    `go.sum`, `Gemfile.lock`).
    - ✅ if an explicit environment definition is found.
    - ✅ (with note "lockfile-level reproducibility") if only a lockfile —
      for most single-language stacks a lockfile IS the reproducibility
      story; don't punish the common healthy case.
    - ⚠️ if neither. (A bare production Dockerfile without compose /
      devcontainer does not count as a dev-environment definition.)
    - N/A under predicate P.

24. **Secret-hygiene guardrails** — only repo-visible, machine-independent
    mechanisms count fully: `.pre-commit-config.yaml` mentioning
    `gitleaks|detect-secrets|trufflehog`, `.gitleaks.toml`, a CI config
    invoking one of those scanners, or an in-tree `.githooks/` pre-commit
    running one.
    - ✅ if ≥1 such mechanism found.
    - ⚠️ if none, but root `AGENTS.md` carries the `claude-leverage:`
      marker (stack adopted; hook enforcement is machine-local and not
      verifiable from the repo — see ADR 0012 on why this caps at ⚠️) OR
      `.gitignore` covers `.env` (minimal hygiene).
    - ❌ if none of the above AND `.env` is not gitignored.

## Levels

A communication layer on top of the score (ADR 0012). Levels gate — they
never average. Per group compute `points` (✅=1.0, ⚠️=0.5, ❌=0) and
`evaluated` (dims minus N/A). A group **passes** iff
`evaluated − points ≤ max(0.5, 0.2 × evaluated)` — the 80 % rule for
groups of ≥3 dims, with a floor so 2-dim groups tolerate one ⚠️ but no
❌. A required group with zero evaluated dims blocks its gate
(`not assessable`), never satisfies it.

| Level | Name | Requires (cumulative) |
|---|---|---|
| L0 | Ad-hoc | — |
| L1 | Instructed | Foundation passes |
| L2 | Maintained | Hygiene passes |
| L3 | Explained | Why passes AND What passes |
| L4 | Self-consistent | In-code passes AND Sync passes |

Report the achieved level plus the blocking gate for the next one, e.g.
`Level: L2 Maintained (L3 blocked by Why: deficit 1.0 > 0.5)`. With
`--scope` narrowed, skip the levels line entirely — levels are only
meaningful on a full run.

## Workflow

1. **Resolve repo root.** `git rev-parse --show-toplevel`. If not in
   a git repo, STOP and report: "repo-doctor needs a git checkout to
   walk tracked files".

2. **Optionally narrow by `--scope`.** Run only the dimensions in the
   requested scope group. Default: all 24.

3. **Run each dimension's check.** Use the `allowed-tools` listed —
   `Read` for AGENTS.md / CLAUDE.md / README / GLOSSARY.md /
   architecture.yml; `Grep` for AIDEV anchors + structured-logging
   patterns; `Bash` for `git ls-files`, `wc -l`, `find`. Cap walks
   at 5000 tracked files; skip the same noise paths everywhere
   (bench/archive-*, node_modules, __pycache__, .git, dist, build,
   vendor, target, .next, .pytest_cache).

3b. **Semantic review (only when `--semantic`).** Dispatch the
    `readiness-reviewer` subagent (read-only; see its file for the S1–S5
    dimension definitions). Render its JSON as:

    ```markdown
    ## Semantic review (advisory — not in the score, ADR 0012)

    | Dim | Verdict | Confidence | Evidence | Fix |
    |---|---|---|---|---|
    | S1 AGENTS.md actionability | ⚠️ attention | high | AGENTS.md:42 — declares `make test`; no Makefile | replace with real command |
    ```

    With `--json`, attach the subagent object unmodified under a
    top-level `"semantic"` key — never merged into `score`, `groups`,
    or `level`. If the subagent fails, returns malformed JSON, or
    subagent dispatch is unavailable in this runtime (Codex), report
    `Semantic review: unavailable (<reason>)` and continue — never fail
    the deterministic report over the advisory layer.

4. **Compute the score** as simple sum: ✅ = 1.0, ⚠️ = 0.5, ❌ = 0.
   Divide by the number of dimensions actually evaluated — that is,
   24 minus the count of N/A verdicts (some Sync and Hygiene
   dimensions return N/A when their target artifact doesn't exist
   or the language has no convention to check). The divisor is
   further narrowed by `--scope`. Multiply by 100. Round.

   Document the N/A count in the report's Summary line so the
   `Score: X/100` number is interpretable (e.g.
   `Score: 67/100 (3 N/A: arch-yml-drift, glossary-drift, structured-logging)`).

5. **Emit the report.** Markdown by default. With `--json`, emit a
   structured object:

   ```json
   {
     "repo": "name",
     "date": "2026-05-26",
     "score": 67,
     "summary": {"pass": 8, "attention": 4, "missing": 3},
     "groups": {
       "foundation": {"points": 2.5, "evaluated": 3},
       "why": {"points": 1.0, "evaluated": 2},
       "what": {"points": 2.0, "evaluated": 2},
       "incode": {"points": 2.0, "evaluated": 2},
       "hygiene": {"points": 6.5, "evaluated": 9},
       "sync": {"points": 3.5, "evaluated": 4}
     },
     "level": {"n": 1, "name": "Instructed", "blocked_by": "hygiene"},
     "dimensions": [
       {"name": "agents-md-root", "status": "pass", "value": "4.2 KiB", "fix": null},
       {"name": "glossary-md", "status": "missing", "value": null, "fix": "/glossary-init"},
       ...
     ],
     "recommended": ["/arch-map", "/glossary-init", "per-dir AGENTS.md"]
   }
   ```

5b. **History + trend (default on; skip with `--no-history`, skip when
    `--scope` is narrowed).** Resolve
    `STATE_DIR="${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}"`,
    falling back to `$HOME/.claude/claude-leverage` if that dir cannot
    be created (same chain as `scripts/hooks/stack-freshness.sh`).
    Canonicalize the repo root before hashing
    (`ROOT_CANON=$(cd "$ROOT" && pwd -P)`) so worktree/symlink spellings
    don't fork the history, then:
    `SLUG="$(basename "$ROOT_CANON")-$(printf '%s' "$ROOT_CANON" | cksum | cut -d' ' -f1)"`.
    Read the last line of `$STATE_DIR/repo-doctor/$SLUG.jsonl` (via
    `tail -n 1`, if the file exists) and emit a Trend line in the
    Summary: `Trend: 61 → 67 (+6) since 2026-07-12 · level L1 → L2`.
    If the previous record's `v` or `evaluated` differs from this run,
    annotate instead of celebrating:
    `Trend: 61 → 67 since 2026-07-12 (dimension set changed 20 → 22 — delta not comparable)`.
    Then `mkdir -p "$STATE_DIR/repo-doctor"` and append **exactly this
    shape of command — do NOT retype or rewrite existing file contents;
    append only**. The `mkdir`/`printf` writes are deliberately NOT in
    `allowed-tools` — write-capable commands with wildcard args would
    be a prose-gated write primitive, the exact failure mode ADR 0012
    (f) forbids. They go through the session's normal permission
    prompt; a user who accepts the state-dir write can allowlist the
    two commands in their own settings, and `--no-history` avoids the
    prompt entirely:

    ```bash
    printf '%s\n' '{"date":"2026-08-01","v":"1.14.0","evaluated":22,"score":67,"groups":{...},"level":1}' >> "$STATE_DIR/repo-doctor/$SLUG.jsonl"
    ```

    The record is the compact one-line JSON (`date`, `v` = plugin
    version, `evaluated` = score divisor, `score`, `groups` from step 5,
    `level`), NOT the full report. If the file exceeds ~200 lines, trim
    it to the last 100 (`tail -n 100` into a temp file in the same dir,
    then move it back) and say so. Finally refresh the freshness
    timestamp the Hard rules mention:
    `date +%s > "$STATE_DIR/.last-repo-doctor"`.

6. **`--quiet`**: suppress ✅ rows; show only ⚠️ + ❌ + the summary +
   recommendations. Default is full report.

6b. **`--fix [N]` (default 3).** After emitting the report, walk the
    recommended actions top-down. Per item: show the gap + the mapped
    skill, ask the user (one item at a time), on yes invoke that skill
    (it carries its own confirmation flow) — or, where skill invocation
    is unavailable in this runtime, print the exact slash command to
    run; on no move on. The doctor itself writes nothing in the repo.
    `--fix` implies the recommendations walk even when `--no-recommend`
    is passed (`--fix` wins, with a note). After the walk, suggest
    `/repo-doctor --quiet` to re-score. In non-interactive runs
    (`--score`, `--json`, CI), ignore `--fix` and print a one-line
    warning.

7. **Exit code.** `0` always, UNLESS `--fail-on` was passed:
   - `--fail-on missing` → exit 2 if any ❌
   - `--fail-on todo` → exit 1 if any ⚠️ (TODO/draft state)
   - `--fail-on stale` → exit 1 if any "stale" status (overdue
     anchors, old session log)
   - `--fail-on semantic` (requires `--semantic`) → exit 3 if any
     semantic `fail` verdict with confidence ≥ medium. This gate is
     non-deterministic by nature — it belongs in scheduled audits,
     not per-commit CI.

   This is what makes the skill useful in CI as a gate.

## Hard rules

- **Read-only on the repo.** Never modify, create, or delete any file
  in the repo. The only writable location is the local state dir
  (the `.last-repo-doctor` timestamp and `repo-doctor/<slug>.jsonl`
  history — both under `~/.local/state/claude-leverage/` or its
  fallback, never the repo). The report is text on stdout (or
  stdout-bound markdown).
- **Be honest about N/A.** A shell-heavy meta-repo doesn't need a
  "structured logging" verdict; mark it N/A and exclude it from
  the score divisor. Forcing every dimension on every repo
  produces scores that don't mean anything.
- **Don't hallucinate test files.** If you can't tell from the
  filename pattern whether something is a test, don't count it as
  one. False positives in the test count produce false-confident
  ratios.
- **Cap walks at 5000 files.** Large monorepos: report what the
  walk saw and the "(truncated)" footer.
- **Skip the bench archive** (`bench/archive-token-savings-thesis/`)
  and standard noise paths. Don't penalize a repo for old
  archived experiments not following current conventions.

## Tunables

- `--score` — print only the integer 0–100 score on stdout, no
  Markdown. Useful for CI scripts: `score=$(claude /skill
  repo-doctor --score)`.
- `--json` — structured output (see step 5).
- `--fail-on missing|todo|stale` — exit non-zero per step 7.
- `--scope foundation|why|what|incode|hygiene|sync|all` — narrow the
  check set. `sync` runs only Dimensions 16–20 (drift detection);
  useful for "did my last commit invalidate any docs?" runs.
  `hygiene` includes the v1.14.0 delivery additions (Dims 21–24).
- `--quiet` — suppress passing rows.
- `--no-recommend` — skip the "Recommended next 3 actions" section.
- `--no-history` — skip workflow step 5b (no state write, no Trend
  line).
- `--fix [N]` — after the report, offer the top-N recommended actions
  one at a time and invoke the mapped skill on yes (workflow step 6b).
  Interactive only.
- `--semantic` — additionally dispatch the `readiness-reviewer`
  subagent (workflow step 3b; token cost: one Sonnet subagent run;
  non-deterministic by nature). Deliberately NOT a `--scope` value:
  `--scope all` stays "all deterministic dimensions" (ADR 0012).

## What this skill does NOT do

- **Bootstrap missing artifacts.** That's `/init-repo` (for AGENTS.md
  + .gitignore + logging template) and the per-skill bootstraps
  (`/glossary-init`, `/arch-map`, `/adr-new`, `/session-log`).
  (`--fix` only *invokes* those skills interactively; it never writes
  files itself.)
- **Check version freshness.** That's `/stack-check`.
- **Audit code for security issues.** That's `/security-review`.
- **Run tests / linters.** Out of scope — those are project-local
  commands the language ecosystem already provides
  (`pytest`, `eslint`, `cargo clippy`, …). The skill checks that
  tests *exist*, not that they pass.
- **Auto-fire on a SessionStart hook.** Per ADR 0004 / ADR 0006:
  user/agent-invoked. The `skill-cheatsheet` SessionStart hook can
  suggest `/repo-doctor`, but doesn't run it.
- **Per-file or per-function audit.** Scope is repo-level
  discoverability artifacts, not the code itself.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. All
deterministic checks use plain Bash + Read + Grep — no
Claude-Code-specific tools. History (step 5b) uses plain shell
redirection and works identically in both tools. **Exception:**
`--semantic` requires Claude Code subagent dispatch; in Codex it
degrades to `Semantic review: unavailable (no subagent dispatch)` and
the deterministic scopes are unaffected.

## Future / not in scope here

- **`--diff-base <ref>`** to score a PR's incremental contribution
  to AI-readiness (e.g., "did this PR add the AGENTS.md it should
  have?"). Future enhancement.
- **Multi-repo dashboard** — run /repo-doctor across N repos and
  emit a comparative table. Out of scope; a wrapper script can
  iterate `--json` outputs.
- **Per-language quality gates** (lint config presence, type-check
  presence). Tempting but veers into language-coupling — out of
  scope for v1. (CI *presence* is Dim 21 since v1.14.0;
  lint/type-check configs remain out of scope.)
