"""Generate the expanding cost chart for the current plugin line.

Separate from plot.py (the frozen Opus 4.7 / n=5 dataset) so the headline
chart stays untouched while this one grows. Append to RUNS as more runs land.

Output: bench/eval/results-current.png

Re-run after adding a datapoint:
    python bench/eval/plot_current.py
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

# Claude Opus 4.8, plugin v1.11.0, endpoint-implementation task.
# Expanding dataset — append (label, before_usd, after_usd) as runs land.
RUNS = [
    ("Run 1\n(pure A/B)", 33.15, 17.45),
]

labels = [r[0] for r in RUNS]
before = np.array([r[1] for r in RUNS])
after = np.array([r[2] for r in RUNS])
mean_b, mean_a = before.mean(), after.mean()

x = np.arange(len(labels))
width = 0.38

fig, ax = plt.subplots(figsize=(8.5, 5))
ax.bar(x - width / 2, before, width, label="BEFORE", color="#9aa0a6")
ax.bar(x + width / 2, after, width, label="AFTER", color="#1a73e8")

ax.axhline(
    mean_b, color="#9aa0a6", linestyle=":", linewidth=1,
    label=f"mean BEFORE  ${mean_b:.2f}",
)
ax.axhline(
    mean_a, color="#1a73e8", linestyle=":", linewidth=1,
    label=f"mean AFTER   ${mean_a:.2f}",
)

for i, (b, a) in enumerate(zip(before, after)):
    ax.text(i - width / 2, b + 0.4, f"${b:.2f}", ha="center", fontsize=8.5)
    ax.text(i + width / 2, a + 0.4, f"${a:.2f}", ha="center", fontsize=8.5)
    delta = (a - b) / b * 100
    ax.text(
        i, max(b, a) + 2.2, f"Δ {delta:+.1f}%", ha="center",
        fontsize=8.5,
        color="#1a73e8" if delta < 0 else "#d93025",
        fontweight="bold",
    )

ax.set_ylabel("Run cost (USD)")
ax.set_title(
    "claude-leverage A/B: cost per run, Claude Opus 4.8 + plugin v1.11.0\n"
    f"endpoint-implementation task on a ~30k LOC Python codebase  (n={len(RUNS)}, expanding)"
)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
# Keep headroom on the right so the expanding dataset has room to grow visually.
ax.set_xlim(-0.6, max(len(labels) - 0.4, 4.6))
ax.set_ylim(0, max(before.max(), after.max()) + 6)
ax.text(
    0.99, 0.02, "dataset expands as more runs land",
    transform=ax.transAxes, ha="right", va="bottom",
    fontsize=8, style="italic", color="#5f6368",
)
ax.legend(loc="upper right", fontsize=8.5, framealpha=0.95)
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig("bench/eval/results-current.png", dpi=180, bbox_inches="tight")
print("wrote bench/eval/results-current.png")
