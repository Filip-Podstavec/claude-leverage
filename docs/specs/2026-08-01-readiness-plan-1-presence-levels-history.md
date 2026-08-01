# Plan 1 — Presence dims 21–24, levels, history, `--fix` (v1.14.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** v2 — revised after Opus design review (findings 1–19 folded in).
> Parent design:
> [2026-08-01-readiness-extension-design.md](2026-08-01-readiness-extension-design.md).

**Goal:** Ship the fully deterministic half of the readiness extension: ADR
0012, four new Hygiene dimensions, the L0–L4 levels layer, local history +
trend, the anti-Goodhart companion doc, `--fix` guided handoff, and the SKILL
consistency fixes surfaced by review.

**Architecture:** All behavior changes are prose in
`skills/repo-doctor/SKILL.md` (the skill's *checks* are model-executed; state
I/O uses exact shell commands the model must run verbatim, mirroring
`/stack-check`), plus one new ADR, one new docs page, one new test file, and
the standard maintenance artifacts. No new agents, no hooks.

**Tech Stack:** Markdown (SKILL.md, ADR, docs, CHANGELOG, READMEs), JSON
manifests, pytest (stdlib-only regex tests).

## Global Constraints

- Deterministic score only — nothing in this plan may make the 0–100 score
  depend on a model judgment or command execution (ADR 0012).
- Read-only on the repo. The only writes are to the state dir, resolved with
  the same three-leg fallback chain as `scripts/hooks/stack-freshness.sh`:
  `${CLAUDE_LEVERAGE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/claude-leverage}`,
  falling back to `$HOME/.claude/claude-leverage` if that dir cannot be
  created.
- No network, no `origin` requirement, no telemetry.
- Dimension numbering 1–20 must not change; new dims append as 21–24.
- The score stays a per-dimension unweighted sum (design doc: no re-weighting).
- Version bump to **1.14.0** in BOTH `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json`, then `python scripts/gen-codex-plugin.py`.
  On this machine use `python`, never `python3` (broken MS Store stub).
- Commit messages: conventional-commit style, **no Co-Authored-By line**.
- SKILL.md description frontmatter stays a folded scalar (`>`), per ADR 0006.
- Level names/gates and the gate formula: ADR 0012 is canonical; SKILL.md and
  the design doc must use identical wording.

---

### Task 1: ADR 0012 — deterministic core / advisory halo + levels

**Files:**
- Create: `docs/adr/0012-repo-doctor-levels-and-deterministic-core.md`
- Modify: `docs/adr/README.md` (index — add one line, match existing rows)

**Interfaces:**
- Produces: the constraint text Tasks 2–7 and Plans 2/3 cite. The gate
  formula and level ladder defined here are the single source of truth.

