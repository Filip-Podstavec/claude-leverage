"""Shared matplotlib style for benchmark charts.

Single source of truth for colors, fonts, rcParams. Imported by report.py
and per_agent_report.py so the hero, per-task, and scatter charts look
consistent.

Palette is deliberately muted - no green-equals-savings marketing inflation.
Slate gray (baseline) and muted blue (leveraged) read as "neutral compare",
not "before/after Instagram filter".
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# Colors. Hex picked to render clearly on both light and dark GitHub themes.
COLOR_BASELINE = "#4A5568"      # slate gray
COLOR_LEVERAGED = "#2B6CB0"     # muted blue
COLOR_SAVINGS_OK = "#2F855A"    # muted green (only for the savings % annotation)
COLOR_REGRESSION = "#C53030"    # muted red (negative savings, quality fail)

# Tier colors for stacked per-task chart.
TIER_COLORS = {
    "opus": "#6B46C1",          # muted purple
    "sonnet": "#2B6CB0",        # muted blue (same as leveraged accent)
    "haiku": "#2F855A",         # muted green
    "cache_read": "#A0AEC0",    # neutral gray-blue (signals "free")
    "other": "#718096",         # mid-gray for anything else
}

# Quality marks.
MARK_PASS = "OK"
MARK_FAIL = "FAIL"


def apply_style() -> None:
    """Apply rcParams. Called once before any plotting."""
    mpl.rcParams.update({
        "font.family": "sans-serif",
        # Arial / Helvetica fall through DejaVu on Linux; on Windows Arial is native.
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "x",
        "grid.color": "#E2E8F0",
        "grid.linewidth": 0.8,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.dpi": 200,
    })


def fmt_tokens(n: int | float) -> str:
    """Format a token count for axis ticks and annotations.

    Compact: 123 -> '123', 1234 -> '1.2k', 1234567 -> '1.2M'.
    """
    n = int(n)
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def fmt_pct(p: float) -> str:
    """Signed percent, no decimals for cleanliness in chart annotations."""
    sign = "+" if p > 0 else ""
    return f"{sign}{p * 100:.0f}%"
