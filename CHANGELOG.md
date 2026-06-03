# Changelog

All notable changes to `claude-leverage` are recorded here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[SemVer](https://semver.org/spec/v2.0.0.html).

## [1.11.0] — 2026-06-03

### Added

- **Conventions steering** — a repo's `conventions.yml` (per-kind casing, a
  vague-name denylist, directory roles, and divergent house rules the model
  cannot infer) is surfaced to agents **before they edit a source file**, via the
  `context-surface` hook. New **`/conventions-init`** skill (15th) drafts it;
  `ai-first-nudge` warns on casing/vague drift an edit introduces. Design in
  [the spec](docs/specs/2026-06-03-conventions-steering-phase2-design.md).
- **Adherence scorer** — `scripts/score_adherence.py`, a deterministic
  naming/casing/structure scorer (`--repo` / `--diff`), usable as a hygiene
  signal. `bench/conventions-eval/` documents the full-repo A/B quality protocol.
- Behavioral tests for `block-secrets-precommit`; a **`windows-latest` CI job** so
  the bash hook tests run on Windows instead of silently skipping.

### Changed

- Pruned the archived token-savings benchmark (raw transcripts + regenerable git
  fixtures; 16 → 4.3 MB), keeping the documentary evidence.

## [1.10.0] — 2026-06-01

### Added

- **`Name to fit in` naming convention** in both `templates/AGENTS.md.example`
  (the artifact installed into client repos) and the root `AGENTS.md`, with the
  mechanics in [`docs/conventions.md`](docs/conventions.md) ("Naming") and the
  rationale in [ADR 0010](docs/adr/0010-naming-detect-and-conform-over-house-style.md).
  Closes two recurring AI naming failure modes: casing
  drift (the model imposing its language default `snake_case`/`camelCase` instead
  of detecting and conforming to the repo's actual style, per kind and per local
  module) and wrong granularity (names that are too vague — `get()` — or too
  verbose/leaking — `getting_data_from_mobile()`). Deliberately
  detect-and-conform, **not** a prescribed house style — a house style would
  contradict the stack's "fit in" north star and be wrong in most client repos.

### Changed

- **Slimmed the root `AGENTS.md` from ~19 KiB to ~7.7 KiB** — the focused
  follow-up the 1.9.0 lean-budget ADR
  ([0009](docs/adr/0009-agents-md-lean-budget-and-size-tiers.md)) deadlined as an
  `AIDEV-TODO`.
  Always-on load-bearing rules stay inline (mission, reading order, `Write
  less, fit in`, AIDEV anchors, security guardrails, build/test, keep-lean
  rule); topic depth moved behind *when-to-read* links to two new docs:
  [`docs/conventions.md`](docs/conventions.md) (repo layout, structured-logging
  spec, per-dir AGENTS.md, `/adr-new` & `/session-log` timing, module org) and
  [`docs/maintaining.md`](docs/maintaining.md) (README/per-dir sync, plugin
  marketplace, Codex subagent parity, design specs). The `#write-less-fit-in`
  anchor (linked from `workflows/onboarding-a-legacy-repo.md`) is preserved.
  No change to `templates/AGENTS.md.example` or any shipped plugin behavior.

## [1.9.0] — 2026-05-31

### Added

- **`Write less, fit in` code-convention section** in both
  `templates/AGENTS.md.example` (the artifact installed into client repos) and
  the root `AGENTS.md`. Until now every convention the stack documented was
  additive (add anchors, add logs, add per-dir docs) with no counterweight
  against AI slop. The new section codifies three subtractive principles —
  match the surrounding code, comments explain WHY not WHAT, no speculative
  abstraction — framed under the same north star ("make the next agent's job
  easier"). The AIDEV-anchor sections now also call out that an anchor (or a
  structured log) on every line is the same noise as a comment on every line.
- **`workflows/onboarding-a-legacy-repo.md`** — end-to-end guide for the
  canonical scenario: an agent inherits a repo with none of the stack's
  conventions and makes it AI-ready **incrementally** (audit → foundation →
  vocabulary + module map → opportunistic logging + anchor-as-you-touch),
  explicitly avoiding the heroic big-bang PR. Linked from `README.md` and
  `workflows/README.md`.

- **`Keeping this file lean` convention** in `templates/AGENTS.md.example` and
  root `AGENTS.md`: AGENTS.md loads every session and Codex silently truncates
  the assembled project doc past ~32 KiB (`project_doc.max_bytes`), so topic
  depth belongs in `docs/` behind *when-to-read* links, not always-on. Working
  target ~8 KiB. Rationale in [ADR 0009](docs/adr/0009-agents-md-lean-budget-and-size-tiers.md).

### Changed

- **`/refresh-context-map` skill** gained a `Hard rules` section (never
  hand-edit the manifest; the manifest is committed, not gitignored; read-only
  on source) and an `If the rebuild fails` note (a failed rebuild degrades
  gracefully — the hook no-ops on a stale/absent manifest, never blocks).
- **`/stack-check` AGENTS.md sanity** now reports two size tiers — **warn over
  8 KiB** (lean target) and **flag over 32 KiB** (Codex hard cap) — instead of
  only the 32 KiB warning. Per-dir AGENTS.md inherit the two-tier check and the
  note that they share the same Codex budget.
- **`/repo-doctor` Dimension 1 (root AGENTS.md)** severity remap: **> 32 KiB is
  now a hard ❌** (silent Codex data loss, not a style nit) and **> 8 KiB is a
  ⚠️** (lean target). Bands evaluated largest-first. The stack-check/repo-doctor
  severity asymmetry is deliberate — see ADR 0009.

- **`/session-log` confidentiality guardrail.** Session logs are committed and
  pushed (sometimes to public repos), but neither the skill nor
  `docs/sessions/README.md` warned against logging secrets / client names /
  internal reasoning. Added a Hard rule + a `Confidentiality pass` workflow step
  + a README note. Notes that `block-secrets-precommit` catches key-shaped
  secrets but not confidential prose — that judgment is the author's.

### Known follow-up

- This repo's own root `AGENTS.md` is 18.7 KiB, over the new 8 KiB target.
  Tracked as a deadlined `AIDEV-TODO` for a focused slimming PR rather than
  bundled here (ADR 0009 records why).

### Fixed

- **`/codex-sandbox` `argument-hint`** advertised a `--profile staging` option
  that does not exist (the body's profile table, picker, and tunables only offer
  `dev|prod|custom`). Corrected the hint and reworded the "no staging profile"
  note from changelog-style archaeology to a forward statement that keeps the
  *why* (Codex config has no audit-log field).

## [1.8.3] — 2026-05-26