- [ ] **Step 1: Write the ADR** following `docs/adr/template.md` structure
  (Date 2026-08-01, Status accepted, Deciders Filip Podstavec). Sections:

  - **Context:** external review vs Factory readiness framework; three
    critiques (presence≠quality, vendor lock/telemetry, L5 marketing); the
    existing score is reproducible and CI-gated via `--fail-on`; Opus design
    review reshaped the levels layer (gate formula, ladder order).
  - **Decision:**
    - (a) the deterministic 0–100 score never includes model-judged or
      execution-dependent results; semantic (`--semantic`, Plan 2) and
      dynamic (Plan 3) render as separate advisory sections, CI-gateable only
      via explicit `--fail-on semantic`;
    - (b) levels L0 Ad-hoc / L1 Instructed (Foundation) / L2 Maintained
      (Hygiene) / L3 Explained (Why AND What) / L4 Self-consistent (In-code
      AND Sync), cumulative. **Gate formula (canonical):**
      `deficit = evaluated − points; passes ⟺ deficit ≤ max(0.5, 0.2 × evaluated)`
      — the 80 % rule for groups ≥3 dims, with a floor so 2-dim groups
      tolerate one ⚠️ but no ❌. A required group with zero evaluated dims
      **blocks** its gate (`not assessable`), never satisfies it. No L5;
    - (c) history is a local JSONL in the state dir, written by shell
      redirection, records carry `v` + `evaluated` so trends across
      dimension-set changes are annotated, not misread — no cloud, no
      `origin`;
    - (d) CODEOWNERS + issue/PR-template dims rejected (team-process
      artifacts, Goodhart bait, high N/A rate);
    - (e) every dimension documents its own gaming vector in
      `docs/repo-doctor-gaming.md`; the plugin's own `claude-leverage:`
      marker never scores ✅ on Dim 24 (vendor self-preference guard);
    - (f) **dynamic-scope carve-out reserved:** if layer 3 is scheduled, it
      ships as a separate skill with its own frontmatter — a broad Bash grant
      must not sit in `/repo-doctor`'s always-active `allowed-tools`, because
      prose cannot gate frontmatter permissions.
  - **Consequences:** positive (CI number stays stable; levels give a
    management-facing vocabulary that follows the stack's adoption funnel;
    local trend without vendor lock) and negative (two verdict systems to
    explain; the gate formula's 0.5 floor is opinionated — no override knob
    in v1; appending dims 21–24 shifts the score's internal weight toward
    Hygiene, 6/20 → 10/24 — accepted and documented rather than re-weighted,
    same call as ADR 0007's divisor change; state file grows one line per
    run, capped ~100).
  - **Alternatives considered:** merge semantic into the score (rejected:
    breaks reproducibility); separate `/readiness` skill (rejected: same
    "one audit command" rationale as ADR 0007); percentage-stated gates
    (rejected: 2-dim groups can only hit 0/50/75/100 %, so an 80 % phrasing
    demands perfection there); Hygiene-first ladder with L1 "Buildable"
    (rejected: labels a well-documented legacy repo "Ad-hoc" on test-ratio
    grounds; Foundation-first matches `/init-repo` as the L1 bootstrap);
    satisfied-by-absence for all-N/A groups (rejected: awards L-levels to
    empty repos); score re-weighting to equal group weights (rejected:
    keeps two arithmetic systems aligned but makes the per-dim score
    illegible); Factory's L5 (rejected: unverifiable); cloud/report storage
    (rejected: compliance blocker).
  - **References:** ADR 0006, ADR 0007, Factory agent-readiness docs (link),
    the external review and the Opus design review (summarized, not pasted).

- [ ] **Step 2: Add the index line** to `docs/adr/README.md` in the existing
  format.

- [ ] **Step 3: Verify** `pytest tests/ -v` passes and the filename matches
  `^0012-.*\.md$`.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0012-repo-doctor-levels-and-deterministic-core.md docs/adr/README.md
git commit -m "docs(adr): 0012 repo-doctor levels + deterministic-core contract"
```

---

### Task 2: Dimensions 21–24 + SKILL consistency fixes

**Files:**
- Modify: `skills/repo-doctor/SKILL.md` — Hygiene section (after Dim 15),
  Dim 15 itself, frontmatter `description` + `argument-hint`, "What it does"
  line ("~15 dimensions" — stale since v1.7), Dimensions heading counts,
  Workflow step 4 divisor text (20 → 24), Tunables `--scope` list, example
  report.

**Interfaces:**
- Produces: dim ids `ci-config`, `env-example`, `repro-env`,
  `secret-guardrails` (Hygiene group; used by Task 3 gate math and `--json`);
  the shared N/A predicate `P` cited by Dims 15/21/23.

- [ ] **Step 1: Define the shared N/A predicate** once, at the top of the
  Dimensions section:

  ```markdown
  **Predicate P (no-code repo):** the repo has zero tracked files matching
  the Dim 3 code-extension list. Dimensions that reference P return N/A
  when it holds — a docs-only repo gets no verdict (and no free ✅) on
  code-shaped checks.
  ```

- [ ] **Step 2: Fix Dim 15** — replace its `✅ otherwise` band so a code-less
  repo returns N/A (predicate P), not ✅. One-line change; note it in the
  CHANGELOG entry (Task 7) as a scoring-behavior fix.

- [ ] **Step 3: Append the four dimension specs** after Dim 15, under
  `### Engineering hygiene — delivery additions (4 checks, v1.14.0)`:

  ```markdown
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
      noise-path filter as Dim 8) and count distinct files with hits.
      - N/A if no env usage detected.
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
  ```

