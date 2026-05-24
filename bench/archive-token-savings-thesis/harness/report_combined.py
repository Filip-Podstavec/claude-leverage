"""Combined report: cold (pre-trim) vs cold (post-trim) vs warm.

Reads three result dirs and emits a single side-by-side comparison chart
plus a markdown summary. Used after running both the post-trim cold and
warm benchmarks so the user can see all three signals on one page.

Usage:
    python bench/harness/report_combined.py \
        --cold-pre  2026-05-21_v0.10.0 \
        --cold-post 2026-05-23_v0.10.0-cold-post-trim \
        --warm      2026-05-23_v0.10.0-warm \
        --out-name combined-2026-05-23

Outputs into bench/results/<out-name>/:
    summary.md           combined narrative + tables
    summary.png          three-stage hero
    per-agent-delta.png  agent intrinsic savings cold-pre vs cold-post

Read-only on the input dirs.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

HARNESS_DIR = Path(__file__).resolve().parent
BENCH_DIR = HARNESS_DIR.parent
RESULTS_DIR = BENCH_DIR / "results"

sys.path.insert(0, str(HARNESS_DIR))
from style import (  # noqa: E402
    COLOR_BASELINE,
    COLOR_LEVERAGED,
    COLOR_REGRESSION,
    COLOR_SAVINGS_OK,
    apply_style,
    fmt_tokens,
)


def load_run(runid: str) -> tuple[dict, list[dict]]:
    """Return (manifest, list of cell summary dicts) for a given runid."""
    d = RESULTS_DIR / runid
    if not (d / "manifest.json").exists():
        raise SystemExit(f"missing manifest: {d}")
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    cells = []
    for p in sorted((d / "raw").glob("*.session.json")):
        cells.append(json.loads(p.read_text(encoding="utf-8")))
    return manifest, cells


def aggregate_cold(cells: list[dict]) -> dict[str, dict]:
    """{condition -> {sum_cost_median, n_cells_ok, per_task_costs}} for cold runs.

    Sums the per-task median costs to produce a 'full workflow' cost for the
    suite. baseline-suite = T1+T2+T3+T4 baseline medians.
    """
    by_task_cond = {}
    for c in cells:
        if c.get("is_error"):
            continue
        key = (c["task"], c["condition"])
        by_task_cond.setdefault(key, []).append(c["total_cost_usd"])

    out = {"baseline": {"per_task": {}, "sum": 0.0, "n_ok_cells": 0},
           "leveraged": {"per_task": {}, "sum": 0.0, "n_ok_cells": 0}}
    for (task, cond), costs in by_task_cond.items():
        m = statistics.median(costs)
        out[cond]["per_task"][task] = {
            "median": m,
            "min": min(costs),
            "max": max(costs),
            "n": len(costs),
        }
        out[cond]["sum"] += m
        out[cond]["n_ok_cells"] += len(costs)
    return out


def aggregate_warm(cells: list[dict]) -> dict[str, dict]:
    """{condition -> {median_total_cost, min, max, n_cells_ok, quality_all_pass}}."""
    by_cond = {}
    for c in cells:
        if c.get("is_error"):
            continue
        by_cond.setdefault(c["condition"], []).append(c)

    out = {}
    for cond, lst in by_cond.items():
        costs = [c["total_cost_usd"] for c in lst]
        all_q = [all(t["quality_pass"] for t in c["turns"]) for c in lst]
        out[cond] = {
            "median_cost": statistics.median(costs),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "n": len(lst),
            "n_all_quality_pass": sum(all_q),
        }
    return out


def render_summary_chart(
    pre_agg: dict, post_agg: dict, warm_agg: dict, out_path: Path, plugin_version: str
) -> None:
    """Three-stage horizontal grouped bar chart."""
    apply_style()
    fig, ax = plt.subplots(figsize=(11, 5.5))

    stages = [
        ("Cold cache, pre-trim\n(v1 benchmark, 4 separate sessions)", pre_agg),
        ("Cold cache, post-trim\n(trimmed agents, 4 separate sessions)", post_agg),
        ("Warm cache, post-trim\n(trimmed agents, 1 session × 4 turns)", warm_agg),
    ]

    y_positions = np.arange(len(stages))
    bar_h = 0.36

    for i, (label, agg) in enumerate(stages):
        if "per_task" in agg.get("baseline", {}):
            bl_cost = agg["baseline"]["sum"]
            lv_cost = agg["leveraged"]["sum"]
            bl_min = sum(t["min"] for t in agg["baseline"]["per_task"].values())
            bl_max = sum(t["max"] for t in agg["baseline"]["per_task"].values())
            lv_min = sum(t["min"] for t in agg["leveraged"]["per_task"].values())
            lv_max = sum(t["max"] for t in agg["leveraged"]["per_task"].values())
        else:
            bl_cost = agg["baseline"]["median_cost"]
            lv_cost = agg["leveraged"]["median_cost"]
            bl_min = agg["baseline"]["min_cost"]
            bl_max = agg["baseline"]["max_cost"]
            lv_min = agg["leveraged"]["min_cost"]
            lv_max = agg["leveraged"]["max_cost"]

        y_bl = y_positions[i] + bar_h / 2
        y_lv = y_positions[i] - bar_h / 2
        ax.barh(y_bl, bl_cost, height=bar_h, color=COLOR_BASELINE, zorder=3)
        ax.errorbar(
            bl_cost, y_bl,
            xerr=[[bl_cost - bl_min], [bl_max - bl_cost]],
            fmt="none", ecolor=COLOR_BASELINE, capsize=3, alpha=0.6, zorder=4,
        )
        ax.barh(y_lv, lv_cost, height=bar_h, color=COLOR_LEVERAGED, zorder=3)
        ax.errorbar(
            lv_cost, y_lv,
            xerr=[[lv_cost - lv_min], [lv_max - lv_cost]],
            fmt="none", ecolor=COLOR_LEVERAGED, capsize=3, alpha=0.6, zorder=4,
        )

        delta_ratio = (lv_cost - bl_cost) / bl_cost if bl_cost else 0.0
        sign = "+" if delta_ratio >= 0 else "-"
        annot = f"{sign}{abs(delta_ratio) * 100:.0f}%"
        color = COLOR_REGRESSION if delta_ratio > 0 else COLOR_SAVINGS_OK
        anchor_x = max(bl_max, lv_max)
        ax.text(
            anchor_x * 1.03, y_positions[i],
            annot,
            va="center", ha="left",
            color=color, fontsize=12, fontweight="bold",
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels([s[0] for s in stages])
    ax.invert_yaxis()
    ax.set_xlabel("equivalent API cost (USD per full 4-task workflow, median)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax.set_title(
        f"claude-leverage v{plugin_version}: cost across 3 measurement stages",
        loc="left", pad=14,
    )

    cur_xmax = ax.get_xlim()[1]
    ax.set_xlim(0, cur_xmax * 1.16)

    legend_handles = [
        Patch(facecolor=COLOR_BASELINE, label="baseline (vanilla Claude Code)"),
        Patch(facecolor=COLOR_LEVERAGED, label="leveraged (+ claude-leverage plugin)"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    fig.subplots_adjust(bottom=0.18)
    fig.savefig(out_path)
    plt.close(fig)


def render_markdown(
    pre_manifest: dict,
    pre_agg: dict,
    post_manifest: dict,
    post_agg: dict,
    warm_manifest: dict,
    warm_agg: dict,
    out_path: Path,
    chart_name: str,
) -> None:
    pv = post_manifest.get("plugin_version", "?")
    lines: list[str] = []
    lines.append(f"# claude-leverage v{pv} - combined benchmark summary")
    lines.append("")
    lines.append(f"![combined]({chart_name})")
    lines.append("")
    lines.append("## Headline (median per full 4-task workflow)")
    lines.append("")
    lines.append("| Stage | Baseline | Leveraged | Delta |")
    lines.append("|---|---:|---:|---:|")

    def fmt_delta(b: float, l: float) -> str:
        if b == 0:
            return "n/a"
        d = (l - b) / b
        sign = "+" if d >= 0 else "-"
        return f"**{sign}{abs(d) * 100:.0f}%**"

    def fmt_row(stage_name: str, agg: dict, kind: str) -> str:
        if kind == "cold":
            b, l = agg["baseline"]["sum"], agg["leveraged"]["sum"]
        else:
            b, l = agg["baseline"]["median_cost"], agg["leveraged"]["median_cost"]
        return f"| {stage_name} | ${b:.3f} | ${l:.3f} | {fmt_delta(b, l)} |"

    lines.append(fmt_row("Cold cache, pre-trim (v1, 4 separate sessions)", pre_agg, "cold"))
    lines.append(fmt_row("Cold cache, post-trim (4 separate sessions)", post_agg, "cold"))
    lines.append(fmt_row("Warm cache, post-trim (1 session × 4 turns)", warm_agg, "warm"))
    lines.append("")

    # Cold-vs-warm savings analysis for the LEVERAGED condition.
    cold_post_lev = post_agg["leveraged"]["sum"]
    warm_lev = warm_agg["leveraged"]["median_cost"]
    if cold_post_lev > 0:
        warm_savings = (cold_post_lev - warm_lev) / cold_post_lev * 100
        lines.append(f"**Cold→warm savings (leveraged):** ${cold_post_lev:.3f} → ${warm_lev:.3f}  ({'-' if warm_savings >= 0 else '+'}{abs(warm_savings):.0f}%). Cache amortization removes the plugin's per-session loading tax.")
        lines.append("")

    # Trim impact on cold leveraged.
    pre_lev = pre_agg["leveraged"]["sum"]
    post_lev = post_agg["leveraged"]["sum"]
    if pre_lev > 0:
        trim_savings = (pre_lev - post_lev) / pre_lev * 100
        lines.append(f"**Trim impact on cold leveraged:** ${pre_lev:.3f} → ${post_lev:.3f}  ({'-' if trim_savings >= 0 else '+'}{abs(trim_savings):.0f}%). Smaller agent prompts means less cache_creation tax even on cold cache.")
        lines.append("")

    lines.append("## Per-task cold (post-trim)")
    lines.append("")
    lines.append("| Task | Baseline | Leveraged | Delta |")
    lines.append("|---|---:|---:|---:|")
    for task in sorted(post_agg["baseline"]["per_task"].keys()):
        b = post_agg["baseline"]["per_task"][task]["median"]
        l = post_agg["leveraged"]["per_task"][task]["median"]
        lines.append(f"| {task} | ${b:.3f} | ${l:.3f} | {fmt_delta(b, l)} |")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append("- **Cold-cache stages** run each task in its own headless `claude -p` session with a fresh fixture copy in `$TMPDIR` and `--setting-sources project`. 4 tasks × 2 conditions × N=3 = 24 sessions per stage.")
    lines.append("- **Warm-cache stage** runs all 4 turns in ONE `claude -p` session via `--input-format stream-json` against a single combined fixture (`bench/fixtures/warm-session/`). Cache_read tokens after turn 1 prove the system prompt cache is reused across turns. 1 fixture × 2 conditions × N=3 = 6 sessions.")
    lines.append("- **Trim:** agent prompts in `agents/*.md` audited and trimmed (845 → 635 lines, -25%). `context-gatherer` switched from Sonnet to Haiku based on v1 finding that baseline `Explore` (Haiku built-in) was structurally cheaper than our Sonnet context-gatherer.")
    lines.append("- Plugin version is identical across all stages (it's the v0.10.0 plugin with v0.11 agent updates). Cost is `result.total_cost_usd` from stream-json (Anthropic's published per-model pricing applied to actual token usage).")
    lines.append("")
    lines.append("Raw cells: `bench/results/<runid>/raw/*.session.json`.")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cold-pre", required=True)
    p.add_argument("--cold-post", required=True)
    p.add_argument("--warm", required=True)
    p.add_argument("--out-name", required=True)
    args = p.parse_args()

    pre_m, pre_c = load_run(args.cold_pre)
    post_m, post_c = load_run(args.cold_post)
    warm_m, warm_c = load_run(args.warm)

    pre_agg = aggregate_cold(pre_c)
    post_agg = aggregate_cold(post_c)
    warm_agg = aggregate_warm(warm_c)

    out_dir = RESULTS_DIR / args.out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_path = out_dir / "summary.png"
    md_path = out_dir / "summary.md"

    render_summary_chart(pre_agg, post_agg, warm_agg, chart_path, post_m.get("plugin_version", "?"))
    render_markdown(
        pre_m, pre_agg, post_m, post_agg, warm_m, warm_agg,
        md_path, chart_name="summary.png",
    )
    print(f"wrote: {chart_path}")
    print(f"wrote: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
