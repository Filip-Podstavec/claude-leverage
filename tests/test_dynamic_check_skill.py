"""Safety-contract guards for skills/dynamic-check/SKILL.md.

/dynamic-check is the only skill in the stack that executes repo-declared
commands. Its safety rests on frontmatter that does NOT pre-approve broad
Bash, a denylist tripwire, and a non-skippable confirm step (ADR 0013).
These guards keep future edits from quietly weakening any of the three.
"""

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "dynamic-check" / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter_does_not_preapprove_broad_bash():
    frontmatter = _text().split("---")[1]
    assert re.search(r"^\s*-\s*Bash\(git rev-parse:\*\)\s*$", frontmatter, re.M), (
        "read-only helper grant Bash(git rev-parse:*) missing from allowed-tools"
    )
    assert not re.search(r"^\s*-\s*Bash(\(\*\))?\s*$", frontmatter, re.M), (
        "plain `Bash` / `Bash(*)` in allowed-tools pre-approves every command "
        "for the turn; forbidden by ADR 0013 (platform prompts are a consent "
        "layer, not an obstacle)"
    )


def test_denylist_covers_required_patterns():
    body = _text()
    for pattern in ["sudo", "git push", "--privileged", "npm publish", "twine upload"]:
        assert pattern in body, f"denylist row missing: {pattern}"


def test_confirmation_step_is_non_skippable_and_fails_closed():
    body = _text()
    assert "non-skippable" in body, "confirm step lost its non-skippable marker"
    assert "nothing executed" in body, (
        "fail-closed wording ('nothing executed') missing — headless runs "
        "must never execute (ADR 0013)"
    )
