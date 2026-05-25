"""Behavioral tests for shipped hook scripts.

Drives each hook with crafted stdin JSON in a tmp working dir and asserts
on the externally observable contract (stdout JSON for SessionStart,
stderr nudges for PostToolUse/Stop, exit code). Catches the class of
bugs where an ignore pattern silently matches the wrong thing — the
1.4.0 field-feedback report identified four such bugs.

Stdlib-only (subprocess). Skips cleanly when bash is not on PATH so the
suite still runs on a stripped-down Windows box without Git Bash.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "scripts" / "hooks"
AI_FIRST_NUDGE = HOOKS_DIR / "ai-first-nudge.sh"
STACK_FRESHNESS = HOOKS_DIR / "stack-freshness.sh"
BARE_REPO_NUDGE = HOOKS_DIR / "bare-repo-nudge.sh"
SECURITY_NUDGE = HOOKS_DIR / "security-nudge.sh"
BLOCK_DANGEROUS_GIT = HOOKS_DIR / "block-dangerous-git.sh"


BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="bash not on PATH — hook behavior tests need a POSIX shell",
)


def _run_hook(
    script: Path,
    stdin_payload: dict | str,
    *,
    cwd: Path,
    state_dir: Path,
    extra_env: dict[str, str] | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Invoke a hook script with given stdin and isolated state dir."""
    if isinstance(stdin_payload, dict):
        stdin_payload = json.dumps(stdin_payload)
    env = os.environ.copy()
    env["CLAUDE_LEVERAGE_STATE_DIR"] = str(state_dir)
    # Strip XDG_STATE_HOME so the hook's fallback chain lands on our override
    # rather than a leftover $HOME/.local/state/claude-leverage from the dev box.
    env.pop("XDG_STATE_HOME", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [BASH, str(script)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=timeout,
    )


def _ai_first_nudge_payload(file_path: str, *, loc: int = 60) -> dict:
    """Build a Write-tool payload with `loc` non-blank lines of nondescript code,
    no AIDEV anchor — should trigger the missing-anchor nudge unless ignored."""
    body = "\n".join(f"line_{i} = {i}" for i in range(loc))
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": body},
    }


# ---------------------------------------------------------------------------
# ai-first-nudge: basename vs path ignore patterns (#1)
# ---------------------------------------------------------------------------