### Added (diagnostic — still tracking the silent-no-emit bug)

- **`context-surface.sh`: capture Python heredoc output when debug log
  is active.** v1.8.2 confirmed the hook IS being invoked end-to-end by
  Claude Code (debug log shows tool=Read, file_rel computed correctly,
  manifest found, "script end reached"), but no `[claude-leverage:context-surface]`
  entry appears in transcripts. Manual repro with the same env vars
  produces JSON correctly. Hypotheses left: Python's stdout written but
  swallowed somewhere, OR a silent `sys.exit(0)` branch that doesn't
  reproduce in isolation. To distinguish: this release captures the
  Python output into a bash variable WHEN
  `CLAUDE_LEVERAGE_CTX_DEBUG_LOG` is set, logs its length + preview,
  and then prints it to stdout. Each `sys.exit(0)` branch in the Python
  heredoc also writes a diagnostic line to stderr now (which Claude Code
  shows in the transcript for non-zero exits, but at exit 0 the stderr
  may or may not be captured — worth checking).
- Production path (debug not set) is unchanged: streams Python stdout
  directly to script stdout with no variable roundtrip and zero new
  overhead.

## [1.8.2] — 2026-05-26

### Added

- **Optional debug logging in `context-surface.sh`.** A real-world Opus
  endpoint-task run produced zero `hookSpecificOutput.PreToolUse` emissions
  despite the manifest being present and the agent demonstrably calling
  `Read` on anchor-bearing files (`classes/db/clickhouse_reader.py`). The
  hook works correctly in isolated smoke tests on the same machine, so
  there's a runtime mismatch we can't observe with the current
  always-silent error paths. To unblock diagnosis without permanently
  noising the hook, this release adds an opt-in trace log: set
  `CLAUDE_LEVERAGE_CTX_DEBUG_LOG=/path/to/log` and the hook will append a
  timestamped line at every invocation and at each early-exit branch
  (opt-out / no-parser / wrong-tool / no-cwd / no-repo / no-manifest /
  no-file-path / no-python / script-end). Off by default — zero overhead
  when the env var isn't set.

## [1.8.1] — 2026-05-26

### Fixed

- **`context-surface.sh` path normalization on Linux.** The bundled
  `canon_path` helper applied `replace("\\", "/")` *after* `os.path.abspath`,
  which on Linux treated a Windows-style input like `\tmp\foo` as relative
  (since `\` isn't a path separator on POSIX), prepended cwd, and produced a
  path that no longer matched `repo_root` — the manifest lookup silently
  missed. The regression test
  `test_hook_normalizes_windows_backslash_path` correctly caught this on
  the GitHub Actions Linux runner; it had passed locally on Windows because
  `cygpath` runs first there and short-circuits the buggy branch. Fix:
  convert backslashes *before* `abspath` so absolute Windows paths are
  recognized as absolute on any platform. AIDEV-NOTE added at the fix site.

## [1.8.0] — 2026-05-26

### Added

- **Smart context surfacing (PreToolUse hook + manifest).** New opt-in
  mechanism that cuts per-session token tax from the leverage stack's
  docs by surfacing only the AIDEV anchors relevant to the file the
  agent is about to read or edit, instead of forcing the agent to
  pre-load every `AGENTS.md` upfront. Motivated by an internal A/B
  benchmark: on a small helper-add task with Sonnet 4.6, the stack
  added +116% to baseline cost when no specific gotcha was present —
  pure overhead worth measuring before designing the fix.
  - `scripts/build-context-map.py` walks `git ls-files`, extracts
    `AIDEV-NOTE`/`TODO`/`QUESTION` anchors (with optional
    `(by: YYYY-MM-DD)` deadlines), and writes
    `.claude-leverage-context-map.json` at the repo root, atomically.
    NUL-byte sniff skips binaries; word-boundary ADR cross-ref avoids
    false matches like `src/api.pyc` matching `src/api.py`.
  - `scripts/hooks/context-surface.sh` (`PreToolUse` on
    `Read|Edit|Write|MultiEdit`) does an O(1) manifest lookup and emits
    `hookSpecificOutput.additionalContext`. Single Python heredoc keeps
    cold-start cost down. Graceful no-op when manifest missing, file
    unknown, entry empty, JSON corrupt, or schema version mismatches —
    **repos that don't adopt pay zero cost**.
  - `/refresh-context-map` skill for rebuilding the manifest after
    anchor/per-dir AGENTS.md/ADR changes or post-merge.
  - `.gitattributes` `merge=ours` for the manifest — a 234-entry sorted
    JSON should never be a hand-merge chore.
  - Cross-tool by design: identical `hookSpecificOutput.additionalContext`
    schema works on Claude Code and Codex per both runtimes' PreToolUse
    specs (researched 2026-05-26).
  - Opt-out per session: `CLAUDE_LEVERAGE_CTX_DISABLE=1`. Verbose mode
    (`CLAUDE_LEVERAGE_CTX_VERBOSE=1`) also surfaces per-dir AGENTS.md
    chain + related ADR refs; off by default per Run-3 finding that
    refs are taxed-without-catch in the common case.
  - 30 regression tests in `tests/test_context_surfacing.py` cover
    binary-file gate, ADR word-boundary, atomic write, partial-flush
    manifest, all-empty entry, Windows backslash path, schema-version
    mismatch, opt-out, truncation cap, verbose mode toggle, etc.
- See [ADR 0008](docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md)
  for the design rationale and the consequence ledger.

### Changed

- `scripts/smoke-plugin.sh` adds a new gate: `python scripts/build-context-map.py --check`
  flags drift between the committed manifest and what regen would produce,
  so a forgotten rebuild surfaces in CI exactly the way version-sync drift does.

## [1.7.0] — 2026-05-26

### Added

- **`/repo-doctor` Sync section (Dimensions 16–20).** Five new
  read-only checks for **code ↔ docs drift** — the failure mode
  where descriptive artifacts (architecture.yml, GLOSSARY.md,
  per-dir AGENTS.md, CHANGELOG, README) are *present* but
  *actively misleading* because they describe a previous version
  of the code. Concretely:
  - **16. `architecture.yml` ↔ disk + symbol drift** —
    declared `modules[].path` exists; each `public_surface`
    symbol still grep-able; orphan dirs flagged.
  - **17. `GLOSSARY.md` ↔ code drift** — each term still
    referenced in code; each `Code:` path exists; top-K
    high-frequency identifiers not in glossary surfaced as
    missing.
  - **18. Per-dir `AGENTS.md` staleness vs dir activity** — for
    each `<dir>/AGENTS.md`, compute `gap_days = (dir_last_change
    - agents_md_last_change)`; flag if `> 30` (override via
    `CLAUDE_LEVERAGE_AGENTS_MD_DRIFT_DAYS`).
  - **19. `CHANGELOG.md` ↔ version manifest** — top
    `## [X.Y.Z]` heading matches primary manifest version
    (`package.json` / `pyproject.toml` / `Cargo.toml` /
    `.claude-plugin/plugin.json` / `composer.json`).
  - **20. `README.md` slash-refs ↔ skill availability** — every
    `/<name>` in README resolves to an installed
    `skills/<name>/SKILL.md` or `commands/<name>.md`, or is
    annotated as external.
- **`--scope sync`** tunable — run only Dimensions 16–20 for a
  fast "did my last commit invalidate any docs?" check.
- **ADR 0007** — Sync drift detection in `/repo-doctor`.
  Documents why drift detection belongs inside `/repo-doctor`
  rather than a separate `/sync-check` skill (one mental model
  for the user), why audit-first vs hook-first (audit catches
  what already drifted; hook for v1.8+ if drift dimensions fire
  often enough in field use), and why we don't auto-fix.

### Changed

- **Score divisor is now variable.** Pre-v1.7 always divided by
  15. Post-v1.7 divides by `(20 − N/A count)` because Sync
  dimensions correctly return N/A when their target artifact
  doesn't exist (drift is meaningless when there's nothing to
  drift from). The Summary line in the report now spells out
  the N/A count so the `Score: X/100` number is interpretable.
