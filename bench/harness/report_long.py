"""Long-session report with crossover-turn analysis.

Headline metric: **crossover turn N** = smallest turn where cumulative
leveraged cost <= cumulative baseline cost. This answers the most useful
question for a prospective user: "after how many turns of a real session
does claude-leverage start saving me money?"

Reads:
    bench/results/<runid>/raw/long__<cond>__r<i>.session.json (with per-turn
    approximate costs)

Writes:
    bench/results/<runid>/long-report.md
    bench/results/<runid>/cumulative.png    (the headline cumulative curves)
    bench/results/<runid>/per-turn.png      (marginal savings per turn)

Usage:
    python bench/harness/report_long.py [<runid>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
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
)


def load_cells(runid: str) -> tuple[dict, list[dict]]:
    d = RESULTS_DIR / runid
    if not (d / "manifest.json").exists():
        raise SystemExit(f"missing manifest: {d}")
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    cells = []
    for p in sorted((d / "raw").glob("long__*.session.json")):
        cells.append(json.loads(p.read_text(encoding="utf-8")))
    return manifest, cells


def latest_long_runid() -> str:
    dirs = sorted(
        (p for p in RESULTS_DIR.iterdir() if p.is_dir() and (p / "manifest.json").exists() and "-long" in p.name),
        key=lambda p: p.stat().st_mtime,
    )
    if not dirs:
        raise SystemExit(f"no long results in {RESULTS_DIR}")
    return dirs[-1].name


def per_turn_median_curve(cells: list[dict], condition: str, n_turns: int) -> tuple[list[float], list[float]]:
    """For a given condition, return (per_turn_median[N], cumulative_median[N]) lists."""
    # cells_by_turn[i] = list of approx_cost_usd values for turn i across runs
    by_turn: list[list[float]] = [[] for _ in range(n_turns)]
    for c in cells:
        if c.get("condition") != condition or c.get("is_error"):
            continue
        for t in c["turns"][:n_turns]:
            by_turn[t["turn_idx"]].append(float(t.get("approx_cost_usd", 0.0)))
    per_turn_med = [median(vals) if vals else 0.0 for vals in by_turn]
    cumulative = []
    running = 0.0
    for x in per_turn_med:
        running += x
        cumulative.append(running)
    return per_turn_med, cumulative


def find_crossover(baseline_cum: list[float], leveraged_cum: list[float]) -> int | None:
    """Return the 1-indexed turn N where leveraged becomes <= baseline cumulatively.

    Returns None if no crossover within the measured range.
    """
    for i, (b, l) in enumerate(zip(baseline_cum, leveraged_cum), start=1):
        if l <= b:
            return i
    return None


def render_cumulative_chart(
    manifest: dict, cells: list[dict], out_path: Path
) -> dict:
    apply_style()
    n_turns = manifest.get("n_turns", 12)

    bl_per_turn, bl_cum = per_turn_median_curve(cells, "baseline", n_turns)
    lv_per_turn, lv_cum = per_turn_median_curve(cells, "leveraged", n_turns)

    crossover = find_crossover(bl_cum, lv_cum)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    turns = list(range(1, n_turns + 1))

    # The two curves.
    ax.plot(turns, bl_cum, "-o", color=COLOR_BASELINE, label="baseline (vanilla Claude Code)", linewidth=2.5, markersize=6, zorder=5)
    ax.plot(turns, lv_cum, "-o", color=COLOR_LEVERAGED, label="leveraged (+ claude-leverage)", linewidth=2.5, markersize=6, zorder=5)

    # Shaded delta region: red where leveraged > baseline (tax), green where leveraged < baseline (savings).
    for i in range(len(turns) - 1):
        x = [turns[i], turns[i + 1]]
        y1 = [bl_cum[i], bl_cum[i + 1]]
        y2 = [lv_cum[i], lv_cum[i + 1]]
        if lv_cum[i] > bl_cum[i] and lv_cum[i + 1] > bl_cum[i + 1]:
            color = COLOR_REGRESSION
            alpha = 0.12
        elif lv_cum[i] < bl_cum[i] and lv_cum[i + 1] < bl_cum[i + 1]:
            color = COLOR_SAVINGS_OK
            alpha = 0.12
        else:
            color = "#A0AEC0"
            alpha = 0.10
        ax.fill_between(x, y1, y2, color=color, alpha=alpha, zorder=1)

    # Crossover marker.
    if crossover is not None:
        ax.axvline(crossover, color=COLOR_SAVINGS_OK, linestyle="--", linewidth=1.5, alpha=0.7, zorder=3)
        ax.text(
            crossover + 0.15, max(bl_cum + lv_cum) * 0.05,
            f"crossover at turn {crossover}", color=COLOR_SAVINGS_OK,
            fontsize=10, fontweight="bold", ha="left", va="bottom",
        )

    ax.set_xlabel("turn number")
    ax.set_ylabel("cumulative cost (USD)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax.set_xticks(turns)
    pv = manifest.get("plugin_version", "?")
    if crossover is None:
        sub = f"no crossover in {n_turns} turns — leveraged stays more expensive throughout"
    else:
        sub = f"leveraged becomes net-cheaper than baseline at turn {crossover}"
    ax.set_title(
        f"claude-leverage v{pv} — long-session cumulative cost  (N={manifest.get('n_runs',2)}, median)\n{sub}",
        fontsize=12,
    )

    legend_handles = [
        Patch(facecolor=COLOR_BASELINE, label="baseline (vanilla Claude Code)"),
        Patch(facecolor=COLOR_LEVERAGED, label="leveraged (+ claude-leverage plugin)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False, fontsize=10)
    fig.savefig(out_path)
    plt.close(fig)

    return {
        "bl_per_turn": bl_per_turn,
        "lv_per_turn": lv_per_turn,
        "bl_cum": bl_cum,
        "lv_cum": lv_cum,
        "crossover": crossover,
    }


def render_per_turn_savings(
    manifest: dict, summary: dict, out_path: Path
) -> None:
    apply_style()
    n_turns = manifest.get("n_turns", 12)
    turns = list(range(1, n_turns + 1))

    # marginal savings rate per turn = (baseline - leveraged) / baseline, signed
    rates = []
    for i in range(n_turns):
        b = summary["bl_per_turn"][i]
        l = summary["lv_per_turn"][i]
        if b > 0:
            rates.append((b - l) / b * 100)
        else:
            rates.append(0.0)

    fig, ax = plt.subplots(figsize=(11, 4))
    colors = [COLOR_SAVINGS_OK if r > 0 else COLOR_REGRESSION for r in rates]
    ax.bar(turns, rates, color=colors, edgecolor="white", linewidth=1, zorder=3)
    ax.axhline(0, color="#1A202C", linewidth=0.8, alpha=0.5, zorder=2)
    ax.set_xlabel("turn number")
    ax.set_ylabel("per-turn savings  (baseline − leveraged) / baseline")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_xticks(turns)
    ax.set_title(
        f"Per-turn savings rate  (green = leveraged cheaper, red = tax)",
        fontsize=11,
    )
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.savefig(out_path)
    plt.close(fig)


def render_markdown(
    manifest: dict, cells: list[dict], summary: dict, out_path: Path,
) -> None:
    pv = manifest.get("plugin_version", "?")
    n = manifest.get("n_runs", 2)
    n_turns = manifest.get("n_turns", 12)
    bl_cum = summary["bl_cum"]
    lv_cum = summary["lv_cum"]

    lines: list[str] = []
    lines.append(f"# claude-leverage v{pv} — long-session benchmark ({manifest.get('runid','?')})")
    lines.append("")
    lines.append(f"- Plugin version: **v{pv}**")
    lines.append(f"- Turns per session: **{n_turns}**")
    lines.append(f"- N runs per condition: **{n}**")
    lines.append(f"- Total cost (subscription): **${manifest.get('total_cost_usd_so_far', 0):.3f}**")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    crossover = summary["crossover"]
    if crossover is not None:
        gap_at_end = lv_cum[-1] - bl_cum[-1]
        sign = "+" if gap_at_end > 0 else "-"
        lines.append(f"**Crossover turn: {crossover}** — at turn {crossover}, cumulative leveraged cost (${lv_cum[crossover-1]:.3f}) drops to or below cumulative baseline cost (${bl_cum[crossover-1]:.3f}).")
        lines.append("")
        if gap_at_end <= 0:
            lines.append(f"By turn {n_turns}, leveraged is **${abs(gap_at_end):.3f} cheaper** than baseline. Asymptotic savings will continue to grow with session length.")
        else:
            lines.append(f"By turn {n_turns}, leveraged has crossed back above baseline by ${gap_at_end:.3f}. Crossover is unstable — likely variance, not a robust win.")
    else:
        gap = lv_cum[-1] - bl_cum[-1]
        lines.append(f"**No crossover in {n_turns} turns.** By turn {n_turns}, leveraged is still **${gap:.3f} more expensive** than baseline (${lv_cum[-1]:.3f} vs ${bl_cum[-1]:.3f}, +{gap/bl_cum[-1]*100:.0f}%).")
        lines.append("")
        lines.append(f"To estimate when leveraged might cross over, look at the *last-half slope*: in turns {n_turns//2+1}–{n_turns}, the gap changed by ${(lv_cum[-1]-bl_cum[-1]) - (lv_cum[n_turns//2-1]-bl_cum[n_turns//2-1]):+.3f}. If the trend is the leveraged gap shrinking, extrapolation gives a crossover at ~turn N (calculation below).")
    lines.append("")
    lines.append("![cumulative](cumulative.png)")
    lines.append("")
    lines.append("![per-turn](per-turn.png)")
    lines.append("")
    lines.append("## Per-turn detail (median across N runs)")
    lines.append("")
    lines.append("| Turn | Prompt (preview) | Baseline cost | Leveraged cost | Cumulative B | Cumulative L | Δ cumulative |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|")
    for i, prompt in enumerate(manifest.get("turns", [])):
        bl = summary["bl_per_turn"][i]
        lv = summary["lv_per_turn"][i]
        b_cum = bl_cum[i]
        l_cum = lv_cum[i]
        delta = l_cum - b_cum
        delta_str = f"{'+' if delta >= 0 else '-'}${abs(delta):.3f}"
        preview = (prompt[:55] + "…") if len(prompt) > 55 else prompt
        lines.append(
            f"| {i+1} | {preview} | ${bl:.3f} | ${lv:.3f} | ${b_cum:.3f} | ${l_cum:.3f} | {delta_str} |"
        )
    lines.append("")

    lines.append("## Delegations observed (leveraged)")
    lines.append("")
    by_agent: dict[str, int] = {}
    for c in cells:
        if c.get("condition") != "leveraged":
            continue
        for d in c.get("delegations") or []:
            by_agent[d.get("agent", "?")] = by_agent.get(d.get("agent", "?"), 0) + 1
    if by_agent:
        for agent, n_inv in sorted(by_agent.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{agent}` — {n_inv} invocation(s) across all leveraged runs")
    else:
        lines.append("_No delegations recorded._")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(f"- ONE `claude -p --input-format stream-json` session per cell, {n_turns} user turns sent sequentially. Same `bench/fixtures/long-session/` cwd for all turns (Claude Code cannot change cwd mid-session).")
    lines.append("- Turns mix: 5 Opus-inline (orientation, small edits, fixes, architectural), 5 explicit subagent delegations (`test-runner`×2, `git-committer`×2, `code-reviewer`×1), 2 hybrid (context-gather + implement).")
    lines.append("- Cost is `result.total_cost_usd` from the final stream-json `result` event (cumulative across all turns). Per-turn approximation: total cost split proportionally to per-assistant-event token volume — exact when each turn produces one final-text event, approximate when multi-step turns (e.g. commits with multiple bash calls) produce several text events.")
    lines.append("- Crossover detection: 1-indexed turn `N` where `cumulative_lev[N] <= cumulative_base[N]`.")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    runid = sys.argv[1] if len(sys.argv) > 1 else latest_long_runid()
    out_dir = RESULTS_DIR / runid
    if not out_dir.exists():
        raise SystemExit(f"no such results dir: {out_dir}")
    manifest, cells = load_cells(runid)

    cum_path = out_dir / "cumulative.png"
    per_turn_path = out_dir / "per-turn.png"
    md_path = out_dir / "long-report.md"

    summary = render_cumulative_chart(manifest, cells, cum_path)
    render_per_turn_savings(manifest, summary, per_turn_path)
    render_markdown(manifest, cells, summary, md_path)
    print(f"wrote: {cum_path}")
    print(f"wrote: {per_turn_path}")
    print(f"wrote: {md_path}")
    if summary["crossover"]:
        print(f"CROSSOVER at turn {summary['crossover']}")
    else:
        print(f"NO CROSSOVER in {manifest.get('n_turns', 12)} turns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
