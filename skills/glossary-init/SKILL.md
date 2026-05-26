---
name: glossary-init
description: >
  USE WHEN setting up a repo for AI-first work, when an agent hallucinates
  domain term meaning, or when user asks to bootstrap / extend the
  repo's domain glossary. Surfaces candidate terms by identifier
  frequency, asks the user for 1-sentence definitions, writes
  `GLOSSARY.md` at repo root. Idempotent — re-running adds new terms
  without overwriting existing ones. Read-only on code; never invents
  domain meaning. Full Do/Don't list in this SKILL body. See ADR 0005
  for why this file lives at root.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git rev-parse:*)
  - Bash(git ls-files:*)
  - Bash(test:*)
  - Bash(ls:*)
  - Bash(wc:*)
argument-hint: "[--top N] [--lang python|typescript|go|rust|auto] [--add term] [--noninteractive]"
---

# /glossary-init

## What it does

Bootstraps (or extends) `GLOSSARY.md` at the repo root — a human-curated
dictionary of domain terms specific to *this* repo. One entry per term:
1–2 sentence definition, optional aliases, optional code-path pointers.

The point: the next agent opening this repo greps `GLOSSARY.md` once
and stops hallucinating that "Lead" means a sales prospect when *here*
it means a journalist's article lead. Reading source to recover
domain meaning per session is O(N) tokens per term; a one-line glossary
entry is O(1).

This skill **surfaces candidate terms** (by frequency of identifier
appearance in tracked code). It **never invents definitions** — the
user types them, the skill structures the file. See ADR 0005 for the
rationale.

## When to invoke

