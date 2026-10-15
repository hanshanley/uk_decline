"""Two clear views of unemployment, without mixing age groups or denominators."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from vizstyle import ACCENT, BG, MUTED, TEXT, house_style

from .sources import SERIES, validate


def period_label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    if start.year == end.year:
        return f"{start:%b}-{end:%b %Y}"
    return f"{start:%b %Y}-{end:%b %Y}"


def make_charts(frame: pd.DataFrame, out: Path) -> list[Path]:
    frame = validate(frame)
    out.mkdir(parents=True, exist_ok=True)
    house_style()
    outputs = []
    for metric, title, ages, filename in (
        ("unemployment_rate", "UK unemployment", "16 and over", "uk_unemployment.png"),
        ("youth_unemployment_rate", "UK youth unemployment", "16-24", "uk_youth_unemployment.png"),
    ):
        part = frame.loc[frame["metric"] == metric].sort_values("date")
        latest = part.iloc[-1]
        label = period_label(latest["period_start"], latest["period_end"])
        values = part.set_index("date")["value"]
        values = values.reindex(pd.date_range(values.index.min(), values.index.max(), freq="MS"))
        fig, ax = plt.subplots(figsize=(12.5, 7), facecolor=BG)
        ax.plot(values.index, values, color=ACCENT, linewidth=2.5)
        ax.scatter([latest["date"]], [latest["value"]], color=ACCENT, s=25, zorder=4)
        ax.set_xlim(values.index.min(), values.index.max() + pd.DateOffset(months=3))
        ax.set_ylim(0, max(1, values.max() * 1.18))
        ax.set_ylabel("Unemployed / economically active (%)")
        ax.set_xlabel("Centre month of each three-month estimate")
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="x", visible=False)
        fig.suptitle(title, x=.10, y=.98, ha="left", fontsize=22, color=TEXT, fontweight="bold")
        fig.text(
            .10, .91,
            f"Aged {ages}; seasonally adjusted three-month survey estimates",
            fontsize=11, color=MUTED,
        )
        fig.text(
            .10, .855, f"Latest: {label} | {latest['value']:.1f}%",
            fontsize=14, color=ACCENT,
        )
        note = (
            f"Source: Office for National Statistics, Labour Force Survey "
            f"({SERIES[metric][0]}); released {latest['release_date']:%d %b %Y}. "
            "Economically active = employed + unemployed; this is not the share of "
            "all people without work. Adjacent estimates overlap. "
        )
        if metric == "youth_unemployment_rate":
            note += "Includes students seeking and available for work. "
        note += (
            "Recent survey estimates are volatile; collection and weighting changes "
            "affect comparisons over time. Missing observations are not filled."
        )
        fig.text(.10, .025, textwrap.fill(note, width=150), fontsize=8, color=MUTED)
        fig.subplots_adjust(left=.10, right=.97, bottom=.21, top=.79)
        path = out / filename
        fig.savefig(path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
        plt.close(fig)
        outputs.append(path)
    return outputs
