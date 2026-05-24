"""End-to-end validation of the shipped plugin manifest.

Catches the class of bugs where the manifest parses but references files
that don't exist — the kind of failure that only shows up after a user
runs `/plugin install` and gets a silent partial install. CI runs these
on every PR.

This test suite is intentionally stdlib-only — no PyYAML, no tomli. The
plugin manifest is JSON; SKILL.md frontmatter is the same YAML subset
the existing test_agent_command_frontmatter.py parses.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
CODEX_HOOKS_JSON = REPO_ROOT / ".codex" / "hooks.json"
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
CODEX_AGENTS_DIR = REPO_ROOT / ".codex" / "agents"


# ---------------------------------------------------------------------------
# Plugin / marketplace manifest
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_json_parses() -> None:
    data = _load_json(PLUGIN_JSON)
    assert isinstance(data, dict)


def test_marketplace_json_parses() -> None:
    data = _load_json(MARKETPLACE_JSON)
    assert isinstance(data, dict)


def test_plugin_json_required_fields() -> None:
    data = _load_json(PLUGIN_JSON)
    for field in ("name", "version", "description", "author", "license", "keywords"):
        assert field in data, f"plugin.json missing top-level field {field!r}"


def test_plugin_version_is_semver_like() -> None:
    """Not strict semver — just X.Y.Z with optional suffix."""
    v = _load_json(PLUGIN_JSON)["version"]
    assert re.match(r"^\d+\.\d+\.\d+", v), f"plugin.json version {v!r} doesn't look like semver"


def test_marketplace_has_plugin_entry() -> None:
    data = _load_json(MARKETPLACE_JSON)
    plugins = data.get("plugins", [])
    names = [p.get("name") for p in plugins if isinstance(p, dict)]
    assert "claude-leverage" in names, "marketplace.json has no entry for claude-leverage"


def test_marketplace_version_matches_plugin() -> None:
    """Same invariant as scripts/check_version_sync.py but inside pytest."""
    plugin_v = _load_json(PLUGIN_JSON)["version"]
    mkt = _load_json(MARKETPLACE_JSON)
    entries = [p for p in mkt["plugins"]
               if isinstance(p, dict) and p.get("name") == "claude-leverage"]
    assert len(entries) == 1, f"expected exactly 1 marketplace entry; got {len(entries)}"
    assert entries[0]["version"] == plugin_v, (
        f"version drift: plugin.json={plugin_v!r}, "
        f"marketplace.json={entries[0]['version']!r}"
    )


# ---------------------------------------------------------------------------
# Claude Code hooks config
# ---------------------------------------------------------------------------


CLAUDE_HOOK_PREFIX = "${CLAUDE_PLUGIN_ROOT}/"


def _all_hook_commands(data: dict) -> list[str]:
    """Collect every concrete `command` string from a hooks.json document.

    Filters out our `_comment` annotations and any empty entries.
    """
    out: list[str] = []
    for _event, blocks in data.get("hooks", {}).items():
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for hook in block.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command")
                if isinstance(cmd, str) and cmd:
                    out.append(cmd)
    return out


def test_hooks_json_parses() -> None:
    data = _load_json(HOOKS_JSON)
    assert isinstance(data, dict)


def test_hooks_json_paths_resolve() -> None:
    """Every Claude hook command must reference an existing executable script."""
    data = _load_json(HOOKS_JSON)
    cmds = _all_hook_commands(data)
    assert cmds, "hooks.json declared no commands — that's almost certainly wrong"
    for cmd in cmds:
        assert cmd.startswith(CLAUDE_HOOK_PREFIX), (
            f"hooks.json command {cmd!r} doesn't use ${{CLAUDE_PLUGIN_ROOT}} prefix"
        )
        rel = cmd[len(CLAUDE_HOOK_PREFIX):]
        # Strip any arguments after the script path.
        rel = rel.split()[0]
        resolved = REPO_ROOT / rel
        assert resolved.is_file(), (
            f"hooks.json references {cmd!r} but {resolved} doesn't exist"
        )


# ---------------------------------------------------------------------------
# Codex hooks template
# ---------------------------------------------------------------------------


CODEX_PLACEHOLDER = "__CLAUDE_LEVERAGE_DIR__/"


def test_codex_hooks_json_parses() -> None:
    data = _load_json(CODEX_HOOKS_JSON)
    assert isinstance(data, dict)


def test_codex_hooks_uses_placeholder() -> None:
    """Template must reference scripts via __CLAUDE_LEVERAGE_DIR__/ so the
    installer can substitute. Real absolute paths leaking in would mean
    a developer committed a resolved file by accident."""
    data = _load_json(CODEX_HOOKS_JSON)
    cmds = _all_hook_commands(data)
    assert cmds, ".codex/hooks.json declared no commands"
    for cmd in cmds:
        assert cmd.startswith(CODEX_PLACEHOLDER), (
            f".codex/hooks.json command {cmd!r} doesn't use the "
            f"__CLAUDE_LEVERAGE_DIR__ placeholder — did a resolved path "
            f"get committed?"
        )


def test_codex_hooks_paths_resolve_via_placeholder() -> None:
    """Substituting REPO_ROOT for the placeholder must point at existing files."""
    data = _load_json(CODEX_HOOKS_JSON)
    for cmd in _all_hook_commands(data):
        rel = cmd[len(CODEX_PLACEHOLDER):]
        rel = rel.split()[0]
        resolved = REPO_ROOT / rel
        assert resolved.is_file(), (
            f".codex/hooks.json references {cmd!r} (resolves to {resolved}) "
            f"which doesn't exist"
        )


def test_codex_hooks_match_claude_hooks_scripts() -> None:
    """The two hook configs should reference the same shell scripts. Mismatch
    means one tool gets a hook the other doesn't — almost always a bug."""
    claude_scripts = sorted(
        cmd[len(CLAUDE_HOOK_PREFIX):].split()[0]
        for cmd in _all_hook_commands(_load_json(HOOKS_JSON))
    )
    codex_scripts = sorted(
        cmd[len(CODEX_PLACEHOLDER):].split()[0]
        for cmd in _all_hook_commands(_load_json(CODEX_HOOKS_JSON))
    )
    assert claude_scripts == codex_scripts, (
        f"hook scripts diverge:\n"
        f"  Claude: {claude_scripts}\n"
        f"  Codex:  {codex_scripts}\n"
        f"If you intentionally want a hook only in one tool, "
        f"document why in the JSON _comment field."
    )


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def _skill_dirs() -> list[Path]:
    # Filter out non-skill scaffolding: pycache, dotted dirs (.git, .DS_Store
    # adjacent metadata), and underscored "private" dirs (a convention for
    # shared helpers that might land under skills/ later).
    return sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir()
        and d.name != "__pycache__"
        and not d.name.startswith(".")
        and not d.name.startswith("_")
    )


