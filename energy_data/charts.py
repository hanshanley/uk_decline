"""Four-country retail electricity and gas prices with explicit scope caveats."""

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import pandas as pd

from ppp_data.figure import labelled_ends
from vizstyle import BG, MUTED, TEXT, country_color, house_style, save_chart

from .sources import COUNTRIES, validate


def make_charts(frame: pd.DataFrame, out: Path) -> list[Path]:
    frame = validate(frame)
    out.mkdir(parents=True, exist_ok=True)
    house_style()
    paths = []
    for fuel in ("electricity", "gas"):
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
        ax.set_xlim(first, last + .25)
        ymax = selected["value"].max() * 1.18
        ax.set_ylim(0, ymax)
        ax.set_xlabel("Year")
        ax.set_ylabel("Household retail price (pence per kWh)")
        ax.set_xticks(sorted({*range(first, last + 1, 2), last}))
        ax.grid(axis="y", visible=True)
        ax.grid(axis="x", visible=False)
        ax.set_axisbelow(True)
        labelled_ends(ax, ends, min_gap=ymax * .13, x=last + .25, fontsize=9.5)
        fig.suptitle(f"Household {fuel} prices: UK, US, Germany and France",
                     x=.10, y=.98, ha="left", fontsize=20, color=TEXT, fontweight="bold")
        fig.text(.10, .91, f"{first}\u2013{last} | UK/Europe: medium-use households; US: all residential customers",
                 fontsize=10.5, color=MUTED)
        note = (
            f"Sources: DESNZ/Eurostat QEP {'5.6' if fuel == 'electricity' else '5.10'} "
            "(UK, Germany, France), tax-inclusive medium-household rates; "
            f"US EIA {'ESRCUUS' if fuel == 'electricity' else 'NGRCUUS'}, national residential rates, not wholesale. "
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
        path = out / f"household_{fuel}_prices.png"
        save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
        plt.close(fig)
        paths.append(path)
    return paths
