"""House-style charts for the London GDP-concentration analysis.

Two figures, London highlighted in the terracotta accent:

  - ``london_share_of_uk_gdp.png``     — London's % of UK GDP over time (the capital's
    share has risen over the series; exact figures are computed from the data at runtime).
  - ``london_gdp_per_head_vs_uk.png``  — London GDP per head as an index (UK = 100),
    showing London sits well above the UK average, with the gap widening over time.

Styling matches the sibling analyses (warm Substack tan, serif type, muted grid, London in
the terracotta accent, italic ONS source note).
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

BG = "#F7F5F0"
TEXT = "#1A1A1A"
MUTED = "#6B6B6B"
GRID = "#D6D3CC"
ACCENT = "#C85A3D"   # London (focus)
BLUE = "#3D6F8C"     # UK reference

_THEME = {
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT, "axes.labelcolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8,
    "grid.color": GRID, "grid.alpha": 0.6, "grid.linewidth": 0.5,
    "font.family": "serif", "font.size": 12,
    "axes.titlesize": 17, "axes.titleweight": "bold", "axes.labelsize": 12,
    "legend.framealpha": 0.0, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.major.size": 0, "ytick.major.size": 0, "text.parse_math": False,
}
_STROKE = [pe.withStroke(linewidth=3.0, foreground="white")]
_SOURCE = ("Data: Office for National Statistics (ONS), Regional economic activity by GDP, "
           "UK \u2014 GDP at current market prices, all ITL regions. London = ITL1 region.")


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _series(df: pd.DataFrame, region: str, metric: str) -> pd.DataFrame:
    sub = df[(df["region"] == region) & (df["metric"] == metric)].copy()
    return sub.sort_values("year")


def _finish(fig, ax, out_dir, filename):
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.04)
    fig.text(0.01, 0.01, _SOURCE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout(pad=0.6)
    plt.subplots_adjust(bottom=0.12)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _chart_share(df, out_dir):
    plt.rcParams.update(_THEME)
    s = _series(df, "London", "share_of_uk_gdp_pct")
    if s.empty:
        return None
    x, y = s["year"], s["value"]
    y0, y1 = y.iloc[0], y.iloc[-1]
    yr0, yr1 = int(x.iloc[0]), int(x.iloc[-1])

    fig, ax = plt.subplots(figsize=(11, 6))
    baseline = min(19, y.min() - 0.5)
    ax.plot(x, y, color=ACCENT, linewidth=2.8)
    ax.fill_between(x, y, baseline, color=ACCENT, alpha=0.08)
    for xi, yi in ((x.iloc[0], y0), (x.iloc[-1], y1)):
        ax.plot([xi], [yi], "o", color=ACCENT, markersize=6)
    ax.text(x.iloc[-1], y1, f"  {y1:.1f}%", fontsize=11, fontweight="bold",
            color=ACCENT, va="center", ha="left", path_effects=_STROKE)
    ax.text(x.iloc[0], y0, f"{y0:.1f}%  ", fontsize=11, fontweight="bold",
            color=ACCENT, va="center", ha="right", path_effects=_STROKE)

    ax.set_title("London's share of UK GDP", pad=30)
    ax.text(0.5, 1.015,
            f"The capital's slice of national output rose from {y0:.1f}% to {y1:.1f}% "
            f"({yr0}\u2013{yr1})",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("London GDP as % of UK GDP", labelpad=2)
    ax.yaxis.set_major_locator(mtick.MultipleLocator(1))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.set_ylim(baseline, y.max() + 0.6)
    return _finish(fig, ax, out_dir, "london_share_of_uk_gdp.png")


def _chart_per_head(df, out_dir):
    plt.rcParams.update(_THEME)
    s = _series(df, "London", "gdp_per_head_index_uk100")
    if s.empty:
        return None
    x, y = s["year"], s["value"]
    y0, y1 = y.iloc[0], y.iloc[-1]
    yr0, yr1 = int(x.iloc[0]), int(x.iloc[-1])

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axhline(100, color=BLUE, linewidth=1.6, linestyle="--")
    ax.text(x.iloc[-1], 100, "  UK average = 100", fontsize=10.5, color=BLUE,
            va="center", ha="left", path_effects=_STROKE)
    ax.plot(x, y, color=ACCENT, linewidth=2.8)
    ax.text(x.iloc[-1], y1, f"  {y1:.0f}", fontsize=11, fontweight="bold",
            color=ACCENT, va="center", ha="left", path_effects=_STROKE)

    ax.set_title("London GDP per head vs the UK average", pad=30)
    ax.text(0.5, 1.015,
            f"London output per person widened from {y0/100:.2f}x to {y1/100:.2f}x the "
            f"UK average ({yr0}\u2013{yr1})",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("GDP per head (index, UK = 100)", labelpad=2)
    ax.set_ylim(90, max(y.max() * 1.05, 180))
    return _finish(fig, ax, out_dir, "london_gdp_per_head_vs_uk.png")


def make_charts(source, out_dir="outputs/london") -> list[pathlib.Path]:
    df = _load(source)
    written = []
    for fn in (_chart_share, _chart_per_head):
        p = fn(df, out_dir)
        if p:
            written.append(p)
    return written
