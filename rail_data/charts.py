"""House-style charts for the London rail-performance analysis.

Two figures, both London-highlighted against a Great Britain reference, drawn as a
4-quarter moving average (the standard way to read seasonal rail stats):

  - ``rail_london_casl.png`` — Cancellations & Significant Lateness (the disruption
    story: it has roughly doubled since the late 2000s).
  - ``rail_london_ppm.png``  — Public Performance Measure ("on time"), which has stayed
    broadly flat, i.e. the lenient headline hides the deterioration above.

Styling matches the sibling analyses (warm Substack tan, serif type, muted grid, UK/London
in the terracotta accent, italic source note).
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
BLUE = "#3D6F8C"     # Great Britain (context)

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

LONDON = "London and South East"
GB = "Great Britain"


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _maa(df: pd.DataFrame, region: str, metric: str) -> pd.DataFrame:
    """4-quarter moving average for one region/metric, indexed by mid-quarter date."""
    sub = df[(df["region"] == region) & (df["metric"] == metric)].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    sub = sub.sort_values("date")
    sub["maa"] = sub["value"].rolling(4, min_periods=4).mean()
    return sub.dropna(subset=["maa"])


def _end_label(ax, xs, ys, text, color):
    ax.text(xs.iloc[-1], ys.iloc[-1], f"  {text}", fontsize=10.5, fontweight="bold",
            color=color, va="center", ha="left", path_effects=_STROKE)


def _chart(df, metric, title, subtitle, ylabel, filename, out_dir, *, annotate_2007=None):
    plt.rcParams.update(_THEME)
    lon = _maa(df, LONDON, metric)
    gb = _maa(df, GB, metric)
    if lon.empty:
        return None

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(gb["date"], gb["maa"], color=BLUE, linewidth=1.8, label="Great Britain")
    ax.plot(lon["date"], lon["maa"], color=ACCENT, linewidth=2.8, label="London & South East")
    _end_label(ax, gb["date"], gb["maa"], "Great Britain", BLUE)
    _end_label(ax, lon["date"], lon["maa"], "London & SE", ACCENT)

    if annotate_2007 is not None:
        row07 = lon[lon["date"].dt.year == 2007]
        if not row07.empty:
            y07 = row07["maa"].iloc[-1]
            ylast = lon["maa"].iloc[-1]
            ax.annotate(annotate_2007.format(y07=y07, ylast=ylast),
                        xy=(row07["date"].iloc[-1], y07), xytext=(0.42, 0.80),
                        textcoords="axes fraction", fontsize=11, color=MUTED,
                        ha="center",
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, alpha=0.6))

    ax.set_title(title, fontweight="bold", pad=30)
    ax.text(0.5, 1.015, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel(ylabel, labelpad=2)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.05)
    fig.text(0.01, 0.01,
             "Data: Office of Rail and Road (ORR) Data Portal, Table 3103 (PPM & CaSL by "
             "operator). London & South East = trains-weighted sector aggregate.",
             ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.12)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(source, out_dir="outputs/rail") -> list[pathlib.Path]:
    df = _load(source)
    written = []
    p = _chart(
        df, "casl_pct",
        "Trains cancelled or significantly late \u2014 London & South East",
        "Serious disruption has roughly doubled since the late 2000s",
        "% of trains cancelled or significantly late (higher = worse)",
        "rail_london_casl.png", out_dir,
        annotate_2007="{y07:.1f}% in 2007, now {ylast:.1f}%",
    )
    if p:
        written.append(p)
    p = _chart(
        df, "ppm_pct",
        "Trains 'on time' (PPM) \u2014 London & South East",
        "The lenient headline punctuality measure has stayed broadly flat",
        "% of trains on time (PPM)",
        "rail_london_ppm.png", out_dir,
    )
    if p:
        written.append(p)
    return written