def test_ai_first_nudge_fires_when_dir_name_contains_test(tmp_path: Path) -> None:
    """A directory called slevomat_test_api/ must NOT make the hook treat
    files inside it as test files. Only basename test_*.py / *_test.py
    should be ignored as tests. Regression for v1.4.0 field-feedback #1."""
    project = tmp_path / "slevomat_test_api"
    project.mkdir()
    target = project / "discover.py"
    payload = _ai_first_nudge_payload(str(target))

    result = _run_hook(
        AI_FIRST_NUDGE,
        payload,
        cwd=tmp_path,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    assert "LOC of net-new code" in result.stderr, (
        f"Expected nudge for production file in test-named dir; got stderr={result.stderr!r}"
    )


def test_ai_first_nudge_ignores_real_test_file_basename(tmp_path: Path) -> None:
    """test_foo.py and foo_test.py basenames must still be ignored — the fix
    must not break the legitimate ignore."""
    project = tmp_path / "src"
    project.mkdir()
    target = project / "test_discover.py"
    payload = _ai_first_nudge_payload(str(target))

    result = _run_hook(
        AI_FIRST_NUDGE,
        payload,
        cwd=tmp_path,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    assert "LOC of net-new code" not in result.stderr, (
        f"test_discover.py is a test file; should be ignored. stderr={result.stderr!r}"
    )


def test_ai_first_nudge_ignores_under_tests_dir(tmp_path: Path) -> None:
    project = tmp_path / "src" / "tests"
    project.mkdir(parents=True)
    target = project / "fixture.py"
    payload = _ai_first_nudge_payload(str(target))

    result = _run_hook(
        AI_FIRST_NUDGE,
        payload,
        cwd=tmp_path,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    assert "LOC of net-new code" not in result.stderr


# ---------------------------------------------------------------------------
# ai-first-nudge: Windows backslash path normalization (#2)
# ---------------------------------------------------------------------------


def test_ai_first_nudge_normalizes_windows_backslashes(tmp_path: Path) -> None:
    """A Windows-style backslash path inside node_modules must be ignored.
    Without normalization the */node_modules/* pattern misses the
    backslash separators. Regression for v1.4.0 field-feedback #2."""
    # NOTE: file does not need to exist — hook reads file_path from stdin only.
    win_path = r"C:\Users\foo\my-project\node_modules\react\index.js"
    payload = _ai_first_nudge_payload(win_path)

    result = _run_hook(
        AI_FIRST_NUDGE,
        payload,
        cwd=tmp_path,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    assert "LOC of net-new code" not in result.stderr, (
        f"node_modules path with backslashes should be ignored; got stderr={result.stderr!r}"
    )


def test_ai_first_nudge_normalizes_backslash_tests_dir(tmp_path: Path) -> None:
    """Same normalization invariant for tests dir."""
    win_path = r"C:\Users\foo\my-project\tests\unit\test_helpers.py"
    payload = _ai_first_nudge_payload(win_path)

    result = _run_hook(
        AI_FIRST_NUDGE,
        payload,
        cwd=tmp_path,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    assert "LOC of net-new code" not in result.stderr


# ---------------------------------------------------------------------------
# stack-freshness: additionalContext JSON migration (#3)
# ---------------------------------------------------------------------------


def _setup_state_with_last_check(state_dir: Path, epoch: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ".last-stack-check").write_text(str(epoch), encoding="utf-8")


def _parse_session_start_json(stdout: str) -> dict:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout, got empty"
    return json.loads(stdout)


def test_stack_freshness_stale_emits_additional_context_json(tmp_path: Path) -> None:
    """When the stored timestamp is older than threshold, the SessionStart
    hook must emit a JSON object on STDOUT containing
    hookSpecificOutput.additionalContext (per Claude Code SessionStart
    spec), so the model actually sees it. Stderr alone is invisible to
    the model context window. Regression for v1.4.0 field-feedback #3."""
    state_dir = tmp_path / "_state"
    very_old = 1_000_000_000  # year 2001
    _setup_state_with_last_check(state_dir, very_old)

    result = _run_hook(
        STACK_FRESHNESS,
        "",
        cwd=tmp_path,
        state_dir=state_dir,
        extra_env={"CLAUDE_LEVERAGE_FRESHNESS_DAYS": "30"},
    )

    assert result.returncode == 0, result.stderr
    payload = _parse_session_start_json(result.stdout)
    hso = payload.get("hookSpecificOutput")
    assert isinstance(hso, dict), f"missing hookSpecificOutput, got {payload!r}"
    assert hso.get("hookEventName") == "SessionStart"
    ctx = hso.get("additionalContext", "")
    assert "stack" in ctx.lower(), f"additionalContext should mention stack, got {ctx!r}"
    assert "/stack-check" in ctx, f"additionalContext should reference /stack-check"


def test_stack_freshness_fresh_is_silent(tmp_path: Path) -> None:
    """Within threshold → no JSON, no stderr, exit 0."""
    state_dir = tmp_path / "_state"
    # Use the hook's own clock by writing "now-ish" into the file
    now_epoch = int(subprocess.check_output(
        [BASH, "-c", "date +%s"], text=True
    ).strip())
    _setup_state_with_last_check(state_dir, now_epoch)

    result = _run_hook(
        STACK_FRESHNESS,
        "",
        cwd=tmp_path,
        state_dir=state_dir,
        extra_env={"CLAUDE_LEVERAGE_FRESHNESS_DAYS": "30"},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", f"fresh stack should be silent, got stdout={result.stdout!r}"


def test_stack_freshness_never_checked_emits_json(tmp_path: Path) -> None:
    """No state file at all → emit additionalContext suggesting first run."""
    state_dir = tmp_path / "_state"
    state_dir.mkdir()  # exists but no .last-stack-check inside

    result = _run_hook(
        STACK_FRESHNESS,
        "",
        cwd=tmp_path,
        state_dir=state_dir,
    )

    assert result.returncode == 0
    payload = _parse_session_start_json(result.stdout)
    hso = payload.get("hookSpecificOutput", {})
    ctx = hso.get("additionalContext", "")
    assert "never" in ctx.lower() or "stack" in ctx.lower()


def test_stack_freshness_disabled_is_silent(tmp_path: Path) -> None:
    """CLAUDE_LEVERAGE_FRESHNESS_DAYS=0 disables entirely."""
    state_dir = tmp_path / "_state"
    _setup_state_with_last_check(state_dir, 1_000_000_000)

    result = _run_hook(
        STACK_FRESHNESS,
        "",
        cwd=tmp_path,
        state_dir=state_dir,
        extra_env={"CLAUDE_LEVERAGE_FRESHNESS_DAYS": "0"},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# bare-repo-nudge: SessionStart nudge for non-git cwd (#4 + #6)
# ---------------------------------------------------------------------------


def test_bare_repo_nudge_fires_in_non_git_dir(tmp_path: Path) -> None:
    """A SessionStart in a non-git cwd should emit additionalContext
    suggesting `git init` + /init-repo, so the model proactively sets up
    guardrails instead of writing token-handling code in a bare dir.
    Regression for v1.4.0 field-feedback #4 + #6."""
    project = tmp_path / "fresh-project"
    project.mkdir()
    # No .git, no AGENTS.md — bare project.

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    payload = _parse_session_start_json(result.stdout)
    hso = payload.get("hookSpecificOutput", {})
    ctx = hso.get("additionalContext", "")
    assert "git" in ctx.lower() and ("init" in ctx.lower() or "init-repo" in ctx)


def test_bare_repo_nudge_silent_inside_git_repo(tmp_path: Path) -> None:
    project = tmp_path / "real-project"
    project.mkdir()
    subprocess.run(
        ["git", "init", "-q"], cwd=str(project), check=True
    )

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"hook should be silent inside a git repo, got stdout={result.stdout!r}"
    )


def test_bare_repo_nudge_silent_in_home_directory(tmp_path: Path) -> None:
    """Don't nudge when cwd is $HOME — user is just opening a terminal,
    not starting project work."""
    fake_home = tmp_path / "home_user"
    fake_home.mkdir()

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=fake_home,
        state_dir=tmp_path / "_state",
        extra_env={"HOME": str(fake_home), "USERPROFILE": str(fake_home)},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"hook should be silent in $HOME, got stdout={result.stdout!r}"
    )


def test_bare_repo_nudge_fires_in_git_project_without_agents_md(tmp_path: Path) -> None:
    """Branch B (v1.4.3+): cwd IS a git repo, has a project marker
    (pyproject.toml / package.json / Cargo.toml / etc.), but no
    AGENTS.md or CLAUDE.md at the repo root → the model has zero
    project-specific conventions loaded, so claude-leverage's value
    proposition is mostly inert. Nudge toward /init-repo to bootstrap."""
    project = tmp_path / "py-project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    (project / "pyproject.toml").write_text("[project]\nname = \"x\"\n", encoding="utf-8")

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0, result.stderr
    payload = _parse_session_start_json(result.stdout)
    ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "/init-repo" in ctx
    assert "AGENTS.md" in ctx, f"branch-B nudge should mention AGENTS.md, got {ctx!r}"


def test_bare_repo_nudge_silent_when_agents_md_present(tmp_path: Path) -> None:
    """Project has AGENTS.md → conventions loaded → no nudge."""
    project = tmp_path / "configured-project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    (project / "pyproject.toml").write_text("[project]\nname = \"x\"\n", encoding="utf-8")
    (project / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"AGENTS.md present should suppress nudge, got {result.stdout!r}"
    )


def test_bare_repo_nudge_silent_when_only_claude_md_present(tmp_path: Path) -> None:
    """CLAUDE.md (typically `@AGENTS.md` import) is enough for the model
    to have project context — no nudge."""
    project = tmp_path / "claude-only-project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    (project / "package.json").write_text("{}", encoding="utf-8")
    (project / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_bare_repo_nudge_silent_in_git_repo_without_project_marker(tmp_path: Path) -> None:
    """An empty git repo with no recognizable project marker (no
    package.json / pyproject.toml / Cargo.toml / etc.) is probably a
    scratch/docs repo — branch B should NOT fire even though AGENTS.md
    is missing. Avoids nudging on every personal notes repo."""
    project = tmp_path / "scratch-repo"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    # No project marker file written.

    result = _run_hook(
        BARE_REPO_NUDGE,
        "",
        cwd=project,
        state_dir=tmp_path / "_state",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"no project marker → should be silent, got {result.stdout!r}"
    )


def test_bare_repo_nudge_rate_limit_per_day(tmp_path: Path) -> None:
    """Second invocation in the same dir on the same day must be silent."""
    project = tmp_path / "fresh-project"
    project.mkdir()
    state_dir = tmp_path / "_state"

    first = _run_hook(BARE_REPO_NUDGE, "", cwd=project, state_dir=state_dir)
    assert first.returncode == 0
    assert first.stdout.strip(), "first call should emit JSON"

    second = _run_hook(BARE_REPO_NUDGE, "", cwd=project, state_dir=state_dir)
    assert second.returncode == 0
    assert second.stdout.strip() == "", (
        f"second call in same dir same day should be silent, got stdout={second.stdout!r}"
    )


# ---------------------------------------------------------------------------
# block-dangerous-git: quote-aware flag detection (#v1.4.5)
# ---------------------------------------------------------------------------
#
# v1.4.4 surfaced the false-positive: the hook stripped quotes wholesale
# before scanning for --force / --no-verify / --hard, so a commit message
# whose body mentioned those flags as prose tripped the detector. The
# v1.4.5 fix moves to quote-aware stripping: contents of '...' and "..."
# are removed (they're DATA, not command tokens) before pattern matching.
#
# These tests cover both directions: real attacks STILL block, prose in
# message bodies NO LONGER blocks.


def _bash_hook_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# --- Should ALLOW (false-positive fixes) ---


def test_block_dangerous_git_allows_force_substring_in_commit_message(tmp_path: Path) -> None:
    """`git commit -m "...--force..."` should NOT be blocked — `--force`
    is inside a quoted message body, not an actual flag. Pre-v1.4.5 the
    aggressive `tr -d` strip would treat it as if it were unquoted and
    co-occur with any later `git push` in the same shell command."""
    cmd = 'git commit -m "explain why --force is bad" && git push'
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}; stderr={result.stderr!r}"
    )


def test_block_dangerous_git_allows_force_in_heredoc_body(tmp_path: Path) -> None:
    """The exact shape that caught v1.4.4: a `git commit -m "$(cat <<'EOF'
    ... --force ... EOF)"` chained with a final `git push`. The heredoc
    body lives inside the outer "..." quote; quote-aware strip eats it."""
    cmd = (
        "git add . && git commit -m \"$(cat <<'EOF'\n"
        "chore: explain hooks reject --force, --no-verify, etc.\n"
        "EOF\n"
        ")\" && git push"
    )
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}; stderr={result.stderr!r}"
    )


