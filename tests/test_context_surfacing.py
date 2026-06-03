"""Unit tests for scripts/build-context-map.py and behavioral tests for
scripts/hooks/context-surface.sh.

Builder tests are pure stdlib pytest. Hook tests use the same subprocess
pattern as tests/test_hook_behavior.py — driving the shell script with
crafted stdin JSON in a tmp working dir, asserting on stdout/stderr/exit.
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
BUILDER = REPO_ROOT / "scripts" / "build-context-map.py"
HOOK = REPO_ROOT / "scripts" / "hooks" / "context-surface.sh"

BASH = shutil.which("bash")
PYTHON = sys.executable

hook_pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="bash not on PATH — hook behavior tests need a POSIX shell",
)


# ---------------------------------------------------------------------------
# Builder tests (no shell dependency)
# ---------------------------------------------------------------------------


def _init_repo_with_files(tmp_path: Path, files: dict[str, str]) -> None:
    """Initialize a git repo and stage all named files. Files must be in
    `git ls-files` for the builder to find them."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)


def _run_builder(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(BUILDER), *args],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_builder_writes_valid_manifest_on_empty_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    result = _run_builder(tmp_path)
    assert result.returncode == 0, f"builder exit {result.returncode}; stderr={result.stderr!r}"

    manifest_path = tmp_path / ".claude-leverage-context-map.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["_meta"]["schema_version"] == 1
    assert manifest["_meta"]["builder_version"] == "1.9.0"
    assert manifest["_meta"]["generator"] == "scripts/build-context-map.py"
    assert manifest["files"] == {}
    assert manifest["_meta"]["anchor_count"] == 0
    assert manifest["_meta"]["file_count"] == 0


def test_builder_extracts_aidev_note(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "src/api.py": (
            "def query(params):\n"
            "    # AIDEV-NOTE: never include 'limit' key — CH 25.4 LIMIT override bug\n"
            "    return run(params)\n"
        ),
    })

    result = _run_builder(tmp_path, "--quiet")
    assert result.returncode == 0, result.stderr

    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert "src/api.py" in manifest["files"], manifest["files"]
    entry = manifest["files"]["src/api.py"]
    assert len(entry["anchors_in_file"]) == 1
    a = entry["anchors_in_file"][0]
    assert a["line"] == 2
    assert a["type"] == "AIDEV-NOTE"
    assert "limit" in a["text"]
    assert "CH 25.4" in a["text"]
    assert manifest["_meta"]["anchor_count"] == 1


def test_builder_extracts_multiple_anchor_types(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "src/foo.py": (
            "# AIDEV-NOTE: load-bearing invariant\n"
            "# AIDEV-TODO(by: 2026-08-01): migrate to webhooks\n"
            "# AIDEV-QUESTION(by: 2026-07-15): is encoding always UTF-8?\n"
            "x = 1\n"
        ),
    })

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    anchors = manifest["files"]["src/foo.py"]["anchors_in_file"]
    assert len(anchors) == 3
    assert [a["type"] for a in anchors] == ["AIDEV-NOTE", "AIDEV-TODO", "AIDEV-QUESTION"]
    assert anchors[1].get("deadline") == "2026-08-01"
    assert anchors[2].get("deadline") == "2026-07-15"


def test_builder_populates_anchors_in_dir_from_siblings(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "src/db/reader.py": "# AIDEV-NOTE: never use 'limit' as a param key\n",
        "src/db/writer.py": "# AIDEV-NOTE: all columns required in row dict\n",
        "src/api.py":      "# AIDEV-NOTE: routes are grouped by tag\n",
    })

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())

    reader = manifest["files"]["src/db/reader.py"]
    assert len(reader["anchors_in_dir"]) == 1
    sibling = reader["anchors_in_dir"][0]
    assert sibling["file"] == "src/db/writer.py"
    assert "row dict" in sibling["text"]

    api = manifest["files"]["src/api.py"]
    assert api["anchors_in_dir"] == []


def test_builder_walks_agents_md_chain(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "AGENTS.md":         "# top-level\n",
        "src/AGENTS.md":     "# src-level\n",
        "src/db/reader.py":  "# AIDEV-NOTE: x\n",
        # no src/db/AGENTS.md — should be skipped
    })

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    entry = manifest["files"]["src/db/reader.py"]
    assert entry["agents_md"] == ["src/AGENTS.md", "AGENTS.md"]


