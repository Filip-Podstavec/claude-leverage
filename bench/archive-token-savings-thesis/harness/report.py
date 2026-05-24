"""Generate the markdown report + hero PNG + per-task PNG from a result dir.

Reads:
    bench/results/<runid>/manifest.json
    bench/results/<runid>/raw/*.session.json

Writes:
    bench/results/<runid>/report.md
    bench/results/<runid>/hero.png
    bench/results/<runid>/per-task.png

Usage:
    python bench/harness/report.py [<runid>]   # default: latest dir
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from style import (
    COLOR_BASELINE,
    COLOR_LEVERAGED,
    COLOR_REGRESSION,
    COLOR_SAVINGS_OK,
    MARK_FAIL,
    MARK_PASS,
    TIER_COLORS,
    apply_style,
    fmt_pct,
    fmt_tokens,
)

BENCH_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BENCH_DIR / "results"


def load_cells(runid: str) -> tuple[dict, list[dict]]:
    """Return (manifest, cells)."""
    d = RESULTS_DIR / runid
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    raw_dir = d / "raw"
    cells = []
    for p in sorted(raw_dir.glob("*.session.json")):
        cells.append(json.loads(p.read_text(encoding="utf-8")))
    return manifest, cells


def latest_runid() -> str:
    dirs = sorted(
        (p for p in RESULTS_DIR.iterdir() if p.is_dir() and (p / "manifest.json").exists()),
        key=lambda p: p.stat().st_mtime,
    )
    if not dirs:
        raise SystemExit(f"no results in {RESULTS_DIR}")
    return dirs[-1].name


def group_by_cell(cells: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """{(task_id, condition): [cell, ...]} - one list per (T*, baseline|leveraged)."""
    g: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cells:
        g[(c["task"], c["condition"])].append(c)
    return g


def aggregate(cells: list[dict]) -> dict:
    """Median/min/max across a list of cell dicts."""
    totals = [c["tokens"]["total"] for c in cells if not c.get("is_error")]
    costs = [c["total_cost_usd"] for c in cells if not c.get("is_error")]
    durs = [c["duration_ms"] for c in cells if not c.get("is_error")]
    quality = [c["quality_pass"] for c in cells if not c.get("is_error")]
    if not totals:
        return {"n": 0}
    return {
        "n": len(cells),
        "n_ok": len(totals),
        "tokens_median": int(statistics.median(totals)),
        "tokens_min": min(totals),
        "tokens_max": max(totals),
        "cost_median": statistics.median(costs),
        "cost_min": min(costs),
        "cost_max": max(costs),
        "duration_median": int(statistics.median(durs)),
        "quality_pass_count": sum(quality),
        "quality_total": len(quality),
        "quality_rate": sum(quality) / len(quality) if quality else 0.0,
    }


def median_run_quality(cells: list[dict]) -> bool:
    """Pick the run whose total_tokens is closest to the median, return its quality_pass."""
    ok = [c for c in cells if not c.get("is_error")]
    if not ok:
        return False
    totals = [c["tokens"]["total"] for c in ok]
    med = statistics.median(totals)
    closest = min(ok, key=lambda c: abs(c["tokens"]["total"] - med))
    return bool(closest["quality_pass"])


def tier_breakdown(cells: list[dict]) -> dict[str, int]:
    """Sum tokens per tier across cells - legacy interface, kept for callers
    that want raw token counts. Prefer tier_cost_breakdown for charting."""
    tiers = {"opus": 0, "sonnet": 0, "haiku": 0, "cache_read": 0, "other": 0}
    for c in cells:
        if c.get("is_error"):
            continue
        mu = c.get("model_usage") or {}
        cache_read = 0
        for model_id, u in mu.items():
            m = model_id.lower()
            if "opus" in m:
                bucket = "opus"
            elif "sonnet" in m:
                bucket = "sonnet"
            elif "haiku" in m:
                bucket = "haiku"
            else:
                bucket = "other"
            inp = int(u.get("inputTokens", 0) or 0)
            out = int(u.get("outputTokens", 0) or 0)
            ccreate = int(u.get("cacheCreationInputTokens", 0) or 0)
            cread = int(u.get("cacheReadInputTokens", 0) or 0)
            tiers[bucket] += inp + out + ccreate
            cache_read += cread
        tiers["cache_read"] += cache_read
    return tiers


def tier_cost_breakdown(cells: list[dict]) -> dict[str, float]:
    """Sum USD cost per tier from stream-json modelUsage[m].costUSD.

    Cache reads are NOT a separate tier here - they're already folded into
    each model's costUSD by Anthropic's pricing (cache_read is just cheap
    input). Charting cost-per-tier this way avoids the visual lie where
    cache_read tokens dominate the bar despite being ~5% of cost.
    """
    tiers = {"opus": 0.0, "sonnet": 0.0, "haiku": 0.0, "other": 0.0}
    for c in cells:
        if c.get("is_error"):
            continue
        mu = c.get("model_usage") or {}
        for model_id, u in mu.items():
            m = model_id.lower()
            if "opus" in m:
                bucket = "opus"
            elif "sonnet" in m:
                bucket = "sonnet"
            elif "haiku" in m:
                bucket = "haiku"
            else:
                bucket = "other"
            tiers[bucket] += float(u.get("costUSD", 0) or 0.0)
    return tiers


# ---------------------------------------------------------------------------
# Hero chart
# ---------------------------------------------------------------------------

def render_hero(manifest: dict, cells: list[dict], out_path: Path) -> dict:
    """Horizontal grouped bar chart: baseline vs leveraged per task (by USD cost).

    USD cost is the relevant comparison axis - raw token count understates the
    impact because cache_creation tokens cost ~3x more than cache_read tokens.
    The result.total_cost_usd from stream-json already collapses these costs
    using Anthropic's published per-model rates.

    Returns the rows used (for embedding in report.md). Tokens are also
    surfaced in the row dict for the per-task table.
    """
    apply_style()
    grouped = group_by_cell(cells)

    # Build per-task rows.
    tasks = sorted({k[0] for k in grouped})
    rows = []
    for tid in tasks:
        bl = aggregate(grouped.get((tid, "baseline"), []))
        lv = aggregate(grouped.get((tid, "leveraged"), []))
        if bl.get("n_ok", 0) == 0 or lv.get("n_ok", 0) == 0:
            continue
        # Headline metric = USD cost.
        bm = bl["cost_median"]
        lm = lv["cost_median"]
        savings = (bm - lm) / bm if bm else 0.0
        task_name = next((c["task_name"] for c in cells if c["task"] == tid), tid)
        rows.append({
            "task": tid,
            "task_name": task_name,
            "baseline_median": bm,
            "baseline_min": bl["cost_min"],
            "baseline_max": bl["cost_max"],
            "leveraged_median": lm,
            "leveraged_min": lv["cost_min"],
            "leveraged_max": lv["cost_max"],
            # Secondary: tokens for the per-task table.
            "baseline_tokens_median": bl["tokens_median"],
            "leveraged_tokens_median": lv["tokens_median"],
            "savings": savings,
            "quality_pass": median_run_quality(grouped[(tid, "leveraged")]),
        })

    if not rows:
        # Empty chart placeholder.
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "no completed runs yet", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        fig.savefig(out_path)
        plt.close(fig)
        return {"rows": []}

    # Sort by savings descending (best on top).
    rows.sort(key=lambda r: -r["savings"])

    fig, ax = plt.subplots(figsize=(10, max(3, 1.2 * len(rows) + 1.2)))

    y_positions = np.arange(len(rows))
    bar_h = 0.36

    for i, r in enumerate(rows):
        # Baseline bar (top of each group).
        y_bl = y_positions[i] + bar_h / 2
        ax.barh(y_bl, r["baseline_median"], height=bar_h, color=COLOR_BASELINE, zorder=3)
        # min-max whisker as a thin line through the bar tip.
        ax.errorbar(
            r["baseline_median"], y_bl,
            xerr=[[r["baseline_median"] - r["baseline_min"]], [r["baseline_max"] - r["baseline_median"]]],
            fmt="none", ecolor=COLOR_BASELINE, capsize=3, alpha=0.6, zorder=4,
        )

        # Leveraged bar (bottom).
        y_lv = y_positions[i] - bar_h / 2
        ax.barh(y_lv, r["leveraged_median"], height=bar_h, color=COLOR_LEVERAGED, zorder=3)
        ax.errorbar(
            r["leveraged_median"], y_lv,
            xerr=[[r["leveraged_median"] - r["leveraged_min"]], [r["leveraged_max"] - r["leveraged_median"]]],
            fmt="none", ecolor=COLOR_LEVERAGED, capsize=3, alpha=0.6, zorder=4,
        )

        # Savings annotation at the longer of the two bars.
        anchor_x = max(r["baseline_max"], r["leveraged_max"])
        pct_txt = fmt_pct(-r["savings"])  # negative because lower=better. We show e.g. -42% as -42%.
        color = COLOR_SAVINGS_OK if r["savings"] > 0 else COLOR_REGRESSION
        # When savings positive (leveraged < baseline), show "-42%" as a SAVING.
        # When savings negative (leveraged > baseline), show "+18%" as a regression.
        if r["savings"] >= 0:
            annot = f"-{r['savings'] * 100:.0f}%"
        else:
            annot = f"+{-r['savings'] * 100:.0f}%"
        # Quality mark inline.
        qmark = MARK_PASS if r["quality_pass"] else MARK_FAIL
        qcolor = COLOR_SAVINGS_OK if r["quality_pass"] else COLOR_REGRESSION
        ax.text(
            anchor_x * 1.04, y_positions[i],
            f"{annot}   [{qmark}]",
            va="center", ha="left",
            color=color, fontsize=11, fontweight="bold",
        )
        # Override mark color with quality result (annotation color = savings sign).
        # The combined label keeps mark legible because the mark is in [] brackets.

    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{r['task']}  {r['task_name']}" for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("equivalent API cost  (USD per session, median across N runs)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.2f}"))
    n = manifest.get("n_runs", 3)
    pv = manifest.get("plugin_version", "?")
    ax.set_title(f"claude-leverage v{pv} - cost per task  (median, N={n}, whiskers = min-max range)")

    # Right-side x-axis padding for annotations.
    cur_xmax = ax.get_xlim()[1]
    ax.set_xlim(0, cur_xmax * 1.22)

    # Proper matplotlib legend with colored Patch handles. Place at the top
    # of the figure (above the chart) so it doesn't collide with the x-axis
    # label below or with annotations on the right.
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
    # Give the legend room at the bottom by reserving space.
    fig.subplots_adjust(bottom=0.20)

    fig.savefig(out_path)
    plt.close(fig)
    return {"rows": rows}


# ---------------------------------------------------------------------------
# Per-task chart (2x2 subplot grid: baseline vs leveraged with tier stack)
# ---------------------------------------------------------------------------

def render_per_task(manifest: dict, cells: list[dict], out_path: Path) -> None:
    """Per-task tier-stacked bars. Y axis is USD cost (headline metric).

    Stack heights are scaled so the total bar height equals the median cost;
    each segment's share within the bar matches its token-share of the model
    that produced it. This keeps the visual proportional to dollars (what the
    user cares about) while preserving the 'where did the work happen' story.
    """
    apply_style()
    grouped = group_by_cell(cells)
    tasks = sorted({k[0] for k in grouped})
    if not tasks:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "no completed runs yet", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        fig.savefig(out_path)
        plt.close(fig)
        return

    n = len(tasks)
    cols = 2 if n > 1 else 1
    rows = (n + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(11, 4.5 * rows))
    if rows == 1 and cols == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [axes]
    elif cols == 1:
        axes = [[a] for a in axes]

    tier_order = ["opus", "sonnet", "haiku"]

    for idx, tid in enumerate(tasks):
        r, c = idx // cols, idx % cols
        ax = axes[r][c]
        bl_cells = grouped.get((tid, "baseline"), [])
        lv_cells = grouped.get((tid, "leveraged"), [])
        if not bl_cells or not lv_cells:
            ax.set_axis_off()
            continue

        # Use USD cost as the y-axis (headline metric).
        bl_med = statistics.median([c["total_cost_usd"] for c in bl_cells if not c.get("is_error")])
        lv_med = statistics.median([c["total_cost_usd"] for c in lv_cells if not c.get("is_error")])
        bl_min = min(c["total_cost_usd"] for c in bl_cells if not c.get("is_error"))
        bl_max = max(c["total_cost_usd"] for c in bl_cells if not c.get("is_error"))
        lv_min = min(c["total_cost_usd"] for c in lv_cells if not c.get("is_error"))
        lv_max = max(c["total_cost_usd"] for c in lv_cells if not c.get("is_error"))

        # Tier cost breakdown (USD per model, no separate cache_read tier -
        # cache costs are already folded into each model's costUSD).
        bl_cost_tiers = tier_cost_breakdown(bl_cells)
        lv_cost_tiers = tier_cost_breakdown(lv_cells)
        # Normalize to median session by dividing by number of runs.
        bl_n = max(1, sum(1 for c in bl_cells if not c.get("is_error")))
        lv_n = max(1, sum(1 for c in lv_cells if not c.get("is_error")))
        bl_scaled = {k: v / bl_n for k, v in bl_cost_tiers.items()}
        lv_scaled = {k: v / lv_n for k, v in lv_cost_tiers.items()}

        x = [0, 1]
        labels = ["baseline", "leveraged"]
        bottom = [0.0, 0.0]
        for tier in tier_order:
            heights = [bl_scaled.get(tier, 0), lv_scaled.get(tier, 0)]
            if max(heights) <= 0:
                continue
            ax.bar(
                x, heights, bottom=bottom,
                color=TIER_COLORS[tier],
                edgecolor="white", linewidth=1.5,
                label=tier.replace("_", " "),
                width=0.55,
            )
            bottom = [bottom[0] + heights[0], bottom[1] + heights[1]]

        # min-max whiskers on the totals.
        ax.errorbar(
            0, bl_med, yerr=[[bl_med - bl_min], [bl_max - bl_med]],
            fmt="none", ecolor="#2D3748", capsize=4, alpha=0.7,
        )
        ax.errorbar(
            1, lv_med, yerr=[[lv_med - lv_min], [lv_max - lv_med]],
            fmt="none", ecolor="#2D3748", capsize=4, alpha=0.7,
        )

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
        ax.set_ylabel("equivalent API cost (USD)")
        task_name = next((c["task_name"] for c in cells if c["task"] == tid), tid)
        ax.set_title(f"{tid}  {task_name}", loc="left")
        ax.grid(True, axis="y")
        ax.set_axisbelow(True)

        # Quality + savings annotation.
        savings = (bl_med - lv_med) / bl_med if bl_med else 0.0
        savings_txt = (f"-{savings * 100:.0f}%" if savings >= 0 else f"+{-savings * 100:.0f}%")
        scolor = COLOR_SAVINGS_OK if savings > 0 else COLOR_REGRESSION
        q_pass = median_run_quality(lv_cells)
        qmark = MARK_PASS if q_pass else MARK_FAIL
        qcolor = COLOR_SAVINGS_OK if q_pass else COLOR_REGRESSION
        ax.text(
            0.98, 0.97,
            f"savings: {savings_txt}\nquality: [{qmark}]",
            transform=ax.transAxes,
            ha="right", va="top",
            fontsize=9,
            color=scolor,
            bbox={"facecolor": "white", "edgecolor": "#E2E8F0", "boxstyle": "round,pad=0.4"},
        )

    # Hide unused subplots.
    for idx in range(n, rows * cols):
        r, c = idx // cols, idx % cols
        axes[r][c].set_axis_off()

    # Shared legend at the bottom. Collect handles across ALL subplots and
    # dedupe by label, so tier colors used only in some subplots (e.g. Haiku
    # in T2 baseline via Explore, but not in T1) still appear in the legend.
    all_handles: dict[str, object] = {}
    for row_ax in axes:
        for ax in row_ax:
            h, l = ax.get_legend_handles_labels()
            for handle, label in zip(h, l):
                if label not in all_handles:
                    all_handles[label] = handle
    if all_handles:
        # Order by canonical tier order for visual consistency.
        canonical = ["opus", "sonnet", "haiku", "other"]
        ordered = [(lab, all_handles[lab]) for lab in canonical if lab in all_handles]
        labels_out, handles_out = zip(*[(lab, h) for lab, h in ordered]) if ordered else ([], [])
        fig.legend(
            list(handles_out), list(labels_out),
            loc="lower center", ncol=len(labels_out),
            bbox_to_anchor=(0.5, -0.02),
        )

    fig.suptitle(
        f"claude-leverage v{manifest.get('plugin_version','?')} - cost per task + tier breakdown  (median, N={manifest.get('n_runs',3)})",
        fontsize=13, fontweight="bold", y=1.0,
    )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def render_markdown(manifest: dict, cells: list[dict], hero_rows: list[dict], out_path: Path) -> None:
    grouped = group_by_cell(cells)
    tasks = sorted({k[0] for k in grouped})

    lines: list[str] = []
    pv = manifest.get("plugin_version", "?")
    cv = manifest.get("claude_code_version", "?")
    n = manifest.get("n_runs", 3)
    lines.append(f"# claude-leverage benchmark - {manifest.get('runid','?')}")
    lines.append("")
    lines.append(f"- Plugin version: **v{pv}**")
    lines.append(f"- Claude Code version: **{cv}**")
    lines.append(f"- Started: {manifest.get('started_at','?')}")
    lines.append(f"- Finished: {manifest.get('finished_at','?')}")
    lines.append(f"- N runs per (task x condition): **{n}**")
    lines.append(f"- Total cost (subscription tokens consumed): **${manifest.get('total_cost_usd_so_far', 0):.3f}**")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    if hero_rows:
        total_bl = sum(r["baseline_median"] for r in hero_rows)
        total_lv = sum(r["leveraged_median"] for r in hero_rows)
        overall = (total_bl - total_lv) / total_bl if total_bl else 0.0
        total_bl_tok = sum(r["baseline_tokens_median"] for r in hero_rows)
        total_lv_tok = sum(r["leveraged_tokens_median"] for r in hero_rows)
        tok_savings = (total_bl_tok - total_lv_tok) / total_bl_tok if total_bl_tok else 0.0
        sign_cost = "-" if overall >= 0 else "+"
        sign_tok = "-" if tok_savings >= 0 else "+"
        lines.append(
            f"Median **cost** summed across {len(hero_rows)} tasks: "
            f"baseline **${total_bl:.3f}** -> leveraged **${total_lv:.3f}**  "
            f"(**{sign_cost}{abs(overall)*100:.0f}%**)."
        )
        lines.append("")
        lines.append(
            f"Median **tokens** summed: "
            f"baseline **{fmt_tokens(total_bl_tok)}** -> leveraged **{fmt_tokens(total_lv_tok)}**  "
            f"({sign_tok}{abs(tok_savings)*100:.0f}%)."
        )
        lines.append("")
        lines.append("![hero](hero.png)")
        lines.append("")

    lines.append("## Per-task breakdown")
    lines.append("")
    lines.append("![per-task](per-task.png)")
    lines.append("")
    lines.append("| Task | Baseline cost | Leveraged cost | Cost savings | Tokens (b -> l) | Quality |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in hero_rows:
        q = MARK_PASS if r["quality_pass"] else MARK_FAIL
        sav = (f"-{r['savings']*100:.0f}%" if r["savings"] >= 0 else f"+{-r['savings']*100:.0f}%")
        lines.append(
            f"| {r['task']} {r['task_name']} | "
            f"${r['baseline_median']:.3f} (${r['baseline_min']:.3f}-${r['baseline_max']:.3f}) | "
            f"${r['leveraged_median']:.3f} (${r['leveraged_min']:.3f}-${r['leveraged_max']:.3f}) | "
            f"{sav} | "
            f"{fmt_tokens(r['baseline_tokens_median'])} -> {fmt_tokens(r['leveraged_tokens_median'])} | "
            f"[{q}] |"
        )
    lines.append("")

    lines.append("## Run-by-run detail")
    lines.append("")
    lines.append("| Cell | Tokens | Cost USD | Duration | Quality | Notes |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for c in sorted(cells, key=lambda c: c["cell"]):
        notes = []
        if c.get("is_error"):
            notes.append(f"error: {c.get('error_message','?')}")
        if c.get("timed_out"):
            notes.append("TIMEOUT")
        q = MARK_PASS if c.get("quality_pass") else MARK_FAIL
        lines.append(
            f"| {c['cell']} | {fmt_tokens(c['tokens']['total'])} | "
            f"${c['total_cost_usd']:.3f} | "
            f"{c['duration_ms']/1000:.1f}s | "
            f"[{q}] | {'; '.join(notes) if notes else ''} |"
        )
    lines.append("")
    lines.append("## What this does and does NOT measure")
    lines.append("")
    lines.append("- **Measured:** real token usage and equivalent API cost (USD) from `claude -p` stream-json `result` events, in headless sessions with isolated profiles.")
    lines.append("- **Not measured:** wall-clock end-user latency, statistical significance (N=3 is too small), realistic-suite coverage, multi-language fixtures.")
    lines.append("- **Baseline = vanilla Claude Code** (with its built-in `Explore`, `general-purpose`, `Plan`, `statusline-setup` agents). Not 'Opus alone with no agents'.")
    lines.append("- **Cold cache:** every session uses a fresh CLAUDE_CONFIG_DIR, so every session pays cache-creation cost. Warm-cache numbers would be lower for both conditions but not necessarily symmetrically.")
    lines.append("- **Quality gate:** each leveraged run is checked against a deterministic regex / git assertion. A run with `FAIL` is *included* in the table but flagged; if every leveraged run fails on a task, treat the savings number with extreme skepticism.")
    lines.append("")
    lines.append("Raw stream-json per cell: see `raw/`.")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    runid = sys.argv[1] if len(sys.argv) > 1 else latest_runid()
    out_dir = RESULTS_DIR / runid
    if not out_dir.exists():
        raise SystemExit(f"no such results dir: {out_dir}")
    manifest, cells = load_cells(runid)

    hero_path = out_dir / "hero.png"
    per_task_path = out_dir / "per-task.png"
    report_path = out_dir / "report.md"

    hero_info = render_hero(manifest, cells, hero_path)
    render_per_task(manifest, cells, per_task_path)
    render_markdown(manifest, cells, hero_info["rows"], report_path)
    print(f"wrote: {hero_path}")
    print(f"wrote: {per_task_path}")
    print(f"wrote: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
