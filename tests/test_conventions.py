from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "conventions", REPO_ROOT / "scripts" / "conventions.py"
)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

SAMPLE = """\
schema_version: 1
naming:
  casing:
    functions: snake_case
    types: PascalCase
  vague_denylist:
    - data
    - result
structure:
  roots:
    "scripts/hooks/": "shell hooks; fail-open"
    "skills/": "one SKILL.md per dir"
  file_loc_ceiling: 400
consistency:
  - "Hooks must fail-open and exit 0 when a parser is absent."
  - "AIDEV anchors: all-caps, <=120 chars."
"""


def test_parse_conventions_extracts_normalized_profile():
    prof = conv.parse_conventions(SAMPLE)
    assert prof["casing"] == {"functions": "snake_case", "types": "PascalCase"}
    assert prof["vague_denylist"] == ["data", "result"]
    assert prof["structure_roots"]["skills/"] == "one SKILL.md per dir"
    assert prof["consistency"][0].startswith("Hooks must fail-open")
    assert len(prof["consistency"]) == 2


def test_parse_conventions_empty_returns_none():
    assert conv.parse_conventions("") is None
    assert conv.parse_conventions("   \n  \n") is None


def test_match_role_longest_prefix():
    roots = {"scripts/": "scripts root", "scripts/hooks/": "hook scripts"}
    assert conv.match_role("scripts/hooks/context-surface.sh", roots) == "hook scripts"
    assert conv.match_role("scripts/build.py", roots) == "scripts root"
    assert conv.match_role("docs/x.md", roots) is None


def test_minimal_parser_handles_lists_without_pyyaml(monkeypatch):
    # Force the fallback path (simulate PyYAML absent) and assert the FULL
    # profile, including the block-list fields the bug dropped.
    monkeypatch.setattr(conv, "_yaml", None)
    prof = conv.parse_conventions(SAMPLE)
    assert prof["casing"]["functions"] == "snake_case"
    assert prof["vague_denylist"] == ["data", "result"]
    assert len(prof["consistency"]) == 2
    assert prof["structure_roots"]["skills/"] == "one SKILL.md per dir"
