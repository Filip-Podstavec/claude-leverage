# Session: conventions steering + adherence scorer (Phase 1 & 2)

**Date:** 2026-06-03
**Branch:** feat/adherence-scorer
**Participants:** Filip, Claude Opus 4.8
**Duration:** ~long (multi-phase)

## Context

Started from a review of the stack's own guardrails. Three gaps surfaced: the
secret-scanning hook had zero behavioral tests, CI never ran on Windows (the
maintainer's platform, where bash hooks silently skip), and the archived
token-savings benchmark bloated the repo. Then the bigger thread: the
"self-maintaining" property leaned entirely on advisory nudges with **no
measurement** of whether the conventions are followed or even read.

## What was done

- **Hardening:** behavioral tests for `block-secrets-precommit`, a `windows-latest`
  CI job (fails if bash/git absent so a skip can't masquerade as a pass), and a
  surgical prune of the bench archive (raw transcripts + regenerable git fixtures;
  16 → 4.3 MB) keeping the documentary evidence.
- **Adherence scorer (Phase 1):** `scripts/score_adherence.py` — deterministic
  naming/casing/structure scoring, `--repo`/`--diff`, language-pluggable (Python
  first). A code review caught a real bug (multi-line signatures collapsed the
  function-length metric) — fixed.
- **Conventions steering (Phase 2, a+b):** `conventions.yml` → `build-context-map.py`
  folds it into the manifest → `context-surface` hook surfaces a compact block
  before source-file edits → `ai-first-nudge` advisory on casing/vague drift in the
  edit blob. Plus `/conventions-init` (15th skill) to draft `conventions.yml`.
  Dogfooded on this repo. 176 tests green.

## Key decisions

- **Measurement-first, steer-first.** Build the cheap deterministic signal before
  any aggressive steering; never block on semantic judgments (false-positives +
  slop-ticking). Escalate to enforcement only with evidence.
- **Synthetic single-file tests do NOT measure plugin value** — a capable model
  writes clean generic code unaided. Built such experiments, then **rolled them
  back out of history** ("as if they never happened") once it was clear they
  can't reveal the real value. The valid eval is the optimized-vs-unoptimized
  full-repo A/B (`bench/eval`). Saved as a durable memory.
- **What the synthetic probe DID show:** a non-default house rule (a function
  prefix) was applied 100% with the conventions doc vs 0% without — i.e. agents
  *do* apply conventions they cannot infer; the plugin's value is conveying the
  *non-default*, not policing default-good style.
- **Conventions live in `_meta.conventions` (once), role computed in the hook at
  runtime** — because the manifest only has per-file entries for anchored files.
- **No manifest schema bump** (additive fields); `BUILDER_VERSION` bumped to 1.9.0.

## Open questions

- Phase 2's value still needs the full-repo A/B on a real codebase to confirm
  output-quality impact (synthetic won't show it).
- Nudge + casing inference are Python-only; other language packs are future work.

## Next steps

- Nothing pushed yet — decide PR strategy for `feat/adherence-scorer` (stacked:
  hardening + scorer + Phase 2).
- Set up conventions on the private test repo (`/conventions-init` → fill house
  rules → `/refresh-context-map`); verify delivery deterministically, then run the
  full-repo before/after A/B for the quality question.

## References

- Commits: `ccdc6ab` (hardening), `f349ca8..b9d3ac3` (scorer), `7d9a119..0830588` (Phase 2).
- Specs: `docs/specs/2026-06-02-conventions-adherence-design.md`,
  `docs/specs/2026-06-03-conventions-steering-phase2-design.md` (+ plans 2a/2b).
- Consider `/adr-new` for: measurement-first/steer-first, and conventions-in-`_meta`.

---

*Distillate, not transcript.*
