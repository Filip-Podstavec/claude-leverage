"""Compare convention-adherence between the two arms of a full-repo A/B (e.g. the
agent's produced change in a `before/` vs `after/` tree), using the scorer.

Prints per-metric scores for each side and the delta. The adherence number is a
hygiene / delivery signal — read it ALONGSIDE task-success and house-rule
compliance, never as the sole verdict (a capable model writes clean generic code
unaided; the plugin's value shows up in navigation + non-default conventions).

Usage:
    python bench/conventions-eval/score_diff.py <before> <after>
where each arg is a .py file or a directory of .py files (the produced change).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from score_adherence import score_files  # noqa: E402

_METRICS = ("naming_clarity", "casing_consistency", "structure")


def _collect(path: Path) -> dict:
    if path.is_dir():
        return {
            str(p.relative_to(path)): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(path.rglob("*.py"))
        }
    return {path.name: path.read_text(encoding="utf-8", errors="replace")}


def compare(before: Path, after: Path) -> dict:
    b = score_files(_collect(before))
    a = score_files(_collect(after))
    return {
        "before": {"overall": b["overall"], **{m: b["metrics"][m]["score"] for m in _METRICS}},
        "after": {"overall": a["overall"], **{m: a["metrics"][m]["score"] for m in _METRICS}},
        "delta_overall": round(a["overall"] - b["overall"], 4),
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: score_diff.py <before> <after>", file=sys.stderr)
        return 2
    print(json.dumps(compare(Path(argv[0]), Path(argv[1])), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