def test_builder_skips_files_without_anchors(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "AGENTS.md":          "# top\n",
        "src/no_anchors.py":  "x = 1\n",
    })

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"] == {}


def test_builder_cross_refs_adrs(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "src/db/reader.py": "# AIDEV-NOTE: x\n",
        "docs/adr/0001-clickhouse.md": (
            "# 0001 ClickHouse as warehouse\n\n"
            "Affects `src/db/reader.py` and `src/db/writer.py`.\n"
        ),
        "docs/adr/0002-unrelated.md": "# 0002 — not relevant\n",
    })

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"]["src/db/reader.py"]["adrs"] == [
        "docs/adr/0001-clickhouse.md"
    ]


def test_builder_adr_word_boundary_rejects_extension_continuation(tmp_path: Path) -> None:
    """ADR mentions `src/api.pyc` should NOT match `src/api.py`."""
    _init_repo_with_files(tmp_path, {
        "src/api.py": "# AIDEV-NOTE: x\n",
        "docs/adr/0001-foo.md": "see src/api.pyc for cached bytecode example\n",
    })
    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"]["src/api.py"]["adrs"] == []


def test_builder_skips_binary_files(tmp_path: Path) -> None:
    """A binary file (NUL byte) that happens to contain AIDEV-NOTE bytes
    must NOT appear in the manifest."""
    payload = b"PNG\x00data\nAIDEV-NOTE: should be ignored\n"
    _init_repo_with_files(tmp_path, {"assets/image.bin": payload})

    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert manifest["files"] == {}


def test_builder_check_mode_exits_1_on_drift(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {"src/x.py": "# AIDEV-NOTE: hi\n"})
    _run_builder(tmp_path, "--quiet")

    (tmp_path / "src/x.py").write_text("# AIDEV-NOTE: changed!\n", encoding="utf-8")
    result = _run_builder(tmp_path, "--check")
    assert result.returncode == 1, f"expected drift exit 1, got {result.returncode}"
    assert "DRIFT" in result.stderr


def test_builder_check_mode_passes_after_rebuild(tmp_path: Path) -> None:
    """Immediately after a rebuild, --check must pass. Regression for the
    pure-timestamp-only-changed false-positive (handled by _strip_generated_at)."""
    _init_repo_with_files(tmp_path, {"src/x.py": "# AIDEV-NOTE: hi\n"})
    _run_builder(tmp_path, "--quiet")
    # rebuild — generated_at differs but content is identical
    _run_builder(tmp_path, "--quiet")
    result = _run_builder(tmp_path, "--check", "--quiet")
    assert result.returncode == 0, f"--check should pass post-rebuild; stderr={result.stderr!r}"


def test_builder_requires_comment_context_for_anchor(tmp_path: Path) -> None:
    """AIDEV-NOTE inside a string literal must NOT be extracted as a real
    anchor. Real comment lines (Python #, JS //, etc.) must be extracted."""
    _init_repo_with_files(tmp_path, {
        # Real anchors (in comments) — should be extracted
        "src/python_comment.py": "# AIDEV-NOTE: real python anchor\nx = 1\n",
        "src/js_comment.js":     "// AIDEV-NOTE: real js anchor\n",
        "src/sql_comment.sql":   "-- AIDEV-NOTE: real sql anchor\n",
        # Fake anchors (in string literals / prose) — must be rejected
        "src/python_string.py": 'data = {"key": "# AIDEV-NOTE: not real\\n"}\n',
        "src/python_docstring.py": '"""AIDEV-NOTE: docstring, not a comment."""\n',
        "src/prose.md":         "Discussion of `AIDEV-NOTE: example` style anchors.\n",
    })
    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())

    assert "src/python_comment.py" in manifest["files"]
    assert "src/js_comment.js" in manifest["files"]
    assert "src/sql_comment.sql" in manifest["files"]
    assert "src/python_string.py" not in manifest["files"], \
        "string-literal AIDEV-NOTE must not be extracted"
    assert "src/python_docstring.py" not in manifest["files"], \
        "docstring AIDEV-NOTE must not be extracted (use # comment style)"
    assert "src/prose.md" not in manifest["files"], \
        "inline-backtick AIDEV-NOTE in markdown prose must not be extracted"