- `/repo-doctor` frontmatter description bumped 15 → 20
  dimensions; explicitly names the Sync group; references both
  ADR 0006 and ADR 0007.
- README, AGENTS.md, marketplace.json, and `skills/README.md`
  `/repo-doctor` descriptions refreshed to mention the Sync
  dimension group.

## [1.6.0] — 2026-05-26

### Added

- **`/repo-doctor` skill — read-only AI-readiness audit.** Scores ~15
  dimensions across Foundation (AGENTS.md root + CLAUDE.md +
  per-dir AGENTS.md), Why (ADRs + session logs), What (GLOSSARY.md +
  architecture.yml), In-code (AIDEV anchor density + overdue
  deadlines), and Hygiene (tests + test/source LOC ratio +
  structured logging + .gitignore + README quickstart + language
  manifest). Each gap → concrete fix action (often `/X`). Flags:
  `--score` (0–100 integer for CI), `--json` (machine-readable),
  `--fail-on missing|todo|stale` (CI gate, non-zero exit), `--scope`
  (narrow check group), `--quiet` (suppress passes). Test/source
  LOC ratio target 0.5–1.0 per the [Count.co healthy benchmark](https://count.co/metric/repository-health-score).

- **`skill-cheatsheet.sh` SessionStart hook.** Compact (~3-line)
  nudge listing high-value skills + triggers, fires once per 14
  days per repo via `additionalContext`. Gated tight: cwd must be
  interesting (not `$HOME` / `/tmp` / system roots), must be inside
  a git repo whose `AGENTS.md` contains a `claude-leverage:` marker
  (i.e., user actively adopted the stack), and the per-repo state
  file must be ≥ `CLAUDE_LEVERAGE_SKILL_HINT_DAYS` (default 14)
  days old. Set the env var to 0 to disable entirely. Mitigates the
  documented skill-auto-activation gap (see "Changed" below).

- **ADR 0006** — `/repo-doctor`, folded-scalar SKILL descriptions,
  and gated skill-cheatsheet hook. Documents *why* the three
  changes belong together as one coherent discoverability layer,
  why folded scalar over single-line, why the cheatsheet is gated
  on adoption marker, and why `/repo-doctor` is separate from
  `/init-repo` (one-shot bootstrap) and `/stack-check` (freshness
  of existing).

### Changed

- **All 13 SKILL.md descriptions converted from `|` (literal block
  scalar) to `>` (folded block scalar).** Reason: field reports
  (agentengineermaster.com, scottspence.com, dev.to) document that
  the 2026 Claude Code runtime sometimes parses only the first line
  of a multi-line description when matching skills for
  auto-activation — responsible for ~40% of "slash works, auto-fire
  doesn't" cases. Folded scalar joins wrapped source lines with
  spaces, yielding a single-string runtime value with no internal
  `\n`. No semantic change to description content; YAML
  representation only. Source remains as readable as before.
- Skill count: 12 → 13. Hook count: 6 → 7. README, AGENTS.md,
  CLAUDE.md, marketplace description, `scripts/smoke-plugin.sh`
  lower bound (`>=13` now), `skills/README.md`, `docs/adr/README.md`
  all updated.
- README Version badge bumped to 1.6.0.

### Fixed

- Typo `halucinates` → `hallucinates` in `glossary-init` SKILL
  description (introduced in v1.5.0).

## [1.5.0] — 2026-05-26

### Added

- **`/glossary-init` skill + `GLOSSARY.md` convention.** Hand-curated
  domain glossary at repo root. The skill surfaces candidate terms by
  frequency analysis of identifiers (classes, type aliases, dataclasses
  per language) and asks the user for 1-sentence definitions —
  **never invents domain meaning**. Idempotent (re-running adds new
  terms without overwriting existing). Closes the "what does `Lead`
  mean in *this* repo?" hallucination class that AGENTS.md prose
  doesn't address cheaply per session.

- **`/arch-map` skill + `architecture.yml` convention.** Hand-curated,
  machine-readable module metadata at repo root: `path` + `role` +
  `stability` + optional `public_surface` / `depends_on` /
  `paired_with` / `owners`. Schema version `v1`. Complements
  `/repo-map`'s human-readable mermaid block — agents can load this
  YAML once and answer structured queries (which modules are
  `stable`? what's the public surface of `agents/`?) without
  re-walking the tree. `--validate` mode for CI.

- **`templates/GLOSSARY.md.example`** + **`templates/architecture.yml.example`**
  — drop-in templates for other repos adopting the convention.

- **ADR 0005** — Structured discoverability layer: GLOSSARY.md +
  architecture.yml. Documents *why* both files live at root (parallel
  with AGENTS.md, not under `docs/`), why YAML over JSON for arch-map,
  why we don't go to per-folder YAML (against the 2026 AGENTS.md-
  per-folder convergent standard), and why neither auto-fires on a
  hook (follows ADR 0004's user-invoked philosophy).

### Changed

- Skill count: 10 → 12. README, AGENTS.md, CLAUDE.md, marketplace
  description, and `scripts/smoke-plugin.sh` lower bound updated.
- README Version badge bumped to 1.5.0 (was stale at 1.3.3 from prior
  release).
- `CLAUDE.md` skills list refreshed: dropped stale `/commit-smart`
  reference (removed in v1.4.4) while adding the two new skills.

## [1.4.5] — 2026-05-25

### Fixed

- **`block-dangerous-git.sh` false positives on prose in commit message
  bodies.** Surfaced during v1.4.4's own commit: the message body
  explained why the hook refuses force-push / `--no-verify` / hard
  reset, but the hook's pre-v1.4.5 `tr -d '"'\\` strip flattened the
  entire bash command into one string before keyword scanning, so the
  literal `--force` substring in the commit message body — combined
  with a chained `git push` later in the same compound command —
  matched the force-push detector and blocked the commit.

  Fixed by moving to quote-aware stripping: contents of `'...'` and
  `"..."` (with `\"` escape) are stripped entirely before keyword
  matching, via Python regex with `re.DOTALL` so multi-line bodies
  (heredoc-inside-`$()`-inside-`"..."`) are caught. Remaining
  backslashes are stripped after that pass to preserve the
  `git\ push\ --force` evasion catch.

  Deliberate trade-off: someone who quotes a flag (e.g.
  `git push '--force'`) now slips past detection. The hook is a
  safety net for accidents — adversarial evasion was always out of
  scope (documented in `hooks/README.md`), and the daily false-
  positive rate on common prose was breaking legitimate commits.

- 9 new tests in `tests/test_hook_behavior.py` covering both directions
  (5 ALLOW cases for quoted flag-mentions, 4 BLOCK cases for real
  attacks including backslash-escape evasion regression guard).

## [1.4.4] — 2026-05-25

### Removed

- **`/commit-smart` slash command** (`commands/commit-smart.md`) —
  removed entirely. The command auto-pushed by default
  (`git push --set-upstream` on first push of a new branch), which
  violates the Claude Code principle that visible / shared-state
  actions should require explicit confirmation. The auto-push was
  treacherous: users who invoked `/commit-smart` for the commit part
  got a public remote ref as a side effect.

  Vanilla Claude Code commit workflow + the existing
  `block-secrets-precommit` and `block-dangerous-git` hooks already
  enforce every safety invariant `/commit-smart` had (refuse `.env`,
  refuse `--no-verify`, refuse `--force`, refuse `--amend`, match
  Conventional Commits style). The slash command added a treacherous
  auto-push for no net benefit.

  v0.12.0 already dropped the *delegation* layer of `/commit-smart`
  after benchmarks disproved the token-savings thesis; v1.4.4 closes
  the loop by dropping the *command* itself. The bench evidence stays
  in `bench/archive-token-savings-thesis/` as before.

### Changed (docs)

- `README.md`, `AGENTS.md`, `workflows/security-first-feature.md`,
  `workflows/maintaining-as-it-grows.md`, `workflows/README.md`,
  `commands-docs/README.md`, `skills/process-diagram/SKILL.md`,
  `skills/explain-diff/SKILL.md` — every live-doc reference to
  `/commit-smart` replaced with vanilla-commit guidance. The historical
  pivot specs under `docs/specs/` and the bench archive are left as
  frozen reference (per AGENTS.md repo conventions).

## [1.4.3] — 2026-05-25

### Added

- **`bare-repo-nudge.sh` branch B** — SessionStart inside a git repo
  whose root has neither `AGENTS.md` nor `CLAUDE.md` AND that looks
  like a real project (recognizable marker file like `package.json`,
  `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`,
  `build.gradle[.kts]`, `Gemfile`, `composer.json`, `mix.exs`,
  `*.csproj`, `Package.swift`, `CMakeLists.txt`, `requirements.txt`,
  `setup.py` / `setup.cfg`) now emits an `additionalContext` nudge
  toward `/init-repo`. Closes the gap where the plugin's hooks fire
  but the convention layer (AIDEV anchors, structured logging,
  per-dir AGENTS.md, module org) stays invisible to the model.
  v1.4.1's branch A still covers the non-git case.
- 4 new tests in `tests/test_hook_behavior.py` covering the branch-B
  decision tree (fires for git + project marker + no AGENTS.md;
  silent for AGENTS.md present, CLAUDE.md present, or no project
  marker).

## [1.4.2] — 2026-05-25

### Fixed

- **All 10 shell scripts** (`scripts/hooks/*.sh`,
  `scripts/install-codex.sh`, `scripts/smoke-plugin.sh`,
  `statusline/statusline-command.sh`) were committed to the git
  index with mode `100644` instead of `100755`. On Linux installs
  via `/plugin install`, every Bash call emitted
  `Permission denied` from the hook scripts, silently disabling the
  security guardrails the plugin exists to provide. Flipped via
  `git update-index --chmod=+x`.

### Added

- New parametrized pytest in `tests/test_plugin_integrity.py`
  (`test_shell_script_is_executable_in_git_index`) calls
  `git ls-files -s` for every tracked shell script and asserts
  mode `100755`. Prevents the regression from recurring silently.

## [1.4.1] — 2026-05-25

### Fixed (field-feedback bundle)

- **`ai-first-nudge.sh`** split basename-only vs path ignore patterns
  so directories named e.g. `slevomat_test_api/` no longer silently
  swallow nudges for production files inside them. Added Windows
  backslash → forward slash normalization before pattern matching so
  `node_modules` and friends still match on Git Bash.
- **`stack-freshness.sh`** migrated from `printf >&2` to stdout JSON
  `hookSpecificOutput.additionalContext` per the Claude Code
  SessionStart hook spec, so the model actually sees the nudge in
  its context window (stderr from SessionStart is invisible to the
  model).
- **`skills/stack-check/SKILL.md` step 9** now mandates exactly
  `date +%s > "$STATE_DIR/.last-stack-check"`; prevents the
  hallucinated-epoch bug where the body and mtime disagreed by
  ~2 months and suppressed nudges for weeks.

### Added

- **`bare-repo-nudge.sh`** — new SessionStart hook (branch A only at
  this stage). When cwd is not inside a git repo and is not a
  just-opened-terminal location (`$HOME` / `/tmp` / `/etc` / …),
  emits a one-per-day `additionalContext` nudge toward `git init` +
  `/init-repo`. Fills the gap left by `security-nudge.sh` (git-only
  by design) so that fresh non-git projects — the exact place where
  guardrails are most valuable — get proactive signal at session
  start.
- 13 new tests in `tests/test_hook_behavior.py` driving each hook
  with crafted stdin JSON in an isolated state dir, asserting on
  the externally observable contract.

## [1.4.0] — 2026-05-25

The "self-audit caught self-maintenance gaps" release. A pre-push
human-led audit of the v1.0.0 → v1.3.3 commit batch surfaced three
stale-reference issues that had survived 4–7 version-bumps each —
exactly the failure mode the stack's "self-maintaining as the repo
grows" mission is supposed to prevent. v1.4.0 closes the loop on both
fronts: fixes the stale references found, AND adds the deterministic
checks that would have caught them automatically.

### Fixed (stale references)

- **`.github/workflows/ci.yml`**: pytest job name no longer references
  `leverage_stats_agg.py` (deleted in v1.1.0); renamed to "Pytest
  (plugin integrity + frontmatter)".
- **`AGENTS.md`** "Design specs" section: removed broken pointer to
  `docs/specs/2026-05-21-synthetic-benchmark-design.md`; the file
  lives at `bench/archive-token-savings-thesis/...` since v1.2.1.
  Added an inline pointer there.
- **`tests/README.md`**: Coverage section fully rewritten to describe
  the actually-shipped `test_plugin_integrity.py` (added v1.2.0) and
  `test_agent_command_frontmatter.py`. Dropped the deleted
  `test_leverage_stats_agg.py` entry. Added `bash scripts/smoke-plugin.sh`
  as the one-shot pre-push entrypoint.
- **`scripts/hooks/block-secrets-precommit.sh`**: false-positive hint
  text no longer points users to `~/.claude/hooks/block-secrets-precommit.sh`
  (a path that does not exist in plugin-install mode). New hint
  describes the fork-from-plugin-source pattern.

### Added (self-maintenance hardening)

- **Repo-wide markdown link audit in `/stack-check`** (new step 7):
  walks every tracked `*.md` (capped at 200), extracts path-like
  tokens (`scripts/...`, `docs/...`, `tests/...`) outside fenced code
  blocks, reports broken refs as `<md-file>:<line> → <token>`. Cap of
  20 in the report so the section never dominates. New env var
  `CLAUDE_LEVERAGE_SKIP_MD_LINK_AUDIT=1` to disable on doc-heavy
  repos. This is the deterministic version of what humans would have
  needed to do by hand to catch the three issues above.
- **CI workflow floating-ref scan in `security-reviewer` subagent**
  (new step 1c): on diffs touching `.github/workflows/*.yml` (and
  CircleCI / GitLab / Azure / Drone equivalents), parses each
  `uses: <owner>/<repo>@<ref>`; classifies as SHA (ok), semver tag
  (Nice tier comment), or branch ref / `master` / `main` / `latest`
  (Important tier finding). Triggered automatically by `/security-review`
  whenever a workflow file is in the diff. Catches the irony of a
  "security by default" repo with floating action refs in its own CI.
- **`.githooks/pre-push` (opt-in)** + `.githooks/README.md`: in-tree
  pre-push hook that runs `scripts/smoke-plugin.sh --quiet` and
  blocks the push on failure. Enable per-clone with
  `git config core.hooksPath .githooks`. Disable with
  `git config --unset core.hooksPath`. Bypass once with
  `git push --no-verify`. In-tree (vs `.git/hooks/`) so the hook is
  visible to review, evolves with the repo, and doesn't diverge
  per-clone.

### Maintenance

- **`.gitattributes`** added: forces LF line endings for `*.sh`,
  `.githooks/*`, `*.py`, `*.json`, `*.toml`, `*.yml`, `*.yaml`. Without
  this, Windows clones with `autocrlf=true` ship CRLF inside shell
  scripts, and `bash` on Linux / macOS / Git Bash refuses to execute
  them (`/usr/bin/env bash^M: bad interpreter`). Markdown stays
  platform-native; binary assets explicitly marked.
- **`.github/workflows/ci.yml`** shellcheck step pinned to
  `ludeeus/action-shellcheck@00cae500b08a931fb5698e11e79bfbd38e612a38`
  (v2.0.0 SHA) instead of `@master`. Comment block documents the bump
  procedure (replace SHA + comment together).
- **`AGENTS.md` Build / test section** documents
  `bash scripts/smoke-plugin.sh` as the canonical one-shot, and points
  at the opt-in pre-push hook setup.

### Why the version is 1.4.0 and not 1.3.4

Three real new features (markdown link audit in `/stack-check`, CI
floating-ref scan in `security-reviewer`, in-tree opt-in pre-push
hook). Stale-reference fixes alone would be 1.3.4; the additive
self-maintenance hardening earns the minor bump.

## [1.3.3] — 2026-05-24

Dogfooding pass. We ship `/process-diagram` skill but weren't using it
in our own docs — classic "the cobbler's children have no shoes" gap.
This release fixes that.

### Added

- **Mermaid sequenceDiagram in README's `## Workflow example`** —
  shows the end-to-end security-first feature flow as a real sequence
  (User → Claude Code → hooks → security-reviewer subagent → Git),
  with auto-fired hook events as dashed return arrows, explicit
  invocations as solid arrows, and `Note over` boxes for asynchronous
  Stop-hook firings. Wrapped in `<!-- process-diagram:security-first-flow:start -->`
  markers so future `/process-diagram` re-runs regenerate it
  idempotently.
- **Mermaid flowchart for the maintenance-debt cycle in
  `workflows/maintaining-as-it-grows.md`** — replaces the prior
  ASCII-art cycle with a color-coded flowchart (green = passive
  nudges, blue = active skills, orange = durable artifacts). Same
  marker pattern for regeneration.

### Rationale

The README already had ONE mermaid block (architecture diagram from
`/repo-map`). Adding `/process-diagram` outputs for workflows means
we're dogfooding both diagram skills, AND the diagrams stay
maintainable via skill re-run rather than hand-editing. GitHub
renders mermaid natively — no asset toolchain, no PNG drift,
copy-paste-able into PR descriptions.

### Changed

- Plugin version bumped to **1.3.3** (patch: documentation visuals
  via dogfooding; no functional changes, no new skills).

## [1.3.2] — 2026-05-24

Token-efficiency + README polish pass. Skill / agent / command
descriptions are loaded into the system prompt on every cold session, so
verbose descriptions tax `cache_creation_input_tokens` on every fresh
start. v1.3.1's `USE WHEN ...` expansions were over-long.

### Changed

- **All 10 skill descriptions, 2 subagent descriptions, and 2 command
  descriptions tightened to 3–7 lines each.** Pattern: 1–2 sentences of
  `USE WHEN ... triggers`, 1–2 sentences of `what it does`, optional
  one-liner about scope (read-only, cross-tool, etc.). Detailed
  `Do NOT use for` examples + hard rules + workflow stayed in the
  SKILL.md / agent body where they're loaded only on actual invocation,
  not on every session start.
- **README rewritten for first-impression polish.** Banner moved below
  badges (badges first = more visual). "What you get" reorganized by
  category (always-on safety / security review / repo maintenance /
  setup + handoff / workflow commands / conventions / cross-tool
  plumbing) instead of a flat alphabetical list. Workflow example now
  shows nudges firing inline (`↳` annotations) so the agent's
  behaviour is visible per step. Honest history compressed.
- **Statusline screenshot** ([`statusline/screenshot.png`](statusline/screenshot.png))
  embedded in the README's "Optional: portable statusline" subsection
  alongside install instructions, so the visual value is discoverable
  at install time.
- **README "What's inside" table** fixed stale references:
  `claude-md-snippets/` was "(none in default install)" but now lists
  the 2 shipped snippets (`security-review-routing`,
  `adr-session-log-discipline`); `docs/adr/` and `docs/sessions/` row
  counts updated.
- **Workflow example** in README extended with `/adr-new` and
  `/session-log` steps so the durable-memory layer is visible in the
  "what does this look like in practice" tour.
- **Codex install step 4** now says "Copies all 10 skills" instead of
  enumerating 8 by name (less likely to bit-rot on next skill add).

### Estimated token impact

Frontmatter description lines across 14 files: roughly 150 → 84
(~44 % reduction). At ~10 tokens per line, this saves ~600–700 tokens
on every cold session (where the plugin's system prompt slice is
freshly cached). For warm sessions the cache amortizes; for cold
runs (`/plugin install` smoke, fresh CI agent, first session of the
day on a new machine) this is real savings.

### Statusline cleanup (in-place, mtime touched)

- `statusline/statusline-command.sh` description in `statusline/README.md`
  no longer mentions the removed `$cost` segment (was leaking back into
  the "What you get" bullet in README; now consistent).

Plugin version → **1.3.2** (patch: discoverability tuning + README
polish + screenshot; no breaking changes, no new skills).

## [1.3.1] — 2026-05-24

Discoverability follow-up to v1.3.0. The two new skills (`/adr-new`,
`/session-log`) shipped with descriptions that explained WHAT they did,
not WHEN to use them — meaning Claude Code's skill resolver wouldn't
auto-surface them at the right moment, and v1.3.0 was effectively just
two new commands users had to remember to type.

### Changed

- **`/adr-new` description** rewritten with explicit `USE WHEN ... / Do
  NOT use for ...` trigger pattern. Lists concrete examples that warrant
  an ADR (database choice, framework, auth model, explicit alternative
  rejection) and what to skip (variable naming, one-off fixes, lint
  conventions).
- **`/session-log` description** rewritten same way. Lists trigger
  signals the model should watch for in conversation (user says
  "thanks", "tomorrow", "wrap up"; 3+ commits with no log yet today; or
  explicit summary request) and what NOT to log (quick fixes,
  pure-exploration sessions).
- **`AGENTS.md`** gained a new "When to invoke `/adr-new` and
  `/session-log`" section in "Code conventions". Documents the
  invocation discipline explicitly so it's visible at session start,
  not buried in skill descriptions.

### Added

- **`docs/adr/0004-adr-and-session-log-are-user-invoked-no-auto-fire-hook.md`**
  — records the deliberate decision NOT to auto-fire either skill via a
  hook (Stop ≠ "user is leaving"; SessionStart is too late for the
  previous session's log; auto-detecting "load-bearing decision" from a
  shell hook is infeasible). Future agents proposing a Stop-hook
  variant will find the rationale here.
- **`claude-md-snippets/adr-session-log-discipline.md`** — new snippet
  that carries the convention into adopting projects via `/init-repo`,
  so agents in client repos also see the discipline at session start.
  Includes the recommended "reading order for new agents" so adopting
  projects get progressive-disclosure documentation without
  hand-authoring it.

### Fixed

- Plugin description in `marketplace.json` was still "8 on-demand
  skills" from v1.2.x; bumped to "10 on-demand skills" matching the
  shipped count.
- README install-verification block said `/skill list # confirm 8
  skills`; corrected to 10.
- `scripts/smoke-plugin.sh` skill-count check raised from `>= 8` to
  `>= 10` so a regression that loses a skill gets caught.

Plugin version → **1.3.1** (patch: discoverability fixes for v1.3.0
features + one new snippet + one new ADR; no breaking changes).

## [1.3.0] — 2026-05-24

The "durable memory" release. Adds ADR and session-log conventions plus
the two skills that make them low-friction to maintain.

### Added

- **`docs/adr/`** — Architecture Decision Records directory with MADR-
  flavored template, README index, and three seed ADRs documenting the
  most load-bearing decisions in this repo (the v1.0 pivot, the
  AGENTS.md-canonical pattern, the no-embedding-RAG choice). New
  decisions: `/adr-new`.
- **`docs/sessions/`** — Distilled session-log directory with template
  and convention README. Format: `YYYY-MM-DD-<topic>.md`. Distillate
  (context, what was done, key decisions, open questions, next steps),
  not transcript. New entries: `/session-log`.
- **`/adr-new`** skill — bootstraps a new numbered ADR. Picks next
  number, asks for title + context, fills MADR template, appends to
  index. Immutable status once accepted (`proposed` → `accepted` →
  `deprecated` / `superseded by NNNN`).
- **`/session-log`** skill — at end of a working session, distills the
  current conversation into a journal entry. Pulls branch + recent
  commits from git, model summarizes the chat. Hard cap on length
  (~80 lines) so it stays useful instead of becoming dead weight.
- **AI-specific recommendations section** in `templates/AGENTS.md.example`
  for projects that ship LLM-backed features: Langfuse/Helicone/Phoenix
  for LLM observability, Promptfoo or Langfuse evals for regression
  detection, hard cost caps before LLM calls (not inside), Pydantic/Zod
  for structured outputs, prompt-injection treatment of external data.
- **"Reading order for new agents"** section in both `AGENTS.md` and
  `templates/AGENTS.md.example`: 1) AGENTS.md, 2) docs/adr/, 3) last
  1–3 session logs, 4) specific specs on demand, 5) code via imports.
  Progressive disclosure as explicit policy.

