"""Internal-consistency guards for skills/repo-doctor/SKILL.md.

The repo-doctor skill is model-executed prose: its dimension numbering,
group heading counts, scope lists, and the gaming-doc companion can drift
apart with no compiler to notice. These regex guards catch exactly the
drift class the skill's own Sync dimensions exist to catch in other repos.
"""

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "repo-doctor" / "SKILL.md"
GAMING = Path(__file__).resolve().parents[1] / "docs" / "repo-doctor-gaming.md"

DIM_COUNT = 24


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _dimensions_section(text: str) -> str:
    # Slice to the Dimensions section only — the Workflow section reuses
    # low numbers ("1. **Resolve repo root.**") and would false-match.
    start = text.index("## Dimensions")
    end = text.index("## Levels", start)
    return text[start:end]


def test_dimensions_contiguous_and_unique():
    dims = _dimensions_section(_skill_text())
    nums = [int(m) for m in re.findall(r"^(\d+)\. \*\*", dims, re.M)]
    assert nums == list(range(1, DIM_COUNT + 1)), (
        f"dimension numbering is not 1..{DIM_COUNT} exactly once: {nums}"
    )


def test_group_heading_counts_sum_to_dim_count():
    dims = _dimensions_section(_skill_text())
    counts = [int(m) for m in re.findall(r"^###.*\((\d+) checks?\b", dims, re.M)]
    assert sum(counts) == DIM_COUNT, (
        f"group heading counts {counts} sum to {sum(counts)}, not {DIM_COUNT}"
    )


def test_scope_values_consistent_between_frontmatter_and_tunables():
    text = _skill_text()
    frontmatter = text.split("---", 2)[1]
    # Anchor to the Tunables section — earlier prose legitimately mentions
    # single scope values (e.g. "`--scope hygiene`") and must not match.
    tunables_section = text[text.index("## Tunables"):]
    hint = re.search(r"--scope ([a-z|]+)", frontmatter)
    tunable = re.search(r"`--scope ([a-z|]+)`", tunables_section)
    assert hint, "frontmatter argument-hint lost its --scope value list"
    assert tunable, "Tunables section lost its --scope value list"
    assert hint.group(1) == tunable.group(1), (
        f"--scope lists diverged: frontmatter={hint.group(1)!r} "
        f"tunables={tunable.group(1)!r}"
    )


def test_gaming_doc_has_one_row_per_dimension():
    rows = re.findall(r"^\| (\d+) \|", GAMING.read_text(encoding="utf-8"), re.M)
    assert sorted(int(r) for r in rows) == list(range(1, DIM_COUNT + 1)), (
        f"docs/repo-doctor-gaming.md must have exactly one row per "
        f"dimension 1..{DIM_COUNT}; got {sorted(int(r) for r in rows)}"
    )