def test_builder_skips_its_own_manifest(tmp_path: Path) -> None:
    """The manifest JSON contains the literal `AIDEV-NOTE` substring
    inside text values. Without explicit self-skip, a second build would
    add the manifest itself as a tracked file with bogus anchors and
    cause perpetual drift on every rebuild."""
    _init_repo_with_files(tmp_path, {"src/x.py": "# AIDEV-NOTE: real anchor\n"})
    _run_builder(tmp_path, "--quiet")
    # Add the manifest to git so it's tracked
    subprocess.run(["git", "-C", str(tmp_path), "add",
                    ".claude-leverage-context-map.json"], check=True)
    # Second run must NOT include the manifest in `files`
    _run_builder(tmp_path, "--quiet")
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text())
    assert ".claude-leverage-context-map.json" not in manifest["files"]


def test_builder_writes_atomically(tmp_path: Path) -> None:
    """After a successful run, no leftover .tmp file should remain at the
    target location. (Confirms _atomic_write cleaned up via os.replace.)"""
    _init_repo_with_files(tmp_path, {"src/x.py": "# AIDEV-NOTE: hi\n"})
    _run_builder(tmp_path, "--quiet")
    assert (tmp_path / ".claude-leverage-context-map.json").exists()
    assert not (tmp_path / ".claude-leverage-context-map.json.tmp").exists()


# ---------------------------------------------------------------------------
# Hook behavioral tests (subprocess against the shell script)
# ---------------------------------------------------------------------------


def _read_payload(file_path: str) -> dict:
    return {"tool_name": "Read", "tool_input": {"file_path": file_path}}


def _run_hook(stdin_payload: dict, *, cwd: Path, extra_env: dict | None = None,
              timeout: int = 10) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("XDG_STATE_HOME", None)
    # Don't inherit user's verbose / disable settings — tests set them explicitly.
    env.pop("CLAUDE_LEVERAGE_CTX_VERBOSE", None)
    env.pop("CLAUDE_LEVERAGE_CTX_DISABLE", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=timeout,
    )


def _make_manifest(files_map: dict) -> dict:
    return {
        "_meta": {
            "schema_version": 1,
            "builder_version": "1.8.0",
            "generated_at": "2026-05-26T00:00:00+00:00",
            "generator": "scripts/build-context-map.py",
            "file_count": len(files_map),
            "anchor_count": sum(len(v.get("anchors_in_file", [])) for v in files_map.values()),
            "repo_root": ".",
        },
        "files": files_map,
    }


def _seed_manifest(repo: Path, files_map: dict) -> None:
    (repo / ".claude-leverage-context-map.json").write_text(
        json.dumps(_make_manifest(files_map), indent=2), encoding="utf-8",
    )


