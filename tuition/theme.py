"""Substack-style plotting theme, matching the pre1870_reapportionment_package figures.

Palette and rcParams are copied from that project's scripts/generate_figures.py so the
tuition figures share the same look (background, serif font, muted grid, italic source
notes, bold titles). Import :func:`apply` before plotting.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless: no display required
import matplotlib.pyplot as plt

# ── Substack-style theme (matches pre1870_reapportionment_package) ──────────
BG = "#FFFFFF"
CARD = "#F3F4F6"
TEXT = "#111827"
MUTED = "#6B7280"
ACCENT = "#C0392B"
BLUE = "#1F5C99"
GOLD = "#D19000"
GREEN = "#2A9D8F"
GRID = "#E5E7EB"

RC_PARAMS = {
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": GRID,
    "grid.color": GRID,
    "grid.alpha": 1.0,
    "grid.linewidth": 0.9,
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 12,
    "axes.titlesize": 16,
    "axes.labelsize": 13,
    "figure.titlesize": 18,
    "legend.framealpha": 0.0,
    "legend.fontsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


def apply() -> None:
    """Apply the shared Substack theme to matplotlib's global rcParams."""
    plt.rcParams.update(RC_PARAMS)


def source_note(fig, text: str, x: float = 0.01, y: float = 0.01, ha: str = "left") -> None:
    """Add the standard italic, muted source note used across the project's figures."""
    fig.text(x, y, text, ha=ha, fontsize=8, color=MUTED, style="italic")
