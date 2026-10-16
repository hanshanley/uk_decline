"""Five distinct spending measures; gaps and source-method breaks stay visible."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from ppp_data.figure import labelled_ends
from ppp_data.peers import POLAND
from vizstyle import ACCENT, BG, MUTED, TEXT, house_style, save_chart, with_year_gaps

from . import sources

CHARTS = (
    (
        sources.TRANSPORT, "inland_transport_investment.png",
        "Inland transport infrastructure investment",
        "Roads, rail and inland waterways; all financing sources",
        "Source: OECD / International Transport Forum, Transport infrastructure indicators. "
        "Published inland investment as a share of GDP; new construction and improvements, "
        "not maintenance or all infrastructure. National coverage differs; compare trends with caution. "
        "Country series stop at their last supplied observation; missing years are not filled.",
    ),
    (
        sources.CAPITAL, "public_capital_investment.png", "Public capital investment",
        "General-government gross fixed capital formation; before depreciation",
        "Source: OECD National Accounts, general-government P51G / same-year nominal GDP (B1GQ). "
        "Numerator and denominator use the same national currency and year; no exchange-rate conversion. "
        "Includes buildings, equipment, weapons systems and capitalised R&D: not infrastructure alone. "
        "Excludes public corporations; not public-sector net investment.",
    ),
    (
        sources.BUDGET, "government_research_funding.png", "Government research funding",
        "Budget allocations for civil and defence R&D; not actual expenditure",
        "Sources: OECD GBARD totals / same-year nominal OECD GDP; EU-27: Eurostat gba_nabsfin07 "
        "published GDP share. EU means member-government budgets, not the EU institutions' budget. "
        "US series is federal budget authority. Fiscal reporting periods differ; dividing by calendar-year "
        "GDP is an annual comparison, not an exact fiscal-year match. Excludes R&D tax relief.",
    ),
    (
        sources.RESEARCH, "total_research_spending.png", "Total research and development spending",
        "R&D performed across the economy; all funding sectors",
        "Source: OECD Main Science and Technology Indicators, GERD as a share of GDP. "
        "Businesses, universities, government and non-profits; includes foreign funding of domestic R&D, "
        "not domestic funding of research abroad. OECD-flagged definition breaks are not joined "
        "(including UK breaks in 2014 and 2018). Not a government funding total or a pure science budget.",
    ),
    (
        sources.MILITARY, "military_expenditure.png", "Military expenditure",
        "SIPRI-based calendar-year expenditure; not NATO budget estimates or spending targets",
        "Source: SIPRI Military Expenditure Database via World Bank WDI, MS.MIL.XPND.GD.ZS. "
        "Published nominal military expenditure / nominal GDP; no currency conversion applied. "
        "EU is the World Bank's published aggregate, not an unweighted country average. "
        "Includes military R&D, so these five charts are not additive. Estimates may be revised.",
    ),
)
STYLES = {
    "GBR": (ACCENT, "-", 2.8), "USA": (TEXT, "-", 1.9),
    "EU27_2020": (MUTED, "--", 2.0), "EUU": (MUTED, "--", 2.0),
    "POL": (POLAND.colour, POLAND.linestyle, POLAND.linewidth),
}


def make_charts(frame: pd.DataFrame, output: Path) -> list[Path]:
    frame = sources.validate(frame)
    house_style()
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for metric, filename, title, subtitle, source in CHARTS:
        data = frame[frame["metric"] == metric]
        first, last = int(data["year"].min()), int(data["year"].max())
        fig, ax = plt.subplots(figsize=(13.5, 7.8))
        ends = []
        for code, (color, linestyle, width) in STYLES.items():
            part = data[data["iso3"] == code].sort_values("year")
            if part.empty:
                continue
            annual = with_year_gaps(
                part.set_index("year")["value"],
                breaks=part.loc[part["status"].str.split(";").map(lambda codes: "B" in codes), "year"],
            )
            country = sources.COUNTRIES[code]
            ax.plot(annual.index, annual.values, color=color, linestyle=linestyle, linewidth=width,
                    marker="o", markersize=3.2, label=country)
            latest = part.iloc[-1]
            status = f"; {latest['status'].replace(';', ',')}" if latest["status"] else ""
            ends.append((
                float(latest["value"]),
                f"{country} {latest['value']:.2f}%\n  {int(latest['year'])}{status}", color,
            ))
        ymax = max(data["value"].max() * 1.18, 0.1)
        ax.set_ylim(0, ymax)
        labelled_ends(ax, ends, min_gap=ymax * .085, x=last + .35, fontsize=10.5)
        ax.set_xlim(first - .4, last + .35)
        ticks = list(range(first, last + 1, 5))
        if last - ticks[-1] >= 3:
            ticks.append(last)
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:.0f}"))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
        ax.set_xlabel("Year")
        ax.set_ylabel("Share of GDP (%)")
        ax.grid(axis="y", linewidth=.5)
        ax.set_axisbelow(True)
        fig.suptitle(f"{title}, {first}\u2013{last}", x=.085, y=.97, ha="left",
                     fontsize=21, fontweight="bold")
        fig.text(.085, .905, subtitle, fontsize=11, color=MUTED)
        if metric == sources.TRANSPORT and "EU27_2020" not in set(data["iso3"]):
            source += " No comparable EU aggregate is supplied; none is synthesised."
        source += (
            " End labels give each series' own latest year. E = estimated, P = provisional, "
            "D = definition differs, B = series break; source flags are retained in the CSV. "
            "Gaps and flagged breaks are not bridged."
        )
        fig.text(.085, .02, textwrap.fill(source, width=150), va="bottom",
                 fontsize=8.5, color=MUTED, style="italic")
        fig.subplots_adjust(left=.085, right=.78, bottom=.23, top=.84)
        path = output / filename
        save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
        plt.close(fig)
        paths.append(path)
    return paths
