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


def test_frontmatter_allowed_tools_is_exactly_the_readonly_set():
    frontmatter = _text().split("---")[1]
    tools = re.findall(r"^\s*-\s*(\S.*?)\s*$", frontmatter.split("allowed-tools:")[1], re.M)
    assert tools == ["Read", "Grep", "Glob", "Bash(git rev-parse:*)"], (
        f"allowed-tools drifted from the exact read-only set required by "
        f"ADR 0013 (platform prompts are a consent layer, not an obstacle); "
        f"got {tools}"
    )


def test_denylist_covers_required_patterns():
    # Slice to the denylist step itself — `sudo` etc. also appear in the
    # report example, which would keep this green after a real removal.
    body = _text()
    denylist_step = body[body.index("**Denylist screen.**"):body.index("**Preview + confirm")]
    for pattern in ["sudo", "git push", "--privileged", "npm publish", "twine upload"]:
        assert pattern in denylist_step, f"denylist row missing: {pattern}"


def test_confirmation_step_is_non_skippable_and_fails_closed():
    body = _text()
    assert "non-skippable" in body, "confirm step lost its non-skippable marker"
    assert "nothing executed" in body, (
        "fail-closed wording ('nothing executed') missing — headless runs "
        "must never execute (ADR 0013)"
    )