### Changed

- Skill count: 8 → **10** (added `/adr-new`, `/session-log`).
- `templates/AGENTS.md.example` "Project" section now expects a concrete
  domain product description ("what + for whom"), not a generic
  one-liner.
- `templates/AGENTS.md.example` "Repo layout" template now includes the
  full `docs/` substructure (`adr/`, `sessions/`, `specs/`, `runbooks/`,
  `architecture/`, `conventions/`) as the recommended convention.
- `AGENTS.md` (this repo) lists 10 skills, references `/adr-new` and
  `/session-log` in maintenance rules.
- `workflows/maintaining-as-it-grows.md` extended with the "Skills you
  invoke per-decision and per-session (durable memory)" table, plus the
  maintenance-debt cycle diagram now includes the ADR + session-log
  steps.
- `CLAUDE.md` adapter notes how to invoke `/session-log` at session end.
- Plugin version bumped to **1.3.0** (new skills + new conventions; no
  breaking changes).

### Motivation

Inspired by an external conversation about AI-first dev practices that
called out three layers we were under-investing in:

1. **ADRs** as the durable record of *why* the architecture looks the
   way it does. Already had `docs/specs/` for specs; now also `docs/adr/`
   for the rationale layer, which is what stops a plausible-but-wrong
   refactor proposal from a future agent.
