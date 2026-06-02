from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "score_adherence", REPO_ROOT / "scripts" / "score_adherence.py"
)
sa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sa)


def test_extract_python_identifiers_kinds():
    src = (
        "import os\n"
        "MAX_RETRIES = 3\n"
        "def fetch_user(user_id):\n"
        "    result = user_id + 1\n"
        "    return result\n"
        "class UserRepository:\n"
        "    pass\n"
    )
    ids = sa.extract_python_identifiers(src)
    assert ("function", "fetch_user") in ids
    assert ("type", "UserRepository") in ids
    assert ("constant", "MAX_RETRIES") in ids
    assert ("variable", "result") in ids
    assert all(name != "os" for _, name in ids)


def test_naming_clarity_flags_vague_and_short():
    ids = [
        ("variable", "user_id"),     # clear
        ("function", "fetch_user"),  # clear
        ("variable", "data"),        # vague
        ("variable", "tmp"),         # vague
        ("variable", "x"),           # too short, but loop-ok -> clear
        ("variable", "q"),           # too short, not loop-ok -> unclear
    ]
    m = sa.score_naming_clarity(ids)
    assert m["total"] == 6
    assert m["unclear"] == 3            # data, tmp, q
    assert "data" in m["examples"]
    assert m["score"] == round(1 - 3 / 6, 4)
