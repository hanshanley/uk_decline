"""Four-country household energy and industrial electricity price comparisons."""

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from ppp_data.figure import labelled_ends
from vizstyle import BG, MUTED, TEXT, country_color, house_style, save_chart

from .sources import COUNTRIES, INDUSTRIAL_EIA, INDUSTRIAL_TABLES, validate


def make_charts(frame: pd.DataFrame, out: Path, *, industrial: bool = False) -> list[Path]:
    frame = validate(frame, industrial=industrial)
    out.mkdir(parents=True, exist_ok=True)
    house_style()
    paths = []
    for fuel in (INDUSTRIAL_TABLES if industrial else ("electricity", "gas")):
        selected = frame.loc[frame["fuel"] == fuel]
        first, last = int(selected["year"].min()), int(selected["year"].max())
        fig, ax = plt.subplots(figsize=(12.5, 7), facecolor=BG)
        ends = []
        for code, name in COUNTRIES.items():
            part = selected.loc[selected["iso3"] == code].sort_values("year")
            color = country_color(code)
            ax.plot(part["year"], part["value"], label=name, color=color,
                    linewidth=2.8 if code == "GBR" else 1.8, marker="o", markersize=3)
            final = part.iloc[-1]
            ends.append((final["value"], f"{name}\n{final['value']:.2f}p/kWh ({last})", color, last))
        ax.set_xlim(first - .5, last + .25)
        ymax = selected["value"].max() * 1.18
        ax.set_ylim(0, ymax)
        ax.set_xlabel("Year")
        ax.set_ylabel(f"{'Industrial/business' if industrial else 'Household'} retail price (pence per kWh)")
        ax.set_xticks(range(first, last + 1, 2))
        ax.tick_params(axis="x", pad=12)
        ax.tick_params(axis="y", pad=8)
        ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:g}p"))
        ax.grid(axis="y", visible=True)
        ax.grid(axis="x", visible=False)
        ax.set_axisbelow(True)
        labelled_ends(ax, ends, min_gap=ymax * .13, x=last + .25, fontsize=9.5)
        fig.suptitle(f"{'Industrial' if industrial else 'Household'} {fuel} prices: UK, US, Germany and France",
                     x=.10, y=.98, ha="left", fontsize=20, color=TEXT, fontweight="bold")
        scope = (
            "UK/Europe: medium non-household users; US: industrial sector"
            if industrial else "UK/Europe: medium-use households; US: all residential customers"
        )
        fig.text(.10, .91, f"{first}\u2013{last} | {scope}",
                 fontsize=10.5, color=MUTED)
        source = (
            "Sources: DESNZ/Eurostat QEP 5.4, medium non-household users (2,000-19,999 MWh/year); "
            "includes non-recoverable taxes/levies but excludes VAT and other recoverable taxes/levies. "
            f"US EIA {INDUSTRIAL_EIA['electricity'][1]}, national industrial retail rates including taxes, not wholesale. "
            if industrial else
            f"Sources: DESNZ/Eurostat QEP {'5.6' if fuel == 'electricity' else '5.10'} "
            "(UK, Germany, France), tax-inclusive medium-household rates; "
            f"US EIA {'ESRCUUS' if fuel == 'electricity' else 'NGRCUUS'}, national residential rates, not wholesale. "
        )
        note = source + (
            "European annual prices average both half-years; US prices are EIA's published annual rates. "
            "European sterling conversions follow DESNZ; US prices use World Bank annual GBP/USD. "
            "Prices include delivery/fixed bill costs on the sources' unit-price basis, unlike variable-only tariffs. "
            "Consumption profiles and averaging conventions differ: this is not a matched-usage tariff comparison. "
            "Support-scheme accounting follows each source; these are not net bills after all cash transfers. "
            "Current-price sterling, not inflation- or purchasing-power-adjusted; exchange rates affect comparisons."
        )
        if fuel == "gas":
            note += (
                " US gas is converted from cubic feet using annual EIA end-use heat content "
                "(approximate gross-energy basis); US consumer sales taxes may be incompletely reported."
            )
        flagged = selected.loc[selected["status"].ne("")]
        if not flagged.empty:
            note += " Source flags: " + ", ".join(
                f"{row.country} {int(row.year)} {'provisional' if row.status == 'p' else 'revised'}"
                for row in flagged.itertuples()
            ) + "."
        fig.text(.10, .025, textwrap.fill(note, width=150), fontsize=7.8, color=MUTED, style="italic")
        fig.subplots_adjust(left=.10, right=.73, bottom=.28, top=.85)
        path = out / f"{'industrial' if industrial else 'household'}_{fuel}_prices.png"
        save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
        plt.close(fig)
        paths.append(path)
    return paths
