"""Mock figure generator for the HKSTP proposal deck.

ALL DATA IS SYNTHETIC. The figures illustrate what the Tochka agent platform
produces; numbers are not from BOCHK or any real source. Each figure carries
"Illustrative — synthetic data" in the footer so this is unambiguous to a
reader. Generated once, then read by docs/decks/build.mjs and embedded into
both PPTX decks.

Run:
    python docs/figures_gen.py

Output:
    docs/figures/fig_01_coverage_gaps.png
    docs/figures/fig_02_queue_pressure.png
    docs/figures/fig_03_wealth_affinity.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import RegularPolygon

# Aino-inspired palette (matches frontend/lib/cartography.ts).
PAPER = "#f6f4ef"
INK = "#1a1a1a"
MUTED = "#6b6760"
ACCENT = "#0f5ea8"
WARM = "#e07a5f"
WARN = "#c44536"
GOOD = "#3a7d44"

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Arial", "Helvetica", "DejaVu Sans"],
    "axes.facecolor": PAPER,
    "figure.facecolor": PAPER,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlecolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _stamp(fig: plt.Figure) -> None:
    fig.text(
        0.5, 0.015,
        "Illustrative — synthetic data, not real BOCHK figures",
        ha="center", va="bottom", color=MUTED, fontsize=8, style="italic",
    )


def fig_coverage_gaps() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
    rng = np.random.default_rng(7)

    rows, cols = 12, 22
    hex_size = 0.5
    centers: list[tuple[float, float]] = []
    densities: list[float] = []
    for r in range(rows):
        for c in range(cols):
            x = c * hex_size * 1.7 + (r % 2) * hex_size * 0.85
            y = r * hex_size * 1.5
            d = (
                np.exp(-((x - 9) ** 2 + (y - 5) ** 2) / 8) * 1.0
                + np.exp(-((x - 15) ** 2 + (y - 7.5) ** 2) / 12) * 0.7
                + np.exp(-((x - 4) ** 2 + (y - 3) ** 2) / 15) * 0.5
                + rng.normal(0, 0.07)
            )
            centers.append((x, y))
            densities.append(max(0.0, min(1.2, float(d))))

    cmap = LinearSegmentedColormap.from_list("warmpaper", [PAPER, WARM, WARN])
    hexes = [RegularPolygon(c, numVertices=6, radius=hex_size, orientation=np.pi / 6) for c in centers]
    pc = PatchCollection(hexes, cmap=cmap, edgecolor="white", linewidth=0.4)
    pc.set_array(np.array(densities))
    pc.set_clim(0, 1.2)
    ax.add_collection(pc)

    branch_xy = np.array([
        (4, 4), (6, 5), (8, 3), (10, 2), (12, 4), (14, 5),
        (5, 8), (7, 9), (9, 10), (11, 10.5), (16.5, 5.5), (18.5, 4),
    ])
    ax.scatter(branch_xy[:, 0], branch_xy[:, 1], s=85, c=ACCENT, marker="o",
               edgecolors="white", linewidths=1.5, zorder=5)

    gap1 = patches.Ellipse((15.5, 8.5), 5.0, 3.5, fill=False, edgecolor=WARN,
                           linewidth=2.4, linestyle="--", zorder=4)
    gap2 = patches.Ellipse((2.5, 5.5), 3.5, 2.7, fill=False, edgecolor=WARN,
                           linewidth=2.4, linestyle="--", zorder=4)
    ax.add_patch(gap1)
    ax.add_patch(gap2)
    ax.annotate(
        "Gap A — 47K residents,\n0 branches in 10-min walk",
        xy=(15.5, 8.5), xytext=(16.5, 11.8), color=WARN, fontsize=10, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=WARN, lw=1.2),
    )
    ax.annotate(
        "Gap B — 28K residents,\n1 distant branch",
        xy=(2.5, 5.5), xytext=(-1.0, 8.0), color=WARN, fontsize=10, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=WARN, lw=1.2),
    )

    ax.set_xlim(-2.5, 22)
    ax.set_ylim(-0.5, 13.5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.set_title("Coverage gaps in the BOCHK branch network",
                 fontsize=16, fontweight="bold", pad=10, loc="left")

    ax.scatter([], [], s=85, c=ACCENT, edgecolors="white", linewidths=1.5, label="BOCHK branch")
    ax.plot([], [], color=WARN, linewidth=2.4, linestyle="--", label="Coverage gap")
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=INK)

    fig.text(0.05, 0.06,
             "Population density (warm hexes) overlaid with branch locations (blue dots). Dashed ellipses mark high-density areas underserved by the current 10-minute-walk catchment.",
             color=MUTED, fontsize=9.5, style="italic", wrap=True)

    _stamp(fig)
    plt.subplots_adjust(top=0.92, bottom=0.14, left=0.04, right=0.98)
    plt.savefig(OUT / "fig_01_coverage_gaps.png", dpi=150, facecolor=PAPER)
    plt.close()


def fig_queue_pressure() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.3), dpi=150)
    branches = [
        "Sham Shui Po", "Cheung Sha Wan", "Lai Chi Kok", "Mei Foo",
        "Mong Kok", "Yau Ma Tei", "TST", "Central",
        "Causeway Bay", "North Point", "Quarry Bay", "Tsing Yi",
    ]
    capacity = np.array([180] * 12)
    queue = np.array([220, 165, 145, 130, 245, 215, 195, 175, 235, 155, 140, 195])

    x = np.arange(len(branches))
    width = 0.4
    ax.bar(x - width / 2, capacity, width, color=MUTED, alpha=0.45,
           label="Capacity (customers/hour)")
    over = queue > capacity
    colors = [WARN if o else ACCENT for o in over]
    ax.bar(x + width / 2, queue, width, color=colors, label="Peak-hour load")

    for i, (q, c) in enumerate(zip(queue, capacity, strict=False)):
        if q > c:
            ax.text(i + width / 2, q + 6, f"+{q - c}",
                    ha="center", color=WARN, fontweight="bold", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(branches, rotation=32, ha="right", fontsize=10, color=INK)
    ax.set_ylabel("customers / hour", color=MUTED, fontsize=10)
    ax.set_ylim(0, 290)
    ax.spines["left"].set_color(MUTED)
    ax.set_title("Peak-hour queue load vs branch capacity",
                 fontsize=16, fontweight="bold", pad=10, loc="left")
    ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=INK)

    fig.text(0.05, 0.04,
             "Same staffing model across branches, very different load. Red bars exceed capacity — narrative hook for differential staffing or capacity rebalancing.",
             color=MUTED, fontsize=9.5, style="italic", wrap=True)

    _stamp(fig)
    plt.subplots_adjust(top=0.91, bottom=0.30, left=0.07, right=0.97)
    plt.savefig(OUT / "fig_02_queue_pressure.png", dpi=150, facecolor=PAPER)
    plt.close()


def fig_wealth_affinity() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=150)
    rng = np.random.default_rng(42)

    clusters = [
        ("Premium",   ACCENT, (8.0, 9.0), 1.0, 22),
        ("Growth",    GOOD,   (5.5, 6.2), 0.9, 28),
        ("Mature",    WARM,   (3.0, 4.0), 0.8, 28),
        ("Periphery", MUTED,  (1.4, 2.2), 0.7, 32),
    ]

    for name, color, center, spread, n in clusters:
        xs = rng.normal(center[0], spread * 0.95, n)
        ys = rng.normal(center[1], spread * 0.75, n)
        sizes = rng.uniform(40, 140, n)
        ax.scatter(xs, ys, s=sizes, c=color, alpha=0.55,
                   edgecolors="white", linewidths=0.6)
        ax.text(center[0] + 0.25, center[1] + 1.3, name, color=color,
                fontweight="bold", fontsize=12)

    ax.set_xlabel("Premium POI density (private clubs, specialty hospitals, intl schools / km²)",
                  color=MUTED, fontsize=10)
    ax.set_ylabel("Avg transaction value (HK$, log scale)", color=MUTED, fontsize=10)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines["bottom"].set_color(MUTED)
    ax.spines["left"].set_color(MUTED)
    ax.set_xlim(-1, 11)
    ax.set_ylim(0, 12)
    ax.set_title("Spatial wealth segmentation by neighbourhood",
                 fontsize=16, fontweight="bold", pad=10, loc="left")

    fig.text(0.05, 0.04,
             "POI affinity score against customer transaction value reveals four spatial segments. The Premium cluster correlates strongly with private clubs and international schools — fed by the SiteSense-derived POI parser.",
             color=MUTED, fontsize=9.5, style="italic", wrap=True)

    _stamp(fig)
    plt.subplots_adjust(top=0.91, bottom=0.20, left=0.07, right=0.97)
    plt.savefig(OUT / "fig_03_wealth_affinity.png", dpi=150, facecolor=PAPER)
    plt.close()


if __name__ == "__main__":
    fig_coverage_gaps()
    fig_queue_pressure()
    fig_wealth_affinity()
    print(f"Generated 3 figures to {OUT}")
