"""Separate overall and youth unemployment charts, with EU and US references."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from ppp_data.figure import labelled_ends
from vizstyle import BG, MUTED, TEXT, country_color, house_style, save_chart

from . import references
from .sources import SERIES, validate


def period_label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    if start.year == end.year:
        return f"{start:%b}-{end:%b %Y}"
    return f"{start:%b %Y}-{end:%b %Y}"


def make_charts(frame: pd.DataFrame, out: Path, reference_frame: pd.DataFrame) -> list[Path]:
    frame = validate(frame)
    reference_frame = references.validate(reference_frame)
    out.mkdir(parents=True, exist_ok=True)
    house_style()
    outputs = []
    for metric, title, filename in (
        ("unemployment_rate", "Unemployment: UK, EU and US", "uk_unemployment.png"),
        ("youth_unemployment_rate", "Youth unemployment: UK, EU and US", "uk_youth_unemployment.png"),
    ):
        uk = frame.loc[frame["metric"] == metric]
        peers = reference_frame.loc[reference_frame["metric"] == metric]
        fig, ax = plt.subplots(figsize=(12.5, 7), facecolor=BG)
        ends = []
        for country, part, color, style in (
            ("UK", uk, country_color("UK"), "-"),
            ("EU", peers.loc[peers["country"] == "EU"], country_color("EU"), "--"),
            ("US", peers.loc[peers["country"] == "US"], country_color("US"), "-"),
        ):
            part = part.sort_values("date")
            last = part.iloc[-1]
            values = part.set_index("date")["value"]
            values = values.reindex(pd.date_range(values.index.min(), values.index.max(), freq="MS"))
            age = last["age_group"]
            ax.plot(
                values.index, values, color=color, linewidth=2.7 if country == "UK" else 1.8,
                linestyle=style, label=f"{country} ({age})",
                marker="o", markersize=3.5, markevery=[len(values) - 1], markeredgewidth=0,
            )
            period = (
                period_label(last["period_start"], last["period_end"])
                if country == "UK" else f"{last['date']:%b %Y}"
            )
            ends.append((
                float(last["value"]), f"{country} {last['value']:.1f}%\n  {period}", color,
                mdates.date2num(last["date"]),
            ))
        dates = pd.concat([uk["date"], peers["date"]])
        label_date = dates.max() + pd.DateOffset(months=3)
        ax.set_xlim(dates.min(), label_date)
        ymax = max(1, max(uk["value"].max(), peers["value"].max()) * 1.15)
        ax.set_ylim(0, ymax)
        labelled_ends(ax, ends, min_gap=ymax * .10, x=mdates.date2num(label_date), fontsize=10)
        ax.set_ylabel("Unemployment rate (%)")
        ax.set_xlabel("Year")
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="x", visible=False)
        ax.grid(axis="y", visible=True)
        ax.set_axisbelow(True)
        fig.suptitle(title, x=.10, y=.98, ha="left", fontsize=22, color=TEXT, fontweight="bold")
        fig.text(
            .10, .91, "Seasonally adjusted; UK: rolling three months; EU and US: monthly",
            fontsize=11, color=MUTED,
        )
        code = SERIES[metric][0]
        ages = (
            "UK and US: ages 16+; EU: ages 15-74."
            if metric == "unemployment_rate" else
            "UK and US: ages 16-24; EU: ages 15-24. Includes students seeking and available for work."
        )
        note = (
            f"Source: Office for National Statistics (ONS LFS, {code}); "
            "Eurostat une_rt_m (EU); US Bureau of Labor Statistics via Eurostat (US). "
            f"{ages} EU is the fixed 27-country aggregate, excluding the UK. "
            "Rates use each age group's labour force (employed + unemployed), not its whole population. "
            "UK points use the centre month; line-end labels show the full reference period. "
            "National definitions and reference periods differ; UK estimates overlap and are subject to survey uncertainty. "
            "Missing observations are not filled; the US October 2025 gap reflects the federal shutdown."
        )
        fig.text(.10, .025, textwrap.fill(note, width=150), fontsize=8, color=MUTED, style="italic")
        fig.subplots_adjust(left=.10, right=.77, bottom=.23, top=.85)
        path = out / filename
        save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
        plt.close(fig)
        outputs.append(path)
    return outputs