- [ ] **Step 4: Update the surrounding prose** — "What it does" line: "~15" →
  "~24 dimensions"; frontmatter description Hygiene list gains "CI config,
  .env.example, repro env, secret guardrails"; heading "Engineering hygiene
  (6 checks)" → "(10 checks)"; Workflow step 4 "20 minus N/A" → "24 minus
  N/A"; normalize the `--scope` value list to
  `foundation|why|what|incode|hygiene|sync|all` in BOTH the frontmatter
  `argument-hint` (currently missing `sync`, has no in-code scope at all) and
  the Tunables section; example-report Hygiene table gains four rows; the
  "Future / not in scope" bullet on per-language quality gates gets: "CI
  *presence* is Dim 21; lint/type-check configs remain out of scope."

- [ ] **Step 5: Dry-run** — invoke `/repo-doctor --scope hygiene` on this
  repo; confirm the four dims produce sane verdicts here (expect: 21 ✅,
  22 N/A, 23 ✅-with-note or ✅, 24 ✅ — `.githooks/` + CI) and the divisor
  note reflects reality.

- [ ] **Step 6: Verify** `pytest tests/ -v`.

- [ ] **Step 7: Commit**

```bash
git add skills/repo-doctor/SKILL.md
git commit -m "feat(repo-doctor): presence dims 21-24 + N/A predicate + scope-list fix"
```

---

### Task 3: Levels layer

**Files:**
- Modify: `skills/repo-doctor/SKILL.md` — new `## Levels` section after
  "Dimensions"; Summary line format; `--json` schema in Workflow step 5.

**Interfaces:**
- Consumes: per-dim points/N-A verdicts grouped as
  Foundation/Why/What/In-code/Hygiene/Sync; Task 2 dims count toward Hygiene.
- Produces: JSON fields `groups` (per-group `{points, evaluated}`) and
  `level: {n, name, blocked_by}` consumed by Task 4 history records.

- [ ] **Step 1: Add the `## Levels` section** (wording must match ADR 0012):

  ```markdown
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
  ```

- [ ] **Step 2: Extend the Summary line** in the output-format example:
  `✅ 8 · ⚠️ 4 · ❌ 3 · **Score: 67/100** · **Level: L1 Instructed (L2
  blocked by Hygiene: deficit 2.5 > 2.0)**` and extend the `--json` example
  (numbers must be self-consistent — points are multiples of 0.5):

  ```json
  "groups": {
    "foundation": {"points": 2.5, "evaluated": 3},
    "why": {"points": 1.0, "evaluated": 2},
    "what": {"points": 2.0, "evaluated": 2},
    "incode": {"points": 2.0, "evaluated": 2},
    "hygiene": {"points": 6.5, "evaluated": 9},
    "sync": {"points": 3.5, "evaluated": 4}
  },
  "level": {"n": 1, "name": "Instructed", "blocked_by": "hygiene"}
  ```

- [ ] **Step 3: Dry-run** full `/repo-doctor` on this repo; hand-check one
  group's deficit arithmetic against the table; confirm the level line and
  `blocked_by` are consistent.

- [ ] **Step 4: Commit**

```bash
git add skills/repo-doctor/SKILL.md
git commit -m "feat(repo-doctor): L0-L4 readiness levels with deficit gating"
```

---

### Task 4: History + trend

**Files:**
- Modify: `skills/repo-doctor/SKILL.md` — allowed-tools, Tunables, Workflow,
  Hard rules, frontmatter `argument-hint`.

**Interfaces:**
- Consumes: Task 3 JSON fields (`score`, `groups`, `level`).
- Produces: `$STATE_DIR/repo-doctor/<slug>.jsonl`, one line per full run:
  `{"date":"2026-08-01","v":"1.14.0","evaluated":22,"score":67,"groups":{…},"level":1}`.