2. **Session logs** as the continuity layer between sessions. Without
   them, every session re-discovers context from cold. With them
   (distilled, not raw transcripts), the next agent reads the last 1–3
   logs and picks up the thread.
3. **Progressive-disclosure reading order** in AGENTS.md. The agent
   loads minimum context at session start; fetches deeper docs only when
   relevant. Explicitly documented now in both this repo and the
   template for adopting repos.

## [1.2.1] — 2026-05-24

### Added

- **Mission statement** in both `AGENTS.md` and `README.md` (above the
  "Project" / "What you get" sections). Makes the repo's actual goal —
  *help an AI dev ship secure and long-term-maintainable software for
  clients, working through Claude Code or Codex* — visible to anyone
  (or any agent) opening the repo for the first time. Three guiding
  properties enumerated: security by default, self-maintaining as the
  repo grows, cross-tool by design.
- **`workflows/security-first-feature.md`** — concrete end-to-end
  walkthrough of shipping a sensitive feature with the stack
  (`/init-repo` once → hooks fire passively → `/security-review`
  before commit → `/commit-smart` → `/explain-diff --for pr`).
  Documents what the workflow does and does NOT do for you.
- **`workflows/maintaining-as-it-grows.md`** — the "what the stack
  does automatically vs what I invoke" mental-model document.
  Includes the maintenance-debt cycle diagram (write code →
  ai-first-nudge → per-dir AGENTS.md nudge → security-nudge →
  AIDEV-TODO with deadline → stack-freshness → /stack-check → resolved
  debt) and the full table of tunable env vars per nudge.