def test_block_dangerous_git_allows_no_verify_substring_in_message(tmp_path: Path) -> None:
    cmd = 'git commit -m "the --no-verify flag bypasses hooks — never use it"'
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}; stderr={result.stderr!r}"
    )


def test_block_dangerous_git_allows_hard_reset_substring_in_message(tmp_path: Path) -> None:
    cmd = "git commit -m 'document that git reset --hard main is destructive'"
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}; stderr={result.stderr!r}"
    )


# --- Should BLOCK (real attacks; regression guard) ---


def test_block_dangerous_git_blocks_actual_force_push(tmp_path: Path) -> None:
    cmd = "git push --force origin main"
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 2, (
        f"expected block (exit 2), got {result.returncode}; stderr={result.stderr!r}"
    )
    assert "Force push" in result.stderr


def test_block_dangerous_git_blocks_force_push_short_option(tmp_path: Path) -> None:
    cmd = "git push -f origin main"
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 2, (
        f"expected block (exit 2), got {result.returncode}; stderr={result.stderr!r}"
    )


def test_block_dangerous_git_blocks_actual_no_verify(tmp_path: Path) -> None:
    cmd = 'git commit --no-verify -m "skip the hooks"'
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 2, (
        f"expected block (exit 2), got {result.returncode}; stderr={result.stderr!r}"
    )
    assert "--no-verify" in result.stderr


def test_block_dangerous_git_blocks_actual_hard_reset_main(tmp_path: Path) -> None:
    cmd = "git reset --hard origin/main"
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 2, (
        f"expected block (exit 2), got {result.returncode}; stderr={result.stderr!r}"
    )


def test_block_dangerous_git_blocks_backslash_escape_evasion(tmp_path: Path) -> None:
    """Backslash-escape evasion (`git push \\--force`) is in an UNQUOTED
    position; the backslash-strip step after quote-aware stripping must
    still reconstitute the flag and block it. Pre-v1.4.5 caught this; the
    v1.4.5 refactor must preserve it."""
    cmd = "git push \\--force origin main"
    result = _run_hook(BLOCK_DANGEROUS_GIT, _bash_hook_payload(cmd),
                       cwd=tmp_path, state_dir=tmp_path / "_state")
    assert result.returncode == 2, (
        f"backslash-escape evasion should still block; got exit {result.returncode}, "
        f"stderr={result.stderr!r}"
    )
