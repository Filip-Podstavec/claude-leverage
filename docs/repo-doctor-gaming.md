# How each `/repo-doctor` dimension can be gamed

Every metric invites its own evasion (Goodhart's law), and a readiness score
you can cheat is worse than no score — it converts an honest gap into false
confidence. This table documents, per dimension, the cheapest way to score
green without earning it, and what (if anything) counters it. Where the
counter is "accepted", that is a deliberate call: the deterministic layer
stays simple and legible, and the quality question moves to the semantic
review (`--semantic`, ADR 0012) or to `/dynamic-check`. Read this before
trusting a suspiciously green report — yours or a vendor's.

| Dim | Check | Gamed by | Countered by |
|---|---|---|---|
| 1 | AGENTS.md (root) | 1-line file passes `test -f` + size bands | size floor not enforced — accepted; semantic review (S1) judges content |
| 2 | CLAUDE.md import | valid `@AGENTS.md` import plus contradicting extra prose below it | only import presence checked — accepted; semantic review (S4) catches contradictions |
| 3 | Per-dir AGENTS.md | empty AGENTS.md dropped into each big dir | none deterministic — accepted; Dim 18 catches subsequent staleness, S1 judges content |
| 4 | ADRs | 3 template-placeholder ADRs to clear the count | count-only — accepted; semantic review (S3) judges substance |
| 5 | Session logs | `touch` a log file / commit an empty one to refresh the date | filename-date parse only — accepted; content not judged |
| 6 | GLOSSARY.md | circular one-liners ("Account: an account") instead of `<TODO>` | `<TODO>`-ratio check only — accepted; semantic review (S5) judges informativeness |
| 7 | architecture.yml | keep `<TODO>` share just under 30 % | threshold is blunt — accepted; Dim 16 catches drift |
| 8 | AIDEV anchor density | sprinkle meaningless AIDEV-NOTEs to reach the band | the `> 10/KLOC` noise band flags over-anchoring |
| 9 | Overdue anchors | repeatedly pushing deadlines out | none — accepted; deadline moves stay visible in git history |
| 10 | Tests present | empty `tests/` dir | file-count ≥ 1 check; Dim 11 measures substance |
| 11 | Test/source ratio | trivial assert-true tests inflate test LOC | ratio `> 1.5` band flags absurd inflation; quality not judged — accepted |
| 12 | Structured logging | import `structlog`, keep using `print(` | mixed-usage grep flags both kinds present |
| 13 | .gitignore state | — (binary presence check, nothing to fake) | — |
| 14 | README quickstart | quickstart heading with no real content | heading-only check — accepted; semantic review (S2) verifies truthfulness |
| 15 | Language manifest | empty `pyproject.toml` | presence-only — accepted; `/dynamic-check` proves declared commands run |
| 16 | arch.yml ↔ disk | keep paths valid, let `role`/`stability` prose rot | symbol grep catches renamed `public_surface`; prose staleness accepted |
| 17 | GLOSSARY ↔ code | mention a dead term once in a comment to keep it "referenced" | frequency heuristic reduces but does not eliminate — accepted |
| 18 | Per-dir AGENTS.md staleness | `touch`/trivial-edit AGENTS.md without updating content | mtime-based — accepted; S1 judges content |
| 19 | CHANGELOG ↔ version | bump the heading with an empty entry body | heading match only — accepted |
| 20 | README slash-refs | delete the docs instead of fixing the refs | fewer artifacts lowers Dims 1–7 instead |
| 21 | CI config | workflow file with no jobs | push/PR-trigger grep; residual risk accepted |
| 22 | .env.example | empty example file | requires ≥ 1 `KEY=`-shaped line |
| 23 | Reproducible env | stale lockfile nobody regenerates | none — accepted (lockfile freshness is out of scope) |
| 24 | Secret guardrails | adopting the `claude-leverage:` marker without installing hooks | marker caps at ⚠️ (ADR 0012); ✅ needs a repo-visible scanner config |

Three systemic notes:

- **`/dynamic-check` can be gamed by curation** — declaring only the
  commands that pass. Countered by the semantic review (S1/S2), which
  judges *coverage*: docs that omit the obvious build/test story get
  flagged for that instead.

- **The score divisor is honest by construction** — N/A dims leave the
  divisor, so you cannot raise the score by making dimensions inapplicable.
- **The levels layer gates instead of averaging** (ADR 0012), so a fatal
  gap in one group cannot be washed out by polish elsewhere.
