"""Shared figure helpers for the PPP charts.

Small pieces of layout that both :mod:`ppp_data.charts` and :mod:`ppp_data.tuition_ppp`
need — the themed pyplot handle, the wrapped source note, the centred subtitle, the axis
tidy-up, and right-hand end labels that do not sit on top of each other.
"""

from __future__ import annotations

import textwrap

from vizstyle import MUTED, house_style, white_stroke

# Characters per line in the source note. Figures are saved with ``bbox_inches="tight"``,
# so an unwrapped one-line note sets the figure width — these notes are long enough to have
# doubled it. Wrapping keeps every PPP figure about as wide as the existing charts.
NOTE_WRAP = 165


def themed_plt():
    """Return pyplot with the shared house style applied (idempotent)."""
    import matplotlib.pyplot as plt

    house_style()
    return plt


def note(*parts: str) -> str:
    """Join the source-note sentences and wrap them to :data:`NOTE_WRAP`."""
    return textwrap.fill(" ".join(p for p in parts if p), width=NOTE_WRAP)


def subtitle(ax, text: str) -> None:
    """The centred, muted one-liner under the title that carries the figure's key fact."""
    ax.text(0.5, 1.015, text, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=11.5, color=MUTED)


def tidy(ax, *, xlabel: str = "Year", ylabel: str = "") -> None:
    """Apply the house axis treatment: labels, horizontal grid, no tick marks."""
    ax.set_xlabel(xlabel, labelpad=2)
    ax.set_ylabel(ylabel, labelpad=2)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.04)


def span(*year_lists: list[int]) -> str:
    """An en-dashed year range covering every list given, e.g. ``1990-2025``.

    Derived from the data rather than written into the title, so the figures stay honest
    when the World Bank publishes another year.
    """
    years = [y for years in year_lists for y in years]
    return f"{min(years)}\u2013{max(years)}" if years else ""


def labelled_ends(ax, items: list[tuple[float, str, str]], *, min_gap: float,
                  x: float, fontsize: float = 10.5) -> None:
    """Draw right-hand end labels, nudged apart so near-identical values stay readable.

    ``items`` is ``(y_value, text, colour)``. Each label is placed at its true y where
    possible; where two series end within ``min_gap`` of each other, the lower label is
    pushed down just far enough to clear the one above.
    """
    placed: list[float] = []
    for value, text, colour in sorted(items, key=lambda item: -item[0]):
        y = value
        if placed and placed[-1] - y < min_gap:
            y = placed[-1] - min_gap
        placed.append(y)
        ax.text(x, y, f"  {text}", fontsize=fontsize, fontweight="bold", color=colour,
                va="center", ha="left", path_effects=white_stroke())