@hook_pytestmark
def test_hook_silent_when_manifest_missing(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"expected silent, got {result.stdout!r}"


@hook_pytestmark
def test_hook_emits_context_for_file_in_manifest(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/db/reader.py": {
            "anchors_in_file": [
                {"line": 29, "type": "AIDEV-NOTE", "text": "never use 'limit' as a param key"}
            ],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })

    payload = _read_payload(str(tmp_path / "src/db/reader.py"))
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), f"expected JSON, got {result.stdout!r}"
    out = json.loads(result.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    ctx = hso["additionalContext"]
    assert "[claude-leverage:context-surface]" in ctx
    assert "src/db/reader.py" in ctx
    assert "L29" in ctx
    assert "limit" in ctx


@hook_pytestmark
@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
def test_hook_fires_for_edit_family_tools(tmp_path: Path, tool: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "watch out"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    payload = {"tool_name": tool, "tool_input": {"file_path": str(tmp_path / "src/x.py")}}
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    assert "watch out" in result.stdout


@hook_pytestmark
@pytest.mark.parametrize("tool", ["Bash", "Grep", "Glob", "Agent", "Skill"])
def test_hook_skips_non_file_tools(tmp_path: Path, tool: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "x"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    payload = {"tool_name": tool, "tool_input": {"command": "ls"}}
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@hook_pytestmark
def test_hook_normalizes_windows_backslash_path(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/db/reader.py": {
            "anchors_in_file": [{"line": 29, "type": "AIDEV-NOTE", "text": "limit trap"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })

    win_path = str(tmp_path).replace("/", "\\") + r"\src\db\reader.py"
    payload = {"tool_name": "Read", "tool_input": {"file_path": win_path}}
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip(), f"expected emission, got {result.stdout!r}"
    assert "limit trap" in result.stdout


@hook_pytestmark
def test_hook_silent_on_corrupt_manifest(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    (tmp_path / ".claude-leverage-context-map.json").write_text(
        "{ this is not valid json", encoding="utf-8",
    )
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


@hook_pytestmark
def test_hook_silent_on_truncated_manifest(tmp_path: Path) -> None:
    """Manifest exists but was truncated mid-array — graceful no-op."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    (tmp_path / ".claude-leverage-context-map.json").write_text(
        '{"_meta":{"schema_version":1},"files":{"src/x.py":{"anchors_in_file":[{"line":1,',
        encoding="utf-8",
    )
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


@hook_pytestmark
def test_hook_silent_when_all_arrays_empty(tmp_path: Path) -> None:
    """File in manifest with empty arrays → no marker-only emission."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [],
            "anchors_in_dir": [],
            "agents_md": [],
            "adrs": [],
        },
    })
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"expected silent, got {result.stdout!r}"


@hook_pytestmark
def test_hook_opt_out_via_env_var(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "important"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    result = _run_hook(
        _read_payload(str(tmp_path / "src/x.py")),
        cwd=tmp_path,
        extra_env={"CLAUDE_LEVERAGE_CTX_DISABLE": "1"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@hook_pytestmark
def test_hook_truncates_at_cap(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    big = [{"line": i, "type": "AIDEV-NOTE", "text": "x" * 200} for i in range(1, 101)]
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": big,
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 4096 + 100, f"context size {len(ctx)} exceeds budget"
    assert "truncated" in ctx


@hook_pytestmark
def test_hook_verbose_mode_includes_agents_md_and_adrs(tmp_path: Path) -> None:
    """Default: anchors only. Verbose: agents_md + adrs also surface."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    _seed_manifest(tmp_path, {
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "stay sharp"}],
            "anchors_in_dir": [],
            "agents_md": ["src/AGENTS.md", "AGENTS.md"],
            "adrs": ["docs/adr/0001-foo.md"],
        },
    })
    payload = _read_payload(str(tmp_path / "src/x.py"))

    # Default (verbose off): anchors only
    result = _run_hook(payload, cwd=tmp_path)
    ctx_default = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "stay sharp" in ctx_default
    assert "src/AGENTS.md" not in ctx_default
    assert "0001-foo.md" not in ctx_default

    # Verbose on
    result = _run_hook(payload, cwd=tmp_path,
                       extra_env={"CLAUDE_LEVERAGE_CTX_VERBOSE": "1"})
    ctx_verbose = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "src/AGENTS.md" in ctx_verbose
    assert "docs/adr/0001-foo.md" in ctx_verbose


@hook_pytestmark
def test_hook_skips_on_schema_version_mismatch(tmp_path: Path) -> None:
    """Future schema_version → graceful no-op, never crash."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    m = _make_manifest({
        "src/x.py": {
            "anchors_in_file": [{"line": 1, "type": "AIDEV-NOTE", "text": "x"}],
            "anchors_in_dir": [], "agents_md": [], "adrs": [],
        },
    })
    m["_meta"]["schema_version"] = 99
    (tmp_path / ".claude-leverage-context-map.json").write_text(
        json.dumps(m, indent=2), encoding="utf-8",
    )
    result = _run_hook(_read_payload(str(tmp_path / "src/x.py")), cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# conventions.yml folded into _meta.conventions (builder v1.9.0)
# ---------------------------------------------------------------------------


def test_builder_includes_meta_conventions_when_present(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {
        "conventions.yml": (
            "naming:\n  casing:\n    functions: snake_case\n"
            "  vague_denylist:\n    - data\n"
            "structure:\n  roots:\n    \"scripts/\": \"scripts root\"\n"
            "consistency:\n  - \"Hooks must fail-open.\"\n"
        ),
        "scripts/x.py": "# AIDEV-NOTE: anchor so the file lands in the manifest\nx = 1\n",
    })
    _run_builder(tmp_path)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text(encoding="utf-8"))
    conv = manifest["_meta"]["conventions"]
    assert conv["casing"]["functions"] == "snake_case"
    assert "data" in conv["vague_denylist"]
    assert conv["structure_roots"]["scripts/"] == "scripts root"
    assert conv["consistency"] == ["Hooks must fail-open."]


def test_builder_omits_conventions_when_absent(tmp_path: Path) -> None:
    _init_repo_with_files(tmp_path, {"scripts/x.py": "# AIDEV-NOTE: a\nx = 1\n"})
    _run_builder(tmp_path)
    manifest = json.loads((tmp_path / ".claude-leverage-context-map.json").read_text(encoding="utf-8"))
    assert "conventions" not in manifest["_meta"]
