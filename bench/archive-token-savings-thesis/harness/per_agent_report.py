"""Per-agent verdicts: which agents save tokens, which to delete, which to improve.

INTERNAL OUTPUT - not part of README. Goes into bench/results/<runid>/per-agent-report.md
and per-agent-scatter.png.

Verdict thresholds (applied to median, requires n_invocations >= 3 for stability):
  GREAT             - savings > 50% AND quality_pass_rate >= 0.9 AND max < 2x median (predictable)
  GOOD              - savings 20-50% AND quality_pass_rate >= 0.9
  MARGINAL          - savings 5-20%, or savings > 20% with quality 0.7-0.9
  NEEDS IMPROVEMENT - savings 0-5%, or quality < 0.7
  DELETE CANDIDATE  - savings <= 0 AND n_invocations >= 5
  INSUFFICIENT DATA - n_invocations < 3
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from report import group_by_cell, load_cells, latest_runid, RESULTS_DIR
from style import (
    COLOR_BASELINE,
    COLOR_REGRESSION,
    COLOR_SAVINGS_OK,
    apply_style,
    fmt_pct,
    fmt_tokens,
)

VERDICT_COLORS = {
    "GREAT": "#2F855A",
    "GOOD": "#38A169",
    "MARGINAL": "#D69E2E",
    "NEEDS IMPROVEMENT": "#DD6B20",
    "DELETE CANDIDATE": "#C53030",
    "INSUFFICIENT DATA": "#A0AEC0",
}


def assign_verdict(savings_ratio: float, quality_rate: float, n_invocations: int, max_med_ratio: float) -> str:
    if n_invocations < 3:
        return "INSUFFICIENT DATA"
    if savings_ratio <= 0 and n_invocations >= 5:
        return "DELETE CANDIDATE"
    if savings_ratio <= 0:
        return "NEEDS IMPROVEMENT"
    if quality_rate < 0.7:
        return "NEEDS IMPROVEMENT"
    if savings_ratio > 0.5 and quality_rate >= 0.9 and max_med_ratio < 2.0:
        return "GREAT"
    if 0.2 <= savings_ratio <= 0.5 and quality_rate >= 0.9:
        return "GOOD"
    if 0.2 <= savings_ratio and 0.7 <= quality_rate < 0.9:
        return "MARGINAL"
    if 0.05 <= savings_ratio < 0.2:
        return "MARGINAL"
    if 0 < savings_ratio < 0.05:
        return "NEEDS IMPROVEMENT"
    return "MARGINAL"


def per_agent_aggregation(cells: list[dict]) -> list[dict]:
    """Group invocations by agent across all leveraged cells.

    For each agent, gather: invocation count, median tokens reported by the
    hook (track-delegations stderr), quality_pass_rate inferred from the parent
    cell quality, and Opus-baseline-estimate by pairing with the same task's
    baseline median.
    """
    grouped = group_by_cell(cells)

    # Baseline median tokens per task = our counterfactual for "if Opus did this alone".
    baseline_median_by_task: dict[str, float] = {}
    for (tid, cond), lst in grouped.items():
        if cond != "baseline":
            continue
        oks = [c["tokens"]["total"] for c in lst if not c.get("is_error")]
        if oks:
            baseline_median_by_task[tid] = statistics.median(oks)

    # invocations[agent] = list of dicts:
    #   {task, tokens (from hook), tier, quality_pass}
    invocations: dict[str, list[dict]] = defaultdict(list)
    for c in cells:
        if c["condition"] != "leveraged" or c.get("is_error"):
            continue
        task = c["task"]
        q = bool(c.get("quality_pass"))
        for d in c.get("delegations") or []:
            agent = d.get("agent")
            tok = d.get("tokens")
            if not agent:
                continue
            invocations[agent].append({
                "task": task,
                "tokens": tok,
                "tier": d.get("tier"),
                "quality_pass": q,
                "leveraged_cell_total": c["tokens"]["total"],
            })

    rows: list[dict] = []
    for agent, lst in sorted(invocations.items(), key=lambda kv: kv[0]):
        token_lst = [x["tokens"] for x in lst if x["tokens"] is not None]
        n = len(lst)
        # Quality across distinct cells that called this agent.
        cells_quality = {(x["task"], x["leveraged_cell_total"]): x["quality_pass"] for x in lst}
        q_rate = (sum(cells_quality.values()) / len(cells_quality)) if cells_quality else 0.0
        tiers = sorted({x["tier"] for x in lst if x.get("tier")})

        # Opus-baseline estimate: per-task baseline median, summed across distinct tasks the agent fired on,
        # then divided by total invocations to get a per-invocation expected baseline.
        # This is a fair attribution because the leveraged session called this agent
        # exactly to do something the baseline session would have done itself.
        tasks_seen = {x["task"] for x in lst}
        baseline_tokens_per_invocation: list[float] = []
        for x in lst:
            if x["task"] in baseline_median_by_task:
                baseline_tokens_per_invocation.append(baseline_median_by_task[x["task"]])
        baseline_estimate = (
            statistics.median(baseline_tokens_per_invocation)
            if baseline_tokens_per_invocation else None
        )

        if token_lst:
            med = int(statistics.median(token_lst))
            mn = min(token_lst)
            mx = max(token_lst)
        else:
            med = mn = mx = 0

        # Savings per invocation = baseline_estimate - leveraged_med
        # As a ratio of baseline.
        if baseline_estimate and baseline_estimate > 0 and med > 0:
            savings_ratio = (baseline_estimate - med) / baseline_estimate
            savings_abs = baseline_estimate - med
        else:
            savings_ratio = 0.0
            savings_abs = 0

        max_med_ratio = (mx / med) if med > 0 else 0.0
        verdict = assign_verdict(savings_ratio, q_rate, n, max_med_ratio)

        rows.append({
            "agent": agent,
            "n_invocations": n,
            "tiers": tiers,
            "tasks_engaged": sorted(tasks_seen),
            "median_tokens": med,
            "min_tokens": mn,
            "max_tokens": mx,
            "baseline_estimate": int(baseline_estimate) if baseline_estimate else None,
            "savings_abs": int(savings_abs),
            "savings_ratio": savings_ratio,
            "quality_pass_rate": q_rate,
            "verdict": verdict,
        })

    # Sort by verdict severity then savings desc.
    severity = {
        "GREAT": 0, "GOOD": 1, "MARGINAL": 2,
        "NEEDS IMPROVEMENT": 3, "DELETE CANDIDATE": 4,
        "INSUFFICIENT DATA": 5,
    }
    rows.sort(key=lambda r: (severity.get(r["verdict"], 9), -r["savings_ratio"]))
    return rows


def render_scatter(rows: list[dict], out_path: Path) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    for r in rows:
        color = VERDICT_COLORS.get(r["verdict"], "#718096")
        size = max(40, min(400, r["median_tokens"] / 200))
        ax.scatter(
            r["n_invocations"], r["savings_ratio"] * 100,
            s=size, c=color, edgecolors="white", linewidth=1.2,
            alpha=0.9, zorder=3,
        )
        ax.annotate(
            r["agent"],
            (r["n_invocations"], r["savings_ratio"] * 100),
            xytext=(6, 4), textcoords="offset points",
            fontsize=9,
        )
    ax.axhline(0, color="#1A202C", linewidth=0.8, alpha=0.4, zorder=1)
    ax.axhline(20, color=COLOR_SAVINGS_OK, linewidth=0.6, alpha=0.25, linestyle=":", zorder=1)
    ax.axhline(50, color=COLOR_SAVINGS_OK, linewidth=0.6, alpha=0.25, linestyle=":", zorder=1)
    ax.set_xlabel("invocations (across all benchmark runs)")
    ax.set_ylabel("savings vs baseline (%)")
    ax.set_title("Per-agent: savings vs invocation count  (marker size = median tokens)")
    ax.grid(True, axis="y")
    ax.set_axisbelow(True)

    # Legend.
    for verdict, color in VERDICT_COLORS.items():
        if any(r["verdict"] == verdict for r in rows):
            ax.scatter([], [], c=color, label=verdict, s=80, edgecolors="white")
    ax.legend(loc="lower right", frameon=True, framealpha=0.95)
    fig.savefig(out_path)
    plt.close(fig)


def render_markdown(manifest: dict, rows: list[dict], scatter_path: Path, out_path: Path) -> None:
    lines: list[str] = []
    pv = manifest.get("plugin_version", "?")
    lines.append(f"# Per-agent verdicts - claude-leverage v{pv}  ({manifest.get('runid','?')})")
    lines.append("")
    lines.append("**Internal report - not part of README.** Use to decide which agents to improve, delete, or add.")
    lines.append("")
    lines.append("![scatter](per-agent-scatter.png)")
    lines.append("")
    lines.append("## Verdicts")
    lines.append("")
    lines.append("| Verdict | Agent | Invocations | Tier(s) | Median tokens | Baseline est. | Savings | Quality |")
    lines.append("|---|---|---:|---|---:|---:|---:|---:|")
    for r in rows:
        bl = fmt_tokens(r["baseline_estimate"]) if r["baseline_estimate"] else "?"
        sav = (
            f"-{r['savings_ratio']*100:.0f}%" if r['savings_ratio'] > 0
            else f"+{-r['savings_ratio']*100:.0f}%" if r['savings_ratio'] < 0
            else "0%"
        )
        lines.append(
            f"| {r['verdict']} | `{r['agent']}` | {r['n_invocations']} | {','.join(r['tiers'])} | "
            f"{fmt_tokens(r['median_tokens'])} ({fmt_tokens(r['min_tokens'])}-{fmt_tokens(r['max_tokens'])}) | "
            f"{bl} | {sav} | {r['quality_pass_rate']*100:.0f}% |"
        )
    lines.append("")
    lines.append("## Reading this report")
    lines.append("")
    lines.append("**Important: this measures agent-execution efficiency, NOT system-level cost.**")
    lines.append("")
    lines.append("An agent can show -78% savings here while the leveraged session as a whole costs MORE than baseline. Example: `code-reviewer` (Sonnet) uses 7k tokens to do the review; baseline Opus does the same review in 34k tokens. The agent itself is efficient. But the leveraged session also pays for Opus orchestration (~30k tokens to dispatch, read the report, and integrate). Net session cost can still be higher than baseline.")
    lines.append("")
    lines.append("Use this report to ask: **is each agent doing its piece efficiently?** Use `report.md` (hero chart) to ask: **does the plugin net out cheaper overall?**")
    lines.append("")
    lines.append("- **Baseline estimate** is the median total tokens the *baseline session* spent on the same task (the counterfactual: 'what would Opus alone have done if it did the whole task').")
    lines.append("- **Savings** is `(baseline_estimate - median_agent_tokens) / baseline_estimate`. This is agent intrinsic efficiency, not net session savings. Negative = agent uses more tokens than baseline did total on the same task.")
    lines.append("- **Quality** is the pass rate of the deterministic task-level check across all leveraged runs that engaged this agent. A low rate means the savings number is suspect.")
    lines.append("- **Insufficient data** = n_invocations < 3. The mini-suite invokes each agent at most N times (one task per agent), so most rows will be INSUFFICIENT in v1. The realistic suite (v2) will fix this by spreading invocations across more tasks.")
    lines.append("")
    lines.append("## Actions to consider")
    lines.append("")
    deletions = [r for r in rows if r["verdict"] == "DELETE CANDIDATE"]
    improvements = [r for r in rows if r["verdict"] == "NEEDS IMPROVEMENT"]
    marginals = [r for r in rows if r["verdict"] == "MARGINAL"]
    greats = [r for r in rows if r["verdict"] == "GREAT"]
    if deletions:
        lines.append("**Delete candidates** (savings <= 0 with sufficient data):")
        for r in deletions:
            lines.append(f"- `{r['agent']}` - savings {r['savings_ratio']*100:.0f}%, {r['n_invocations']} invocations")
        lines.append("")
    if improvements:
        lines.append("**Needs improvement** (low savings or low quality):")
        for r in improvements:
            lines.append(f"- `{r['agent']}` - savings {r['savings_ratio']*100:.0f}%, quality {r['quality_pass_rate']*100:.0f}%")
        lines.append("")
    if marginals:
        lines.append("**Marginal** (small-but-real wins, possible to tighten):")
        for r in marginals:
            lines.append(f"- `{r['agent']}` - savings {r['savings_ratio']*100:.0f}%, quality {r['quality_pass_rate']*100:.0f}%")
        lines.append("")
    if greats:
        lines.append("**Clear wins** (keep, possibly use as templates for future agents):")
        for r in greats:
            lines.append(f"- `{r['agent']}` - savings {r['savings_ratio']*100:.0f}%, quality {r['quality_pass_rate']*100:.0f}%")
        lines.append("")
    if not (deletions or improvements or marginals or greats):
        lines.append("_No actionable verdicts yet - all agents in INSUFFICIENT DATA bucket. Run a larger suite (v2) to populate per-agent statistics._")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    runid = sys.argv[1] if len(sys.argv) > 1 else latest_runid()
    out_dir = RESULTS_DIR / runid
    if not out_dir.exists():
        raise SystemExit(f"no such results dir: {out_dir}")
    manifest, cells = load_cells(runid)
    rows = per_agent_aggregation(cells)

    scatter_path = out_dir / "per-agent-scatter.png"
    md_path = out_dir / "per-agent-report.md"
    render_scatter(rows, scatter_path)
    render_markdown(manifest, rows, scatter_path, md_path)
    print(f"wrote: {scatter_path}")
    print(f"wrote: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