- First setup of an AI-first repo (after `/init-repo`).
- When you notice an agent halucinating the meaning of a recurring
  domain term ("I think `Lead` is a sales prospect" — no, it's a
  journalist's article).
- Periodically as the domain vocabulary grows — re-run to add new
  terms (existing entries are preserved).

Do NOT invoke for:

- Code-level documentation (those go in docstrings / type hints).
- Cross-project / cross-client patterns (those live in the user's PKB,
  not in this repo's glossary).
- "What does this function do?" — that's what the code shows.

## Workflow

1. **Resolve repo root.** `git rev-parse --show-toplevel`. If not in a
   git repo, STOP and report: "glossary needs a tracked repo; `git
   init` first or run `/init-repo`".

2. **Detect mode.**
   - If `GLOSSARY.md` does not exist at root → **bootstrap mode**.
   - If `GLOSSARY.md` exists and `$ARGUMENTS` includes `--add <term>` →
     **single-add mode** (skip candidate ranking, jump to step 6 for
     that one term).
   - If `GLOSSARY.md` exists and no `--add` → **extend mode**: surface
     candidates that aren't already in the existing file, propose
     additions.

3. **Detect primary language** by file extension counts in tracked
   files (`git ls-files | head -2000`):
   - `.py` → Python
   - `.ts` / `.tsx` / `.js` / `.jsx` → TypeScript / JavaScript
   - `.go` → Go
   - `.rs` → Rust
   - Mixed → use all detected.
   - Override with `--lang`.

4. **Walk identifiers.** From `git ls-files` (skip generated paths,
   tests, vendor, node_modules, `__pycache__`, `dist`, `build`,
   `.git`, `bench/`), extract identifiers via language-aware patterns:
   - Python: `class\s+([A-Z][A-Za-z0-9_]+)` (classes — high signal),
     `def\s+([a-z_][a-z0-9_]+)` (functions — medium signal). Domain
     terms are usually classes / type aliases / dataclasses, not
     ordinary functions.
   - TypeScript: `(?:class|interface|type|enum)\s+([A-Z][A-Za-z0-9_]+)`.
   - Go: `type\s+([A-Z][A-Za-z0-9_]+)\s+(?:struct|interface)`.
   - Rust: `(?:struct|enum|trait|type)\s+([A-Z][A-Za-z0-9_]+)`.

   Count occurrences across the repo (not just declarations — also
   usage). The more a term is referenced, the more load-bearing.

5. **Filter and rank.** Drop:
   - Language keywords, standard library names, common framework
     base classes (`BaseModel`, `Exception`, `HTTPException`, `Error`,
     `Request`, `Response`, `Client`, `Config`, `Settings`).
   - Single-character names, names < 3 chars.
   - Generic CRUD verbs presented as nouns (`Get`, `Set`, `Create`,
     `Update`, `Delete` alone).
   - PascalCase that's plausibly a library type (rough heuristic:
     starts with `Http`, `Json`, `Sql`, `Db`, `Aws`, `Gcp`, `Azure`).

   Rank remaining by `occurrences * log(distinct_files)` — terms that
   appear in many places AND many files are more central than a term
   used 50 times in one file.

   Cap candidates at `--top N` (default 30).

6. **Surface candidates** (skip in `--add` mode):

   ```
   I found these load-bearing domain terms in <repo>:

   1. Tenant       (47 refs across 12 files) — e.g. src/auth/tenant.py:14
   2. Invoice      (38 refs across 8 files)  — e.g. src/billing/invoice.py:8
   3. Lead         (29 refs across 6 files)  — e.g. src/content/lead.py:22
   ...

   Pick which to include (numbers separated by spaces, "all", or "skip").
   ```

   In `--noninteractive` mode, include the top 15 with `<TODO: definition>`
   placeholders so the user fills them later. Mark such entries with
   an HTML comment `<!-- claude-leverage:glossary-todo -->` so future
   runs can spot them.

7. **For each picked term, prompt:**
   - 1–2 sentence definition (required).
   - Aliases (optional, comma-separated): other names the same concept
     goes by in code, docs, conversations with this user.
   - Code pointers (optional): up to 3 representative paths.

   In `--noninteractive`, fill definition with `<TODO>` placeholder.

8. **Write `GLOSSARY.md`.**

   ```markdown
   <!-- claude-leverage:glossary v1 -->
   # Glossary

   Domain terms specific to this repo. Hand-curated. Update via
   `/glossary-init --add <term>` or by editing this file directly.
   Read this **before** assuming a term means what it does elsewhere —
   domain vocabulary diverges between projects.

   ## Tenant

   A customer organization. One Tenant → many Users. Distinct from
   "Account" which is the billing entity.

   - Aliases: org, organization
   - Code: `src/auth/tenant.py`, `src/billing/account.py`

   ## Invoice

   <definition>
   ```

   Entries are sorted alphabetically by term (case-insensitive). Each
   entry is one H2 + body + optional bullet list. The H1 + intro
   paragraph + `claude-leverage:glossary v1` marker are written exactly
   once on bootstrap; subsequent runs preserve them.

9. **Update AGENTS.md** (idempotent, ask before write). If
   `AGENTS.md` exists at root and doesn't already mention `GLOSSARY.md`,
   offer to append a one-line pointer at the end of the "Code
   conventions" section:

   ```markdown
   ### Domain glossary

   Domain terms specific to this repo live in [`GLOSSARY.md`](GLOSSARY.md).
   **Grep there before assuming** what a term means — domain vocabulary
   diverges between projects.
   ```

   Skip if `--no-update-agents-md` is passed.

10. **Report.** Print the new path, count of entries added, count of
    `<TODO>` placeholders remaining. Remind the user that ranking is
    just a starting point; entries can be added by hand or via
    `--add <term>` at any time.

## Hard rules

- **Never invent a definition.** All entries in the glossary come from
  the user (interactive) or are explicit `<TODO>` placeholders
  (`--noninteractive`). LLM-generated definitions are exactly the
  problem this skill exists to prevent — see ADR 0005.
- **Never overwrite existing entries.** Re-running in extend mode adds
  new terms and leaves existing definitions untouched. If the user
  wants to revise a definition, they edit `GLOSSARY.md` by hand.
- **Never block.** This is a discoverability skill; output is advisory
  if the user declines all candidates.
- **Preserve the schema marker.** The top line
  `<!-- claude-leverage:glossary v1 -->` is load-bearing — future
  versions of this skill use it to detect format.
- **Sort entries alphabetically by term (case-insensitive).** Stable
  ordering keeps diffs readable when the user adds an entry by hand.

## Tunables

- `--top N` — surface top N candidates (default 30, hard cap 100).
- `--lang python|typescript|go|rust|auto` — language to scan (default
  auto-detect by file count). `auto` runs all detected.
- `--add <term>` — skip candidate ranking; add this single term
  interactively. Useful when you notice a missing term mid-session.
- `--noninteractive` — write top 15 candidates with `<TODO>`
  placeholders for definitions; no prompts.
- `--no-update-agents-md` — skip the AGENTS.md pointer step.
- `--target <path>` — non-default file location (default
  `<repo-root>/GLOSSARY.md`).

## What this skill does NOT do

- **Auto-define terms** from code, docstrings, or external sources.
  LLM-generated AGENTS-style files lose 0.5–2pp on task success vs.
  human-curated (Augment Code 2026 study). Definitions are the user's
  job.
- **Track all identifiers.** Glossary scope is ~10–30 load-bearing
  domain terms. Per-function / per-method documentation belongs in
  docstrings, not here.
- **Auto-update on commits.** Domain vocabulary changes slowly; churn
  on every commit would be noise. Re-run the skill periodically.
- **Cross-project / client patterns.** Those live in the user's
  personal knowledge base (PKB), not in this repo's glossary.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. The Codex
host reads identifiers the same way and writes the same
`GLOSSARY.md` format. No tool-specific divergence.

## Future / not in scope here

- `/stack-check` could be extended to validate `GLOSSARY.md` against
  the v1 marker, flag entries with `<TODO>` placeholders, and warn on
  entries whose `Code:` paths no longer exist. Tracked as a future
  enhancement, not part of this skill.
- `/init-repo` could prompt for glossary bootstrap on first run for
  domain-heavy projects. Future enhancement.
