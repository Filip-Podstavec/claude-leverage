---
description: Diagnose a flaky test by running it N times. Delegates to flaky-test-isolator subagent — N runs, signature-grouped failures, stability report. Does NOT fix the test.
allowed-tools: Bash(ls:*), Bash(test:*), Bash(pwd:*)
argument-hint: "<test-path-or-name> [--runs N=10] [--timeout SECONDS=60]"
---

## Project framework hints (computed before delegation)

CWD: !`pwd`
Has package.json: !`test -f package.json && echo "yes" || echo "no"`
Has pyproject.toml: !`test -f pyproject.toml && echo "yes" || echo "no"`
Has pytest.ini: !`test -f pytest.ini && echo "yes" || echo "no"`
Has setup.cfg: !`test -f setup.cfg && echo "yes" || echo "no"`
Has go.mod: !`test -f go.mod && echo "yes" || echo "no"`
Has Cargo.toml: !`test -f Cargo.toml && echo "yes" || echo "no"`
Has Gemfile: !`test -f Gemfile && echo "yes" || echo "no"`

## Your role

You are routing a flaky-test diagnosis. Your job is pre-flight validation and delegation. You do NOT run the tests yourself. The `flaky-test-isolator` subagent (Sonnet) owns execution.

## Defaults and caps

| Arg | Default | Hard cap | Why |
|-----|---------|----------|-----|
| `--runs` | 10 | 50 | 10 runs is usually enough signal; 50 prevents runaway cost on slow suites |
| `--timeout` | 60s per run | 300s per run | 5 min per single test is generous; total budget is enforced by the subagent (30 min wall-clock) |

## Pre-flight workflow

1. **Parse `$ARGUMENTS`:**
   - First positional argument: the test target (file path, test name, or framework-specific pattern).
   - `--runs N`: optional, integer.
   - `--timeout SECONDS`: optional, integer.

2. **Validate the target.** If `$ARGUMENTS` is empty or the first positional looks like a flag, STOP and ask the user for the test target. Do NOT delegate without a target — the subagent would have to guess and waste a delegation.

3. **Apply caps silently.**
   - If `--runs` > 50, set to 50 and tell the user: "Capped --runs to 50."
   - If `--timeout` > 300, set to 300 and tell the user: "Capped --timeout to 300 seconds per run."
   - If `--runs` < 1 or `--timeout` < 1, reject and ask the user for a valid value.

4. **Warn on missing framework hint.** If all of the `Has *` lines above are "no", warn the user: "No common test manifest detected in this directory. The subagent will ask if it can't infer the framework." Then still delegate.

5. **Delegate** to the `flaky-test-isolator` subagent with a self-contained prompt that includes:
   - The exact test target string
   - N (post-cap)
   - Timeout (post-cap)
   - The framework-hint lines from the context block above (so the subagent does not re-discover what you already know)

6. **Relay the subagent's report verbatim.** The structured report IS the deliverable. Do NOT paraphrase, summarize, re-format, or pre-emptively interpret. After relaying, ask the user one question: "Want to attempt a fix, re-run with higher N, or stop here?"

## Hard rules

- Never run the tests yourself from this command. The subagent has Bash; you don't need it here for execution.
- Never apply or propose fixes inside this command. Fixes happen in a separate main-session step after the user decides.
- Never delegate without the test target argument. Asking the user costs one message; a wasted delegation costs an entire subagent invocation.
- If the subagent reports `broken` (<20% pass rate), do not surface this as "just flaky" — the test is failing the majority of the time, which is a different problem.

## When NOT to use this command

- Single-run failures where you have a stack trace already → read the trace inline; the `test-runner` subagent that previously paired with this command was retired in v1.0.0 (see `bench/archive-token-savings-thesis/agents/test-runner.md`).
- "All my tests are flaky" → diagnose framework/env first inline; this command is for one specific test that intermittently fails.
- CI debugging where you don't have local repro → this command runs locally; for CI flakiness you need CI logs first.