SKILL_DIRS = _skill_dirs()


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda d: d.name)
def test_skill_dir_has_skill_md(skill_dir: Path) -> None:
    """Every dir under skills/ must contain a SKILL.md — orphan dirs are
    invisible to the cross-tool installer and confuse contributors."""
    assert (skill_dir / "SKILL.md").is_file(), (
        f"skills/{skill_dir.name}/ has no SKILL.md — either add one or remove the dir"
    )


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda d: d.name)
def test_skill_frontmatter_has_required_fields(skill_dir: Path) -> None:
    """SKILL.md must declare `name` and `description` per agentskills.io spec."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        pytest.skip("paired check: see test_skill_dir_has_skill_md")
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill_md.relative_to(REPO_ROOT)}: missing frontmatter"
    try:
        end = text.index("\n---\n", 4)
    except ValueError:
        pytest.fail(f"{skill_md.relative_to(REPO_ROOT)}: unterminated frontmatter")
    fm = text[4:end]
    # Allow either inline (`name: foo`) or YAML-multiline (`name: |\n  foo`).
    assert re.search(r"^name:\s*\S", fm, re.MULTILINE), (
        f"{skill_md.relative_to(REPO_ROOT)}: missing 'name:' in frontmatter"
    )
    assert re.search(r"^description:", fm, re.MULTILINE), (
        f"{skill_md.relative_to(REPO_ROOT)}: missing 'description:' in frontmatter"
    )


# ---------------------------------------------------------------------------
# Statusline + installers
# ---------------------------------------------------------------------------


def test_statusline_script_exists() -> None:
    assert (REPO_ROOT / "statusline" / "statusline-command.sh").is_file()


def test_install_codex_scripts_exist() -> None:
    assert (REPO_ROOT / "scripts" / "install-codex.sh").is_file()
    assert (REPO_ROOT / "scripts" / "install-codex.ps1").is_file()


def test_gen_codex_agents_script_exists() -> None:
    assert (REPO_ROOT / "scripts" / "gen-codex-agents.py").is_file()


# ---------------------------------------------------------------------------
# Stack manifest
# ---------------------------------------------------------------------------


def test_stack_toml_exists() -> None:
    """stack.toml is what /stack-check reads. If missing, the freshness
    skill is useless."""
    assert (REPO_ROOT / "stack.toml").is_file()


def test_stack_toml_no_template_placeholders() -> None:
    """Easy footgun: forgetting to fill in a template field. Search for
    obvious placeholders that shouldn't ever ship."""
    text = (REPO_ROOT / "stack.toml").read_text(encoding="utf-8")
    for placeholder in ("<TODO>", "<FILL_IN>", "__CLAUDE_LEVERAGE_DIR__"):
        assert placeholder not in text, (
            f"stack.toml contains unfilled placeholder {placeholder!r}"
        )


# ---------------------------------------------------------------------------
# Agent parity (lighter version of test_agent_command_frontmatter.py checks)
# ---------------------------------------------------------------------------


def _agent_md_files() -> list[Path]:
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.name.lower() != "readme.md")


@pytest.mark.parametrize("agent_md", _agent_md_files(), ids=lambda p: p.name)
def test_agent_has_codex_toml(agent_md: Path) -> None:
    """The full parity test is in test_agent_command_frontmatter.py; this
    one just catches the simple "did we forget to regenerate" case."""
    toml_path = CODEX_AGENTS_DIR / (agent_md.stem + ".toml")
    assert toml_path.is_file(), (
        f"{agent_md.name}: no Codex parity at {toml_path.relative_to(REPO_ROOT)}. "
        f"Run: python scripts/gen-codex-agents.py"
    )