- **`claude-md-snippets/security-review-routing.md`** — first actual
  routing snippet: promotes `/security-review` from "Stop hook might
  suggest it" to "project mandates it before commit" on diffs
  touching sensitive paths. Installable via `/init-repo`'s interactive
  flow.

### Changed

- Moved `docs/specs/2026-05-21-synthetic-benchmark-design.md` into
  `bench/archive-token-savings-thesis/` where it belongs (it's the
  design doc for the now-archived benchmark harness).
- `workflows/README.md` and `claude-md-snippets/README.md` updated to
  reflect the actual now-shipped content instead of "no content yet"
  placeholders.
- Plugin version bumped to **1.2.1** (cleanup + documentation, no
  breaking changes, no new skills).

## [1.2.0] — 2026-05-24

### Added

- **Plugin integrity tests** (`tests/test_plugin_integrity.py`):
  end-to-end validation that the shipped manifest references files that
  exist — catches "plugin install silently broke" before push. Adds a
  pytest job covering plugin.json + marketplace.json + hook path
  resolution + skill frontmatter + agent parity + stack.toml sanity.
- **`CHANGELOG.md`** (this file) — Keep-a-Changelog format for users
  running `/plugin update`.
- **Per-directory AGENTS.md nudge** in `scripts/hooks/ai-first-nudge.sh`
  — re-added with proper scoping (only fires inside detected source
  roots like `src/`, `lib/`, `app/`, `apps/`, `pkg/`, `internal/`,
  `services/`, `api/`, `cmd/`, `crates/`, `packages/`, plus monorepo-
  nested variants, AND inside a git repo, AND when the parent dir has
  8+ source files without an existing AGENTS.md in any ancestor —
  override via `CLAUDE_LEVERAGE_DIR_AGENTS_MIN`). The earlier version
  that fired on `/tmp` is fixed by this scoping.
