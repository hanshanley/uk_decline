#!/usr/bin/env python3
"""Generate the UK-decline figures from the combined Europe dataset.

Reads ``data/europe_combined_wide.csv`` (produced by ``fetch_data.py``) and writes
PNGs to ``outputs/``. Styling deliberately mirrors the "Substack-style" theme used in
the pre1870_reapportionment_package figures (warm tan background, serif fonts, muted
palette, italic source note, no top/right spines).

Figures:
  - gdp_per_capita_ppp_over_time.png   UK vs European peers + EU-27, GDP/capita PPP
  - uk_gdp_relative_to_peers.png       UK GDP/capita as a share of the EU average and the US
  - median_disposable_income_pps.png   Median income (Eurostat PPS), UK ends ~2018
  - median_income_pip.png              PIP median income (2017 PPP $/day), UK to ~2021

Usage:
    python plot_uk_decline.py [--data data/europe_combined_wide.csv] [--out outputs]
"""

from __future__ import annotations

import argparse
import pathlib

import matplotlib

matplotlib.use("Agg")  # headless: no display required

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mtick
import pandas as pd

# ── Professional house style (shared vizstyle house style) ───────────────────
from vizstyle import (  # noqa: E402
    BG as SUBSTACK_BG, CARD as SUBSTACK_CARD, TEXT as SUBSTACK_TEXT,
    MUTED as SUBSTACK_MUTED, ACCENT as SUBSTACK_ACCENT, BLUE as SUBSTACK_BLUE,
    GOLD as SUBSTACK_GOLD, GREEN as SUBSTACK_GREEN, GRID as SUBSTACK_GRID,
    house_style,
)

house_style()

LABEL_STROKE = [pe.withStroke(linewidth=3.5, foreground="white")]

# UK is always the warm accent; peers use the cooler/earthy palette. The US (a key
# non-European peer) is near-black. Spain removed per request; US added.
PEERS = [
    ("United Kingdom", SUBSTACK_ACCENT, "-", 2.8),
    ("United States", SUBSTACK_TEXT, "-", 1.8),
    ("Germany", SUBSTACK_BLUE, "-", 1.8),
    ("France", SUBSTACK_GOLD, "-", 1.8),
    ("Italy", SUBSTACK_GREEN, "-", 1.8),
]
EU_WB = ("European Union", SUBSTACK_BLUE, "--", 2.0)                    # World Bank EU aggregate, for GDP
EU_EUROSTAT = ("European Union (27, 2020)", SUBSTACK_MUTED, "--", 1.6)  # Eurostat, income

# GDP per capita is shown in REAL, constant 2015 US$ (inflation-adjusted, market exchange
# rates — NOT PPP). World Bank series NY.GDP.PCAP.KD, which covers 1960+ so it reaches the
# 1970s. (PPP/Maddison series remain in the dataset but are not plotted.)
GDP_METRIC = "gdp_per_capita_real_usd"

SOURCE_GDP = ("Data: World Bank Group, World Development Indicators \u2014 GDP per capita in "
              "current US$ (NY.GDP.PCAP.CD) deflated by US CPI (FP.CPI.TOTL) to constant 2015 US$ "
              "(inflation-adjusted, market exchange rates).")
SOURCE_EUROSTAT = ("Data: Eurostat (European Commission), EU-SILC \u2014 median equivalised net "
                   "income, PPS (ilc_di03). UK series ends ~2018 (post-Brexit).")
SOURCE_PIP = ("Data: World Bank Group, Poverty and Inequality Platform \u2014 median income, "
              "real 2017 PPP $ per day. Multiply by 365 for an annual figure.")


def _series(df: pd.DataFrame, country: str, metric: str) -> pd.DataFrame:
    """Non-null (year, value) rows for one country/metric, sorted by year."""
    sub = df[(df["country"] == country) & df[metric].notna()]
    return sub[["year", metric]].sort_values("year")


def _source_note(fig, text: str, ha: str = "left") -> None:
    x = 0.01 if ha == "left" else 0.99
    fig.text(x, 0.01, text, ha=ha, fontsize=8, color=SUBSTACK_MUTED, style="italic")


def _end_label(ax, xs, ys, text: str, color: str) -> None:
    """Label a line at its final point (right side). Accepts any array-like."""
    xs, ys = list(xs), list(ys)
    if not xs:
        return
    ax.text(xs[-1] + 0.4, ys[-1], text, fontsize=10, fontweight="bold",
            color=color, va="center", ha="left", path_effects=LABEL_STROKE)