- [ ] **Step 1: Extend allowed-tools** with the commands the steps below
  actually run (permission matching is prefix-based, so every leading binary
  must be listed): `Bash(printf:*)`, `Bash(basename:*)`, `Bash(cksum:*)`,
  `Bash(cut:*)`, `Bash(mkdir:*)`, `Bash(tail:*)`, `Bash(pwd:*)`, AND the
  **pre-existing gap** `Bash(git log:*)` (Dims 16–18 already require
  `git log -1 --format=%ct` — under-permissioned since v1.7.0; note in
  CHANGELOG). Do NOT add `Write` — state writes use shell redirection only.

- [ ] **Step 2: Add the workflow step** (after step 5 "Emit the report"):

  ```markdown
  5b. **History + trend (default on; skip with `--no-history`, skip when
      `--scope` is narrowed).** Resolve `STATE_DIR` with the same fallback
      chain as `scripts/hooks/stack-freshness.sh` (env override → XDG →
      `$HOME/.claude/claude-leverage`). Canonicalize the repo root before
      hashing (`ROOT_CANON=$(cd "$ROOT" && pwd -P)`) so worktree/symlink
      spellings don't fork the history, then:
      `SLUG="$(basename "$ROOT_CANON")-$(printf '%s' "$ROOT_CANON" | cksum | cut -d' ' -f1)"`.
      Read the last line of `$STATE_DIR/repo-doctor/$SLUG.jsonl` (if any)
      and emit a Trend line in the Summary:
      `Trend: 61 → 67 (+6) since 2026-07-12 · level L1 → L2`.
      If the previous record's `v` or `evaluated` differs from this run,
      annotate instead of celebrating:
      `Trend: 61 → 67 since 2026-07-12 (dimension set changed 20 → 22 — delta not comparable)`.
      Then `mkdir -p "$STATE_DIR/repo-doctor"` and append **exactly** (do
      NOT retype or rewrite existing file contents — append only):

      printf '%s\n' '<compact-json-record>' >> "$STATE_DIR/repo-doctor/$SLUG.jsonl"

      If the file exceeds ~200 lines, note it and trim to the last 100 via
      `tail -n 100` into a temp file in the same dir, then move it back.
  ```

- [ ] **Step 3: Update Hard rules + docs** — replace the read-only bullet
  with: "Read-only on the repo: never modify, create, or delete any file in
  the repo. The only writable location is the local state dir
  (`.last-repo-doctor` timestamp and `repo-doctor/<slug>.jsonl` history)."
  Update the "What it does" line ("Read-only. Modifies nothing." →
  "Read-only on the repo; writes only local state — see Hard rules") and the
  differentiation table row if it repeats the claim. Add `--no-history` to
  Tunables and the frontmatter `argument-hint`. In the Codex-parity section,
  state that history uses plain shell redirection and works identically in
  both tools.

- [ ] **Step 4: Dry-run twice** on this repo; confirm the second run prints a
  Trend line, the JSONL has exactly two appended lines, and a third run from
  a different path spelling (e.g. via symlink if available) hits the same
  slug.

- [ ] **Step 5: Verify** `pytest tests/ -v`.

- [ ] **Step 6: Commit**

```bash
git add skills/repo-doctor/SKILL.md
git commit -m "feat(repo-doctor): local history + trend (--no-history), fix git-log permission gap"
```

---

### Task 5: Anti-Goodhart companion doc + `--fix` mode

**Files:**
- Create: `docs/repo-doctor-gaming.md`
- Modify: `skills/repo-doctor/SKILL.md` — one when-to-read link; new
  `--fix [N]` tunable + workflow step 6b; frontmatter `argument-hint`.

**Interfaces:**
- Consumes: the "Recommended next 3 actions" list already emitted.

