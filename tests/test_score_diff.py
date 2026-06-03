from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "score_diff", REPO_ROOT / "bench" / "conventions-eval" / "score_diff.py"
)
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def test_compare_reports_after_better_than_before(tmp_path):
    before = tmp_path / "before.py"
    before.write_text("def data():\n    tmp = 1\n    return tmp\n", encoding="utf-8")
    after = tmp_path / "after.py"
    after.write_text("def fetch_user(user_id):\n    return user_id\n", encoding="utf-8")
    res = sd.compare(before, after)
    assert res["after"]["overall"] >= res["before"]["overall"]
    assert res["delta_overall"] >= 0
    assert set(res["before"]) == {"overall", "naming_clarity", "casing_consistency", "structure"}