def _line_chart(df: pd.DataFrame, metric: str, title: str, ylabel: str, yfmt,
                source: str, filename: str, out: pathlib.Path, *,
                eu_agg: tuple | None = None, eu_label: str | None = None,
                scale: float = 1.0, source_ha: str = "left") -> None:
    """Draw a UK-vs-peers line chart for one metric and save it to ``out/filename``.

    ``eu_agg``/``eu_label`` optionally add an EU reference series (Eurostat
    ``EU_EUROSTAT`` for income). It is omitted for the GDP charts because the World
    Bank constant-US$ series has no EU aggregate here and we never synthesize one.
    ``scale``
    divides the values (e.g. 1000 to show GDP in 000s).
    """
    series = [*PEERS, eu_agg] if eu_agg is not None else list(PEERS)
    fig, ax = plt.subplots(figsize=(11, 6))
    plotted = False
    for country, color, ls, lw in series:
        s = _series(df, country, metric)
        if s.empty:
            continue
        plotted = True
        xs, ys = s["year"], s[metric] / scale
        label = eu_label if country.startswith("European Union") else country
        ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw, label=label,
                marker="o" if country == "United Kingdom" else None,
                markersize=5, markeredgecolor="white", markeredgewidth=1.0)

    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel(ylabel, labelpad=2)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(yfmt))
    ax.set_title(title, fontweight="bold", pad=14)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.02)
    if plotted:
        ax.legend(loc="upper left", frameon=False, labelcolor="linecolor", fontsize=10)
    _source_note(fig, source, ha=source_ha)
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.12)
    plt.savefig(out / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_uk_relative(df: pd.DataFrame, out: pathlib.Path) -> None:
    metric = GDP_METRIC  # real constant-US$ series (a country-vs-country ratio is inflation-invariant)
    # Start at 1990: the 1970s/80s market-FX swings are jagged noise; 1990 on is the clean
    # story (US overtakes the UK, Poland catches up) and covers Poland's full series.
    start = 1990
    uk = _series(df, "United Kingdom", metric).set_index("year")[metric]
    uk = uk[uk.index >= start]
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    # Each peer's GDP per capita as a % of the UK (UK = 100). Higher line = richer than the
    # UK; a rising line = catching up with / overtaking the UK.
    refs = [
        ("United States", SUBSTACK_TEXT, "-", 2.8, "United States"),
        ("Germany", SUBSTACK_BLUE, "-", 2.0, "Germany"),
        ("France", SUBSTACK_GOLD, "-", 2.0, "France"),
        ("European Union", SUBSTACK_MUTED, "--", 2.0, "EU average"),
        ("Poland", SUBSTACK_GREEN, "-", 2.0, "Poland"),
    ]
    for country, color, ls, lw, label in refs:
        ref = _series(df, country, metric).set_index("year")[metric]
        ratio = (ref / uk).dropna() * 100.0  # peer as % of the UK
        if ratio.empty:
            continue
        ax.plot(ratio.index, ratio.values, color=color, linewidth=lw, linestyle=ls)
        _end_label(ax, ratio.index, ratio.values, label, color)

    ax.axhline(100, color=SUBSTACK_ACCENT, linewidth=1.4, linestyle="-")
    ax.text(ax.get_xlim()[0], 102, "United Kingdom = 100", fontsize=9.5,
            color=SUBSTACK_ACCENT, style="italic", fontweight="bold", va="bottom")

    us = ((_series(df, "United States", metric).set_index("year")[metric] / uk).dropna() * 100)
    pl = ((_series(df, "Poland", metric).set_index("year")[metric] / uk).dropna() * 100)

    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("GDP per capita as % of the UK (UK = 100)", labelpad=2)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    # Centered title + centered subtitle (the subtitle carries the two turning-point facts,
    # so it stays aligned under the headline instead of drifting to a corner).
    ax.set_title("GDP per capita relative to the UK, 1990\u20132024",
                 fontweight="bold", pad=30)
    ax.text(0.5, 1.015,
            f"The US pulled ahead to {us.iloc[-1]:.0f}% of the UK, while Poland climbed "
            f"from {pl.iloc[0]:.0f}% to {pl.iloc[-1]:.0f}%",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=12, color=SUBSTACK_MUTED)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.04)
    _source_note(fig, SOURCE_GDP)
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.12)
    plt.savefig(out / "uk_gdp_relative_to_peers.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    root = pathlib.Path(__file__).resolve().parent.parent  # repo root (europe_data/..)
    p = argparse.ArgumentParser(description="Plot the UK-decline figures.")
    p.add_argument("--data", default=str(root / "data" / "europe_combined_wide.csv"))
    p.add_argument("--out", default=str(root / "outputs" / "gdp_income"))
    args = p.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.data)

    _line_chart(
        df, GDP_METRIC,
        "Real GDP per capita: the UK drew level with the US in 2007,\nthen fell behind \u2014 1970\u20132024",
        "Real GDP per capita (000s, constant 2015 US$)",
        lambda v, _: f"${v:.0f}k", SOURCE_GDP,
        "gdp_per_capita_real_over_time.png", out,
        eu_agg=EU_WB, eu_label="EU average", scale=1000.0, source_ha="left",
    )
    fig_uk_relative(df, out)
    _line_chart(
        df, "median_disposable_income",
        "Median disposable income (Eurostat, PPS): UK vs peers",
        "Median equivalised income (PPS)",
        lambda v, _: f"{v/1000:.0f}k", SOURCE_EUROSTAT,
        "median_disposable_income_pps.png", out,
        eu_agg=EU_EUROSTAT, eu_label="EU-27", source_ha="right",
    )
    _line_chart(
        df, "median_income_pip",
        "Median income (World Bank PIP, 2017 PPP $/day): UK vs peers",
        "Median income (2017 PPP $ per day)",
        lambda v, _: f"${v:.0f}", SOURCE_PIP,
        "median_income_pip.png", out,
        eu_agg=EU_EUROSTAT, eu_label="EU-27", source_ha="right",
    )

    print(f"Wrote figures to {out}/:")
    for png in sorted(out.glob("*.png")):
        print(f"  {png.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
