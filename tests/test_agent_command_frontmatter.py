"""Structural validation of every agent and command file shipped by this repo.

Catches the class of bugs that don't show up until a user runs `/agents` and
sees a silent load failure: missing `model:` line, wrong `tools:` key,
description that won't render, filename/name-field mismatch, etc.

This is intentionally stdlib-only — no PyYAML dependency. The frontmatter
format used by Claude Code is a thin subset of YAML and a hand-rolled
parser keeps CI bootstrap to `pip install pytest` and nothing else.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"
# extras/ holds opt-in components that aren't loaded by the default plugin
# install but still need to be structurally valid (same maintenance contract).
EXTRAS_AGENTS_DIR = REPO_ROOT / "extras" / "agents"
EXTRAS_COMMANDS_DIR = REPO_ROOT / "extras" / "commands"
# Per-dir READMEs live in *-docs/ siblings (NOT inside agents/ or commands/)
# because Claude Code's plugin loader registers every *.md under agents/ as a
# phantom agent (and every *.md under commands/ as a phantom slash command).
# Moving the dir-internal docs out kills two phantom registrations.

VALID_MODELS = {"sonnet", "haiku", "opus"}


def parse_frontmatter(text: str) -> Optional[dict[str, str]]:
    """Return parsed top-of-file YAML frontmatter, or None if absent/malformed.

    Recognized format: starts with `---\\n`, ends with a line that is `---`,
    contains `key: value` lines in between. Values are stripped of surrounding
    double quotes. Multi-line values are not supported (intentional — Claude
    Code's agent format does not use them).
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


# Discovery is module-level so the parametrize IDs name each file explicitly
# in pytest output. Failures point straight at the offending file. extras/
# components participate in the same validation so they don't drift while
# they're not loaded by the default plugin.
def _md_files(d: Path) -> list[Path]:
    if not d.exists():
        return []
    return [p for p in d.glob("*.md") if p.name.lower() != "readme.md"]


AGENT_FILES = sorted(_md_files(AGENTS_DIR) + _md_files(EXTRAS_AGENTS_DIR))
COMMAND_FILES = sorted(_md_files(COMMANDS_DIR) + _md_files(EXTRAS_COMMANDS_DIR))


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_has_frontmatter(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm is not None, f"{path.name}: missing or malformed frontmatter"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_required_fields(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
    for required in ("name", "description", "tools", "model"):
        assert required in fm, f"{path.name}: missing '{required}' in frontmatter"
        assert fm[required], f"{path.name}: '{required}' is empty"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_name_matches_filename(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
    expected = path.stem
    assert fm.get("name") == expected, (
        f"{path.name}: name field {fm.get('name')!r} != filename stem {expected!r}"
    )


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_model_is_valid(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
    model = fm.get("model", "").lower()
    assert model in VALID_MODELS, (
        f"{path.name}: model={model!r} not in {sorted(VALID_MODELS)}"
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", COMMAND_FILES, ids=lambda p: p.name)
def test_command_has_frontmatter(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm is not None, f"{path.name}: missing or malformed frontmatter"


@pytest.mark.parametrize("path", COMMAND_FILES, ids=lambda p: p.name)
def test_command_has_description(path: Path) -> None:
    fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
    assert "description" in fm, f"{path.name}: missing 'description' in frontmatter"
    assert fm["description"], f"{path.name}: empty description"


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------


def test_no_duplicate_agent_names() -> None:
    names = []
    for path in AGENT_FILES:
        fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
        names.append(fm.get("name"))
    seen: dict[str, int] = {}
    for n in names:
        seen[n] = seen.get(n, 0) + 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, f"duplicate agent names: {duplicates}"