- [ ] **Step 1: Write `docs/repo-doctor-gaming.md`** — intro paragraph (why
  every metric documents its own evasion — honest-history ethos) + a 24-row
  table `| Dim | Gamed by | Countered by |`. Fill all 24 honestly; required
  tone by example: Dim 1 "1-line AGENTS.md passes `test -f` | size floor not
  enforced — accepted; planned semantic review (S1, ADR 0012) judges
  content"; Dim 10 "empty `tests/` dir | file-count ≥1 check"; Dim 21
  "workflow file with no jobs | trigger grep; residual risk accepted";
  Dim 22 "empty `.env.example` | requires ≥1 `KEY=` line"; Dim 24 "adopting
  the stack marker without installing hooks | marker caps at ⚠️ — see ADR
  0012". Since this ships in v1.14.0, phrase semantic counters as
  "(planned: `--semantic`, ADR 0012)" — never promise a flag that errors.

- [ ] **Step 2: Link it from SKILL.md** with one line in the Dimensions
  intro: "How each dimension can be gamed — and what counters it:
  [`docs/repo-doctor-gaming.md`](../../docs/repo-doctor-gaming.md). Read it
  before trusting a suspiciously green report."

- [ ] **Step 3: Verify the `--fix` mechanism before speccing it in** — in a
  scratch session, test whether a skill invocation from within a running
  skill works under `/repo-doctor`'s allowed-tools (no in-repo precedent).
  Record the result in the commit message. Fallback if unavailable: `--fix`
  prints the exact slash command per accepted item and stops.

- [ ] **Step 4: Add `--fix [N]`** to Tunables and a workflow step **6b**
  (before the exit-code step, which stays last):

  ```markdown
  6b. **`--fix [N]` (default 3).** After emitting the report, walk the
      recommended actions top-down. Per item: show the gap + the mapped
      skill, ask the user (one item at a time), on yes invoke that skill
      (it carries its own confirmation flow) — or, where skill invocation
      is unavailable, print the exact slash command to run; on no move on.
      The doctor itself writes nothing in the repo. `--fix` implies the
      recommendations walk even when `--no-recommend` is passed (`--fix`
      wins, with a note). After the walk, suggest `/repo-doctor --quiet`
      to re-score. In non-interactive runs (`--score`, `--json`, CI),
      ignore `--fix` and print a one-line warning.
  ```

  Also extend the "What this skill does NOT do" bootstrap bullet:
  "(`--fix` only *invokes* those skills interactively; it never writes
  files itself)". Update the differentiation table's `/repo-doctor` row to
  "completeness audit + guided handoff (`--fix`)".

- [ ] **Step 5: Verify** `pytest tests/ -v`; dry-run `/repo-doctor --fix 1`
  on this repo and confirm it offers exactly one action and exits cleanly on
  "no".

- [ ] **Step 6: Commit**

```bash
git add docs/repo-doctor-gaming.md skills/repo-doctor/SKILL.md
git commit -m "feat(repo-doctor): anti-Goodhart companion doc + --fix guided handoff"
```

---

### Task 6: Regex integrity tests

**Files:**
- Create: `tests/test_repo_doctor_skill.py`

**Interfaces:**
- Consumes: `skills/repo-doctor/SKILL.md` as text; `docs/repo-doctor-gaming.md`.

- [ ] **Step 1: Write the failing tests** (stdlib-only, matching the house
  test style in `tests/test_plugin_integrity.py`):

  ```python
  import re
  from pathlib import Path

  SKILL = Path(__file__).resolve().parents[1] / "skills" / "repo-doctor" / "SKILL.md"
  GAMING = Path(__file__).resolve().parents[1] / "docs" / "repo-doctor-gaming.md"


  def _skill_text():
      return SKILL.read_text(encoding="utf-8")


  def test_dimensions_contiguous_and_unique():
      nums = [int(m) for m in re.findall(r"^(\d+)\. \*\*", _skill_text(), re.M)]
      assert nums == list(range(1, 25)), f"dims not 1..24 exactly once: {nums}"


  def test_group_heading_counts_sum_to_24():
      counts = [int(m) for m in re.findall(r"^###.*\((\d+) checks?\b", _skill_text(), re.M)]
      assert sum(counts) == 24, f"group heading counts {counts} sum to {sum(counts)}, not 24"


  def test_scope_values_consistent():
      text = _skill_text()
      hint = re.search(r"--scope ([a-z|]+)", text.split("---", 2)[1])  # frontmatter
      tunable = re.search(r"`--scope ([a-z|]+)`", text.split("---", 2)[2])
      assert hint and tunable, "missing --scope in frontmatter or Tunables"
      assert hint.group(1) == tunable.group(1), (hint.group(1), tunable.group(1))


  def test_gaming_doc_has_one_row_per_dimension():
      rows = re.findall(r"^\| (\d+) \|", GAMING.read_text(encoding="utf-8"), re.M)
      assert sorted(int(r) for r in rows) == list(range(1, 25))
  ```

