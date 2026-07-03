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
BG = "#F7F5F0"
CARD = "#EFEDE8"
TEXT = "#1A1A1A"
MUTED = "#6B6B6B"
ACCENT = "#C85A3D"
BLUE = "#3D6F8C"
GOLD = "#C2993E"
GREEN = "#4A7C59"
GRID = "#D6D3CC"

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
    "grid.alpha": 0.6,
    "grid.linewidth": 0.5,
    "font.family": "serif",
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
