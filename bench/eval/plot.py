"""Generate paired bar chart for the A/B benchmark.

Output: bench/eval/results.png (committed alongside this script).

Re-run after adding new datapoints:
    python bench/eval/plot.py
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

# Opus 4.7 runs on the endpoint-implementation task.
# One run dropped (network instability during benchmark) — see bench/eval/README.md.
RUNS = [
    ("Run 7\n(pure A/B)",       23.35, 21.21),
    ("Run 9\n(artifact-only)",  29.98, 12.97),
    ("Run 11\n(artifact-only)", 18.42, 11.78),
    ("Run 12\n(artifact-only)", 20.09, 18.18),
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
    "claude-leverage A/B: cost per run, Claude Opus 4.7\n"
    "endpoint-implementation task on a ~30k LOC Python codebase"
)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylim(0, max(before.max(), after.max()) + 6)
ax.legend(loc="upper right", fontsize=8.5, framealpha=0.95)
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig("bench/eval/results.png", dpi=180, bbox_inches="tight")
print("wrote bench/eval/results.png")