- [ ] **Step 2: Run to verify they fail** before Tasks 2–5 land (or, if this
  task runs last, verify they pass and then mutate one heading locally to
  confirm each assertion actually bites — revert after).

Run: `pytest tests/test_repo_doctor_skill.py -v`

- [ ] **Step 3: Run the full suite** — `pytest tests/ -v`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_repo_doctor_skill.py
git commit -m "test(repo-doctor): SKILL internal-consistency regex guards"
```

---

### Task 7: Maintenance artifacts + release

**Files:**
- Modify: `README.md` (what's-inside row for `/repo-doctor`; "Scores ~20
  dimensions" at both occurrences ≈ L104 and L309 → "~24"), `skills/README.md`
  (same), `workflows/onboarding-a-legacy-repo.md` ("~20 dimensions" line;
  "read-only" wording → "read-only on the repo, local state only"),
  `CHANGELOG.md` (new `## [1.14.0]` top entry), `.claude-plugin/plugin.json`
  + `.claude-plugin/marketplace.json` (version 1.14.0). `AGENTS.md` needs no
  change (lists skill names only; lean budget unaffected).
- Regenerate: `.codex-plugin/` + `.agents/` via `python scripts/gen-codex-plugin.py`.

- [ ] **Step 1: Update README + skills/README + onboarding workflow** rows
  describing `/repo-doctor` (~24 dims, levels L0–L4, local trend, `--fix`).

- [ ] **Step 2: CHANGELOG** — `## [1.14.0]`: Added (dims 21–24, levels,
  history/trend, `--fix`, gaming doc, ADR 0012, consistency tests); Fixed
  (Dim 15 ✅-on-empty → N/A, `--scope` list normalization, missing
  `Bash(git log:*)` for Sync dims, stale "~15 dimensions" line); Changed
  (score weight shifts toward Hygiene, 6/20 → 10/24 of dimensions — see ADR
  0012).

- [ ] **Step 3: Bump versions + regen**

```bash
python scripts/check_version_sync.py   # after editing both manifests
python scripts/gen-codex-plugin.py
```

- [ ] **Step 4: Full verification**

```bash
pytest tests/ -v
python scripts/check_version_sync.py
python scripts/gen-codex-plugin.py --check
bash scripts/smoke-plugin.sh
```

- [ ] **Step 5: Commit**

```bash
git add README.md skills/README.md workflows/onboarding-a-legacy-repo.md CHANGELOG.md .claude-plugin/ .codex-plugin/ .agents/
git commit -m "chore(release): v1.14.0 - repo-doctor readiness levels + presence dims"
```

---

## Self-review notes

- Spec coverage: design-doc items "dims 21–24", "levels", "history", "--fix",
  "anti-Goodhart", "ADR 0012", "consistency fixes", "tests" → Tasks 2, 3, 4,
  5, 5, 1, 2+4, 6. Semantic/dynamic are Plans 2/3 by design.
- Dim 22/24 interaction (`.env` gitignore) is assigned to exactly one dim (24).
- Gate formula appears in three places (ADR, SKILL, design doc) — identical
  wording; ADR is canonical.
- All shell in Task 4 is covered by an enumerated allowed-tools prefix; no
  `Write` tool anywhere in this plan.