- **AIDEV-TODO deadline syntax**:
  `AIDEV-TODO(by: 2026-08-01): description` is now supported by the
  convention. `/stack-check`'s anchor walk parses the deadline and
  flags overdue items differently from "old" items, so deadlines have
  teeth without manual chasing.

### Changed

- Statusline (`statusline/statusline-command.sh`): removed the trailing
  `$cost` estimate segment. The number was unclear without context
  (currency? which rate card?) and only correct against the Opus per-
  MTok rates. Formula preserved in the statusline README for users who
  want to add it back.
- README badges: removed the empty `[]()` link target on the Platform
  badge that was producing IDE warnings; now image-only.
- Plugin version bumped to **1.2.0** in `plugin.json` and
  `marketplace.json` (new features, no breaking changes).

### Fixed

- Nothing user-facing — the v1.1.1 review-loop fixes (regex foot-gun,
  rust template compile, atomic skills swap, etc.) shipped under
  v1.1.0 because the version wasn't bumped between them. This release
  is the first one with a real version-bump-per-feature-batch
  discipline going forward.

## [1.1.0] — 2026-05-24

### Added

- **Codex skills install**: `scripts/install-codex.sh` and `.ps1` copy
  `skills/*` to `~/.agents/skills/claude-leverage/`. All 8 skills now
  work in Codex sessions, not just Claude Code.
- **`/log-structured`** skill — audit non-structured logging in a
  codebase and suggest spec-compliant replacements per the JSON-lines
  convention.
- **`templates/logging/`** — drop-in starter kits for Python (stdlib
  logging + contextvars), TypeScript (pino + AsyncLocalStorage; native
  no-dep variant included), Go (slog + context), Rust (tracing +
  span-based trace context).
- **`/init-repo`** skill — bootstrap a fresh project with AGENTS.md
  from the per-language template, .gitignore patterns, optional
  logging template, interactive customization, idempotent via marker
  blocks.
- **AIDEV anchor age check** added to `/stack-check`: walks current
  repo for AIDEV-TODO / AIDEV-QUESTION, groups by age (fresh / aging /
  stale >90d), reports stale ones with file:line + last-modified date.
- **AGENTS.md sanity** added to `/stack-check`: file-size check vs
  Codex's 32 KiB cap, broken `@<path>` imports, possibly stale file
  references. Per-directory AGENTS.md files included.
- **Per-language dep graph** in `/repo-map` — opt-in second mermaid
  block via `madge` (JS/TS) or `pydeps` (Python). Skipped silently if
  neither tool is installed.
