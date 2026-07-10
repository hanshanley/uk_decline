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

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BLUE, MUTED, TEXT, house_style, source_note

LONDON = "London and South East"
GB = "Great Britain"

house_style()


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


def _chart(df, metric, title, subtitle, ylabel, filename, out_dir):
    lon = _maa(df, LONDON, metric)
    gb = _maa(df, GB, metric)
    if lon.empty or gb.empty:
        return None

    fig, ax = plt.subplots(figsize=(11, 6))
    line_style = {
        "marker": "o",
        "markevery": 4,
        "markersize": 4.2,
        "markeredgecolor": "white",
        "markeredgewidth": 0.8,
        "linewidth": 2.4,
    }
    ax.plot(gb["date"], gb["maa"], color=BLUE, label="Great Britain", **line_style)
    ax.plot(lon["date"], lon["maa"], color=ACCENT, label="London & South East", **line_style)

    ax.set_title(title, fontweight="bold", pad=18)
    ax.text(0.5, 1.01, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10.5, color=MUTED)
    ax.set_xlabel("Period", labelpad=4)
    ax.set_ylabel(ylabel, labelpad=4)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.035)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 0.98),
        ncol=2,
        frameon=False,
        labelcolor=TEXT,
        columnspacing=1.8,
        handlelength=2.0,
    )
    fig.autofmt_xdate(rotation=30, ha="right")
    source_note(
        fig,
        "Source: Office of Rail and Road (ORR), Data Portal Table 3103. "
        "London & South East is a trains-weighted sector aggregate.",
    )
    fig.tight_layout(rect=[0, 0.055, 1, 1], pad=0.7)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(source, out_dir="outputs/rail") -> list[pathlib.Path]:
    df = _load(source)
    written = []
    p = _chart(
        df, "casl_pct",
        "Rail disruption \u2014 London & South East",
        "Cancelled or significantly late trains, 4-quarter moving average",
        "Share of trains (%)\n(higher = worse)",
        "rail_london_casl.png", out_dir,
    )
    if p:
        written.append(p)
    p = _chart(
        df, "ppm_pct",
        "Rail punctuality \u2014 London & South East",
        "Public Performance Measure (PPM), 4-quarter moving average",
        "Trains meeting PPM (%)",
        "rail_london_ppm.png", out_dir,
    )
    if p:
        written.append(p)
    return written
