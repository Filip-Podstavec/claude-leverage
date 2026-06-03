from __future__ import annotations
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_casing_consistency_dominant_style_per_kind():
    ids = [
        ("function", "fetch_user"),
        ("function", "save_order"),
        ("function", "deleteThing"),   # camelCase outlier among snake funcs
        ("type", "UserRepo"),
        ("type", "OrderRepo"),
    ]
    m = sa.score_casing_consistency(ids)
    # functions: 2 snake of 3 -> dominant snake_case, 1 deviates
    # types: 2 of 2 PascalCase -> 0 deviate
    assert m["deviating"] == 1
    assert m["total"] == 5
    assert m["score"] == round(1 - 1 / 5, 4)
    assert m["by_kind"]["function"]["dominant"] == "snake_case"


def test_structure_flags_god_file_and_long_function():
    long_func = "def big():\n" + "\n".join(f"    a{i} = {i}" for i in range(70)) + "\n"
    short_func = "def small():\n    return 1\n"
    src = short_func + long_func
    m = sa.score_structure({"svc.py": src}, file_loc_ceiling=400, func_loc_ceiling=60)
    assert m["functions_total"] == 2
    assert m["functions_over"] == 1          # big() is 71 lines > 60
    assert m["god_files"] == []              # under 400 LOC
    assert 0.0 <= m["score"] <= 1.0


def test_score_files_assembles_report_and_coverage():
    files = {
        "good.py": "def fetch_user(user_id):\n    return user_id\n",
        "notes.md": "# not code\n",          # unsupported lang -> skipped
    }
    rep = sa.score_files(files)
    assert set(rep["metrics"]) == {"naming_clarity", "casing_consistency", "structure"}
    assert rep["coverage"]["files_scored"] == 1
    assert rep["coverage"]["files_skipped"] == 1
    assert ".md" in rep["coverage"]["skipped_extensions"]
    assert 0.0 <= rep["overall"] <= 1.0


GIT = shutil.which("git")
requires_git = pytest.mark.skipif(GIT is None, reason="git not on PATH")


def _run_cli(*args, cwd):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "score_adherence.py"), *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


def test_cli_repo_mode_emits_json(tmp_path):
    (tmp_path / "a.py").write_text("def fetch_user(uid):\n    return uid\n")
    res = _run_cli("--repo", str(tmp_path), cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    rep = json.loads(res.stdout)
    assert rep["coverage"]["files_scored"] == 1


@requires_git
def test_cli_diff_mode_scores_changed_files(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *a],
                       cwd=str(tmp_path), check=True, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / "base.py").write_text("def fetch_user(uid):\n    return uid\n")
    git("add", "."); git("commit", "-qm", "base")
    (tmp_path / "change.py").write_text("def data():\n    tmp = 1\n    return tmp\n")
    git("add", ".")
    res = _run_cli("--diff", "HEAD", cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    rep = json.loads(res.stdout)
    assert rep["coverage"]["files_scored"] == 1


def test_structure_counts_body_of_multiline_signature_function():
    body = "\n".join(f"    a{i} = {i}" for i in range(70))
    src = "def big(\n    arg_one,\n    arg_two,\n):\n" + body + "\n"
    m = sa.score_structure({"svc.py": src}, func_loc_ceiling=60)
    assert m["functions_total"] == 1
    assert m["functions_over"] == 1   # 70-line body flagged despite the wrapped signature


def test_structure_counts_nested_functions():
    src = (
        "def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "    return inner\n"
    )
    m = sa.score_structure({"svc.py": src})
    assert m["functions_total"] == 2   # outer and inner both counted


@requires_git
def test_cli_diff_mode_works_from_subdirectory(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *a],
                       cwd=str(tmp_path), check=True, capture_output=True, text=True)
    git("init", "-q")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "base.py").write_text("def fetch_user(uid):\n    return uid\n")
    git("add", "."); git("commit", "-qm", "base")
    (sub / "change.py").write_text("def data():\n    tmp = 1\n    return tmp\n")
    git("add", ".")
    res = _run_cli("--diff", "HEAD", cwd=sub)   # invoked from the subdir, not the root
    assert res.returncode == 0, res.stderr
    rep = json.loads(res.stdout)
    assert rep["coverage"]["files_scored"] == 1


def test_flag_blob_violations_flags_new_vague_and_casing():
    blob = (
        "def fetch_user(uid):\n"
        "    result = uid\n"
        "    return result\n"
        "def DoThing():\n"
        "    return 1\n"
    )
    flags = sa.flag_blob_violations(blob, casing={"functions": "snake_case"},
                                    denylist=["result"])
    names = {f["name"] for f in flags}
    assert "result" in names
    assert "DoThing" in names
    assert "fetch_user" not in names


def test_flag_blob_violations_clean_blob_is_empty():
    blob = "def fetch_user(uid):\n    return uid\n"
    assert sa.flag_blob_violations(blob, casing={"functions": "snake_case"}) == []


def test_clean_tree_scores_higher_than_dirty_tree():
    clean = {
        "user_service.py": (
            "MAX_RETRIES = 3\n"
            "def fetch_user(user_id):\n    return user_id\n"
            "def save_order(order_id):\n    return order_id\n"
            "class UserRepository:\n    pass\n"
        ),
    }
    dirty = {
        "svc.py": (
            "maxRetries = 3\n"                 # casing outlier
            "def data():\n    tmp = 1\n    return tmp\n"   # vague names
            "def doStuff():\n    x = 2\n    return x\n"     # vague + casing
            "class user_repo:\n    pass\n"     # wrong type casing
        ),
    }
    clean_overall = sa.score_files(clean)["overall"]
    dirty_overall = sa.score_files(dirty)["overall"]
    # The gate checks meaningful SEPARATION (clean clearly beats dirty), not an
    # arbitrary absolute floor — the floor depends on the metric mix per fixture.
    assert clean_overall >= 0.9
    assert clean_overall - dirty_overall >= 0.25