- **`/explain-diff`** skill — plain-English 3–5 bullet narration of the
  current diff in three audience modes (`--for pr / review / self`).
- **`/codex-sandbox`** skill — interactive helper for per-project
  `.codex/config.toml` sandbox + approval modes. Ships two profiles
  (`dev` / `prod`) plus `custom`.
- **`security-reviewer` extended** with `package.json` /
  `requirements.txt` / `pyproject.toml` / `go.mod` / `Cargo.toml` /
  `Gemfile` deps diff scan: flags typosquatting heuristics (1-char
  distance from popular names) at Important tier, suspicious version
  pins at Nice tier. Out-of-scope section now lists concrete SCA
  commands per ecosystem.
- **Per-OS `update_hint`** fields in `stack.toml` (`update_hint_macos`,
  `update_hint_linux`, `update_hint_windows`) — `manifest_version`
  bumped 1 → 2.
- **`gen-codex-agents.py --dry-run`** — prints WOULD CREATE /
  WOULD UPDATE per file with a unified diff, writes nothing.
- **`templates/AGENTS.md.example`** — per-language Build/test sections
  (Python, TypeScript/Node, Go, Rust) with toolchain-specific
  footguns documented inline.

### Removed

- **`/leverage-stats` slash command** and **`track-delegations.sh` hook**
  — observability over the tracking log no longer fits the personal-
  dev-stack framing.
- **`scripts/hooks/leverage_stats_agg.py`** and its tests — paired
  with the removed hook.
- **`/install-snippets` slash command** — bootstrapping a project is
  now handled by `/init-repo` interactively.
- **`plans/` empty directory** — cruft.

### Fixed

- `scripts/install-codex.sh`: replaced `sed` delimiter substitution
  with `Python str.replace` (sed silently corrupted `~/.codex/hooks.json`
  when REPO_DIR contained `#`).
- `scripts/install-codex.ps1`: replaced PowerShell `-replace` (regex,
  unsafe with `$` in paths) with a Python `str.replace` call mirroring
  the bash variant.
- `scripts/install-codex.sh` skills install: atomic staging-dir swap so
  a copy failure mid-loop doesn't leave users with zero skills.
- `scripts/install-codex.sh` previously had a glob-empty foot-gun on
  `.codex/agents/` — now uses explicit per-file existence check.
- `scripts/hooks/security-nudge.sh`: switched from concatenating
  `git diff --cached` + `git diff` (which double-counted lines in
  partially-staged files) to `git diff HEAD`, which is exactly "working
  tree vs HEAD" without double-counting.
- `scripts/hooks/ai-first-nudge.sh` MultiEdit branch: replaced the
  JSON-blob line counter with a Python pass over `edits[*].new_string`,
  fixing inflated counts that triggered spurious nudges on small
  MultiEdit operations.
- `scripts/hooks/stack-freshness.sh`: defensive guard on `date +%s` for
  strictly POSIX systems.
- `scripts/gen-codex-agents.py`: raise `ValueError` when frontmatter
  has no `tools` field (was silently defaulting to read-only sandbox).
- `templates/logging/rust.md`: added `chrono` feature to the
  `tracing-subscriber` dependency, replaced the broken custom
  `WithService` layer (dead RUST_LOG binding + no-op `on_event`) with
  the actually-working span-based approach.
- `templates/logging/typescript.md`: added `base: null` to pino options
  so the formatter-controlled string `level` is the only level field
  in output (was emitting both numeric and string).
- `skills/codex-sandbox/SKILL.md`: dropped the false "staging" profile
  audit-logging claim (no such Codex config field exists).
- `skills/init-repo/SKILL.md`: documented `--allow-non-git` tunable
  for the opt-in path the previous hard rule referenced but didn't
  define.

### Maintenance

- CI: added `codex-agents-parity` job running `gen-codex-agents.py
  --check`. Catches drift between `agents/*.md` and
  `.codex/agents/*.toml` automatically.
- Plugin description deliberately drops the literal word `superpowers`
  from both `plugin.json` and `marketplace.json` to avoid keyword
  collision with the unrelated `obra/superpowers-marketplace` plugin
  that this stack complements (does not replace).

## [1.0.0] — 2026-05-24

The pivot release. Starts the version line over after the v0.x token-
savings experiment was disproven by the in-repo benchmark series.

### Added

- **Personal Claude Code + Codex dev stack** framing (was: tier-routing
  for token savings).
- **`AGENTS.md`** as canonical guidance; **`CLAUDE.md`** as one-line
  `@AGENTS.md` import; same content for both tools.
- **AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION** anchor convention,
  enforced by `ai-first-nudge` PostToolUse hook.
- **Structured JSON-lines logging spec** (documented in AGENTS.md;
  templates land in 1.1.0).
- **`/security-review`** skill + read-only `security-reviewer` Sonnet
  subagent.
- **`/repo-map` and `/process-diagram`** skills for mermaid generation
  with idempotent markers.
- **`/stack-check`** skill + 30-day `stack-freshness` SessionStart hook
  (network-free; local timestamp only).
- **Portable statusline** — Python-based, no `jq` dep, Windows-friendly.
- **Codex parity layer**: `.codex/agents/*.toml` generated from
  `agents/*.md` via `scripts/gen-codex-agents.py`; `scripts/install-codex.sh`
  (+ `.ps1`) replaces the missing plugin marketplace.
- **`templates/AGENTS.md.example`** — generic AGENTS.md drop-in
  (per-language sections added in 1.1.0).

### Kept

- **Security hooks**: `block-secrets-precommit`, `block-dangerous-git`.
  Validated by benchmark as net-positive on every axis.
- **`/commit-smart`**: all-inline, with hard rules (refuse `.env`,
  never force push, never `--no-verify`).
- **`flaky-test-isolator`** subagent: only v0.x agent that survived the
  non-cost-based scrutiny (statistical signal across N runs).

### Removed (archived)

- 11 retired subagents from v0.x (`code-reviewer`, `test-runner`,
  `context-gatherer`, `repo-explorer`, `research-agent`, `docs-updater`,
  `git-committer{,-quick}`, `output-digester`, `impact-mapper`,
  `focused-reviewer`). Frozen in `bench/archive-token-savings-thesis/agents/`
  with tombstone links to benchmark verdicts.
- 4 retired wrapper commands. Same archive.
- 5 retired CLAUDE.md routing snippets. Same archive.
- The benchmark harness itself moved to
  `bench/archive-token-savings-thesis/{fixtures,harness,results}/`
  with a framing README.
- `extras/` directory entirely.
