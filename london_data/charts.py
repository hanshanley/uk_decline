"""House-style charts for the London GDP-concentration analysis.

Two figures, London highlighted in the terracotta accent:

  - ``london_share_of_uk_gdp.png``     — London's % of UK GDP over time (the capital's
    share has risen over the series; exact figures are computed from the data at runtime).
  - ``london_gdp_per_head_vs_uk.png``  — London GDP per head as an index (UK = 100),
    showing London sits well above the UK average, with the gap widening over time.

Styling comes from the shared :mod:`vizstyle` house style (warm Substack tan, serif type,
muted grid, London in the terracotta accent, italic ONS source note).
"""

from __future__ import annotations

import pathlib

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

import vizstyle as vs

_SOURCE = ("Data: Office for National Statistics (ONS), Regional economic activity by GDP, "
           "UK \u2014 GDP at current market prices, all ITL regions. London = ITL1 region.")


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _series(df: pd.DataFrame, region: str, metric: str) -> pd.DataFrame:
    return df[(df["region"] == region) & (df["metric"] == metric)].sort_values("year")


def _line_chart(df, metric, title, subtitle_fn, ylabel, filename, out_dir,
                *, y_formatter, ylim_fn, decorate, y_locator=None):
    """Shared London line chart: accent line, per-chart decoration, title + subtitle, save.

    ``subtitle_fn(y0, y1, yr0, yr1) -> str`` builds the takeaway line; ``ylim_fn(y)`` and
    ``decorate(ax, x, y)`` supply each chart's specifics (the rest is identical scaffolding).
    """
    vs.house_style()
    s = _series(df, "London", metric)
    if s.empty:
        return None
    x, y = s["year"], s["value"]
    y0, y1 = y.iloc[0], y.iloc[-1]
    yr0, yr1 = int(x.iloc[0]), int(x.iloc[-1])

    fig, ax = plt.subplots(figsize=(11, 6))
    decorate(ax, x, y)
    ax.plot(x, y, color=vs.ACCENT, linewidth=2.8)

    ax.set_title(title, pad=30)
    ax.text(0.5, 1.015, subtitle_fn(y0, y1, yr0, yr1),
            transform=ax.transAxes, ha="center", va="bottom", fontsize=12, color=vs.MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel(ylabel, labelpad=2)
    if y_locator is not None:
        ax.yaxis.set_major_locator(y_locator)
    ax.yaxis.set_major_formatter(y_formatter)
    ax.set_ylim(*ylim_fn(y))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.04)
    vs.source_note(fig, _SOURCE)
    return vs.save_fig(fig, pathlib.Path(out_dir) / filename)


def _chart_share(df, out_dir):
    def decorate(ax, x, y):
        ax.fill_between(x, y, y.min() - 0.5, color=vs.ACCENT, alpha=0.08)
        for xi, yi, ha in ((x.iloc[0], y.iloc[0], "right"), (x.iloc[-1], y.iloc[-1], "left")):
            ax.plot([xi], [yi], "o", color=vs.ACCENT, markersize=6)
            label = f"  {yi:.1f}%" if ha == "left" else f"{yi:.1f}%  "
            ax.text(xi, yi, label, fontsize=11, fontweight="bold", color=vs.ACCENT,
                    va="center", ha=ha, path_effects=vs.white_stroke())

    return _line_chart(
        df, "share_of_uk_gdp_pct",
        "London's share of UK GDP",
        lambda y0, y1, yr0, yr1:
            f"The capital's slice of national output rose from {y0:.1f}% to {y1:.1f}% "
            f"({yr0}\u2013{yr1})",
        "London GDP as % of UK GDP",
        "london_share_of_uk_gdp.png", out_dir,
        y_formatter=mtick.FuncFormatter(lambda v, _p: f"{v:.0f}%"),
        y_locator=mtick.MultipleLocator(1),  # integer % ticks (no duplicate labels)
        ylim_fn=lambda y: (y.min() - 0.5, y.max() + 0.6),
        decorate=decorate,
    )


def _chart_per_head(df, out_dir):
    def decorate(ax, x, y):
        ax.axhline(100, color=vs.BLUE, linewidth=1.6, linestyle="--")
        vs.end_label(ax, x.iloc[-1], 100, "UK average = 100", vs.BLUE)
        vs.end_label(ax, x.iloc[-1], y.iloc[-1], f"{y.iloc[-1]:.0f}", vs.ACCENT, fontsize=11)

    return _line_chart(
        df, "gdp_per_head_index_uk100",
        "London GDP per head vs the UK average",
        lambda y0, y1, yr0, yr1:
            f"London output per person widened from {y0/100:.2f}\u00d7 to {y1/100:.2f}\u00d7 "
            f"the UK average ({yr0}\u2013{yr1})",
        "GDP per head (index, UK = 100)",
        "london_gdp_per_head_vs_uk.png", out_dir,
        y_formatter=mtick.FuncFormatter(lambda v, _p: f"{v:.0f}"),
        # floor just below the UK=100 reference; headroom above the peak.
        ylim_fn=lambda y: (min(95, y.min() - 5), y.max() + 8),
        decorate=decorate,
    )


def make_charts(source, out_dir="outputs/london") -> list[pathlib.Path]:
    df = _load(source)
    written = []
    for fn in (_chart_share, _chart_per_head):
        p = fn(df, out_dir)
        if p:
            written.append(p)
    return written
