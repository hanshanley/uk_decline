"""Compare overall and youth unemployment; retain separate exports for reference."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, MUTED, TEXT, house_style

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
    styles = {
        "unemployment_rate": ("Overall (16+)", BLUE),
        "youth_unemployment_rate": ("Youth (16-24)", ACCENT),
    }
    for metrics, title, ages, filename in (
        (
            tuple(SERIES), "UK unemployment: overall and youth",
            "Overall ages 16+; youth ages 16-24", "uk_unemployment_comparison.png",
        ),
        (("unemployment_rate",), "UK unemployment", "Aged 16 and over", "uk_unemployment.png"),
        (("youth_unemployment_rate",), "UK youth unemployment", "Aged 16-24", "uk_youth_unemployment.png"),
    ):
        data = frame.loc[frame["metric"].isin(metrics)]
        latest = data.sort_values("date").iloc[-1]
        label = period_label(latest["period_start"], latest["period_end"])
        combined = len(metrics) > 1
        fig, ax = plt.subplots(figsize=(12.5, 7), facecolor=BG)
        latest_values = []
        for metric in metrics:
            part = data.loc[data["metric"] == metric].sort_values("date")
            last = part.iloc[-1]
            values = part.set_index("date")["value"]
            values = values.reindex(pd.date_range(values.index.min(), values.index.max(), freq="MS"))
            name, color = styles[metric]
            color = color if combined else ACCENT
            ax.plot(values.index, values, color=color, linewidth=2.5, label=name)
            ax.scatter([last["date"]], [last["value"]], color=color, s=25, zorder=4)
            latest_values.append(f"{name.split(' (')[0]}: {last['value']:.1f}%")
        ax.set_xlim(data["date"].min(), latest["date"] + pd.DateOffset(months=3))
        ax.set_ylim(0, max(1, data["value"].max() * 1.18))
        ax.set_ylabel("Unemployed / economically active (%)")
        ax.set_xlabel("Centre month of each three-month estimate")
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="x", visible=False)
        if combined:
            ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=11)
        fig.suptitle(title, x=.10, y=.98, ha="left", fontsize=22, color=TEXT, fontweight="bold")
        fig.text(
            .10, .91,
            f"{ages}; seasonally adjusted three-month survey estimates",
            fontsize=11, color=MUTED,
        )
        summary = " | ".join(latest_values) if combined else f"{latest['value']:.1f}%"
        fig.text(
            .10, .855, f"Latest: {label} | {summary}",
            fontsize=14, color=TEXT if combined else ACCENT,
        )
        codes = ", ".join(SERIES[metric][0] for metric in metrics)
        note = (
            f"Source: Office for National Statistics, Labour Force Survey "
            f"({codes}); released {latest['release_date']:%d %b %Y}. "
            "Economically active = employed + unemployed; this is not the share of "
            "all people without work. Adjacent estimates overlap. "
        )
        if combined:
            note += "Each rate uses its own age group; overall includes young people. "
        if "youth_unemployment_rate" in metrics:
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
