#!/usr/bin/env python3
"""Generate the UK-decline figures from the combined Europe dataset.

Reads ``data/europe_combined_wide.csv`` (produced by ``fetch_data.py``) and writes
PNGs to ``outputs/``. Styling deliberately mirrors the "Substack-style" theme used in
the pre1870_reapportionment_package figures (warm tan background, serif fonts, muted
palette, italic source note, no top/right spines).

Figures:
  - gdp_per_capita_real_over_time.png  National-accounts volumes, fixed-base dollars
  - gdp_per_capita_nominal_over_time.png  Nominal valuations at annual market FX
  - uk_gdp_relative_to_peers.png       Peer nominal GDP/capita as a share of the UK
  - uk_gdp_relative_to_peers_simple.png  US, EU and Poland only
  - median_disposable_income_pps.png   Median income (Eurostat PPS), UK ends ~2018
  - median_disposable_income_oecd.png  Median income (OECD, household-consumption PPP)
  - median_income_pip.png              PIP median income (2021 PPP $/day), UK to ~2021

Usage:
    python plot_uk_decline.py [--data data/europe_combined_wide.csv] [--out outputs]
"""

from __future__ import annotations

import argparse
import pathlib
import textwrap

import matplotlib

matplotlib.use("Agg")  # headless: no display required

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from europe_data import combine, oecd_income, pip
from ppp_data.figure import labelled_ends

# ── Professional house style (shared vizstyle house style) ───────────────────
from vizstyle import (  # noqa: E402
    BG as SUBSTACK_BG, CARD as SUBSTACK_CARD, TEXT as SUBSTACK_TEXT,
    MUTED as SUBSTACK_MUTED, ACCENT as SUBSTACK_ACCENT, BLUE as SUBSTACK_BLUE,
    GOLD as SUBSTACK_GOLD, GREEN as SUBSTACK_GREEN, GRID as SUBSTACK_GRID,
    house_style, with_year_gaps, save_chart,
)

house_style()

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

# Volume growth and current-dollar valuation are separate questions.
GDP_METRIC = "gdp_per_capita_constant_usd"
NOMINAL_GDP_METRIC = "gdp_per_capita_nominal_usd"

SOURCE_GDP = ("Data: World Bank Group, World Development Indicators \u2014 GDP per capita in "
              "constant 2015 US$ (NY.GDP.PCAP.KD), national-accounts volume measure. "
              "Fixed-base dollar conversion, not annual market exchange rates or purchasing power parity; compare growth, "
              "not domestic purchasing-power levels.")
SOURCE_NOMINAL_GDP = (
    "Data: World Bank, World Development Indicators \u2014 GDP per capita, current US$ (NY.GDP.PCAP.CD), "
    "at annual market exchange rates. Not inflation-adjusted: changes include output, "
    "GDP prices and exchange rates. GDP is not household income."
)
SOURCE_EUROSTAT = ("Data: Eurostat (European Commission), European Community Household Panel / "
                   "EU Statistics on Income and Living Conditions \u2014 median household-size-adjusted "
                   "net income, current purchasing power standards (ilc_di03). Survey year; income usually refers "
                   "to the preceding year, with country exceptions including the UK. "
                   "Missing years and flagged method breaks are not connected. UK ends 2018.")
SOURCE_PIP = ("Data: World Bank Group, Poverty and Inequality Platform \u2014 median "
              f"per-person income/consumption, {pip.PPP_VERSION} international dollars per day "
              "(purchasing power parity). Survey observations only; "
              "gaps and known survey/welfare-definition breaks are not connected. "
              "Multiply by 365 for an annual figure.")
SOURCE_OECD = (
    "Data: OECD Income Distribution Database (2012 methodology); OECD annual household-consumption "
    "purchasing power parities. Median disposable household income divided by the square root of household size. "
    "Current-price purchasing-power dollars, not a real-income-growth index. OECD income-year labels retained "
    "(UK financial years); latest common year across five countries. "
    "Missing years and definition changes are not joined; not spliced to Eurostat."
)


def _series(df: pd.DataFrame, country: str, metric: str) -> pd.DataFrame:
    """Non-null (year, value) rows for one country/metric, sorted by year."""
    sub = df[(df["country"] == country) & df[metric].notna()]
    columns = ["year", metric]
    columns.extend(
        f"{metric}__{field}" for field in combine.OPTIONAL_FIELDS
        if f"{metric}__{field}" in sub.columns
    )
    return sub[columns].sort_values("year")


def _source_note(fig, text: str, ha: str = "left") -> None:
    x = 0.01 if ha == "left" else 0.99
    fig.text(x, 0.01, textwrap.fill(text, width=150), ha=ha,
             fontsize=8, color=SUBSTACK_MUTED, style="italic")


def _line_chart(df: pd.DataFrame, metric: str, title: str, ylabel: str, yfmt,
                source: str, filename: str, out: pathlib.Path, *,
                eu_agg: tuple | None = None, eu_label: str | None = None,
                scale: float = 1.0, source_ha: str = "left",
                xlabel: str | None = None) -> None:
    """Draw a UK-vs-peers line chart for one metric and save it to ``out/filename``.

    ``eu_agg``/``eu_label`` optionally add an EU reference series (Eurostat
    ``EU_EUROSTAT`` for income, ``EU_WB`` for GDP). No aggregate is synthesized.
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
        status_column = f"{metric}__status"
        breaks = (
            s.loc[s[status_column].fillna("").astype(str).str.lower().str.contains("b", regex=False), "year"].tolist()
            if status_column in s.columns else []
        )
        for field in ("survey_comparability", "welfare_type", "income_definition"):
            column = f"{metric}__{field}"
            if column in s.columns:
                metadata = s[column]
                known = metadata.notna() & metadata.ne("")
                changed = known & known.shift(fill_value=False) & metadata.ne(metadata.shift())
                breaks.extend(s.loc[changed, "year"])
        annual = with_year_gaps(s.set_index("year")[metric] / scale, breaks=breaks)
        is_uk = country == "United Kingdom"
        label = eu_label if country.startswith("European Union") else country
        ax.plot(annual.index, annual.values, color=color, linestyle=ls, linewidth=lw,
                label=label, marker="o" if is_uk or metric.startswith("median") else None,
                markersize=5 if is_uk else 2.5,
                markeredgecolor="white", markeredgewidth=1.0 if is_uk else 0)

    ax.set_xlabel(xlabel or ("Survey year" if metric == "median_disposable_income" else "Year"), labelpad=2)
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
    bottom = 0.22 if metric == oecd_income.METRIC else (
        0.18 if metric == "median_disposable_income" else 0.15
    )
    plt.subplots_adjust(bottom=bottom)
    save_chart(fig, out / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_median_income_oecd(df: pd.DataFrame, out: pathlib.Path) -> None:
    income = df[(df["year"] >= oecd_income.COMPARISON_START) & df[oecd_income.METRIC].notna()]
    endpoints = []
    for country, *_ in PEERS:
        series = income[income["country"] == country]
        if series.empty:
            raise ValueError(f"Missing OECD median disposable income: {country}")
        endpoints.append(int(series["year"].max()))
    end = min(endpoints)
    _line_chart(
        income[income["year"] <= end], oecd_income.METRIC,
        f"Median disposable income: UK vs peers, {oecd_income.COMPARISON_START}\u2013{end}",
        "Annual household-size-adjusted income\n(current purchasing-power dollars)",
        lambda value, _: f"${value / 1000:.0f}k", SOURCE_OECD,
        "median_disposable_income_oecd.png", out, xlabel="Income year (OECD labels)",
    )


def fig_uk_relative(
    df: pd.DataFrame, out: pathlib.Path, *, simplified: bool = False,
) -> None:
    metric = NOMINAL_GDP_METRIC
    # Match the coverage of the companion World Bank PPP comparison.
    start = 1990
    uk = _series(df, "United Kingdom", metric).set_index("year")[metric]
    uk = uk[uk.index >= start]
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    # These are dollar-valued GDP ratios, not household-income or real-growth ratios.
    refs = [
        ("United States", SUBSTACK_TEXT, "-", 2.8, "United States"),
        ("Germany", SUBSTACK_BLUE, "-", 2.0, "Germany"),
        ("France", SUBSTACK_GOLD, "-", 2.0, "France"),
        ("European Union", SUBSTACK_MUTED, "--", 2.0, "EU average"),
        ("Poland", SUBSTACK_GREEN, "-", 2.0, "Poland"),
    ]
    if simplified:
        refs = [ref for ref in refs if ref[0] not in {"Germany", "France"}]
    plotted_years = []
    labels = []
    for country, color, ls, lw, label in refs:
        ref = _series(df, country, metric).set_index("year")[metric]
        ratio = (ref / uk).dropna() * 100.0  # peer as % of the UK
        if ratio.empty:
            continue
        plotted_years.extend(ratio.index)
        annual = with_year_gaps(ratio)
        ax.plot(annual.index, annual.values, color=color, linewidth=lw, linestyle=ls, label=label,
                marker="o", markersize=2.5)
        labels.append((ratio.iloc[-1], f"{label} ({ratio.index[-1]})", color))
    if not plotted_years:
        plt.close(fig)
        raise ValueError("no overlapping nominal GDP observations from 1990 onward")
    labelled_ends(ax, labels, min_gap=5.0, x=max(plotted_years), fontsize=10)

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
    ax.set_title(f"Nominal GDP per capita relative to the UK, "
                 f"{min(plotted_years)}\u2013{max(plotted_years)}",
                 fontweight="bold", pad=30)
    facts = []
    if not us.empty:
        facts.append(f"US: {us.iloc[-1]:.0f}% of the UK in {us.index[-1]}")
    if not pl.empty:
        facts.append(f"Poland: {pl.iloc[-1]:.0f}% in {pl.index[-1]}")
    if facts:
        ax.text(0.5, 1.015, "; ".join(facts),
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=12, color=SUBSTACK_MUTED)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.04)
    _source_note(fig, SOURCE_NOMINAL_GDP)
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.15)
    filename = (
        "uk_gdp_relative_to_peers_simple.png" if simplified else "uk_gdp_relative_to_peers.png"
    )
    save_chart(fig, out / filename, dpi=200, bbox_inches="tight")
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
        "Real GDP per capita (national-accounts volumes)",
        "GDP per capita (000s, constant 2015 US$)",
        lambda v, _: f"${v:.0f}k", SOURCE_GDP,
        "gdp_per_capita_real_over_time.png", out,
        eu_agg=EU_WB, eu_label="EU average", scale=1000.0, source_ha="left",
    )
    _line_chart(
        df, NOMINAL_GDP_METRIC,
        "Nominal GDP per capita at market exchange rates",
        "GDP per capita (000s, current US$)",
        lambda v, _: f"${v:.0f}k", SOURCE_NOMINAL_GDP,
        "gdp_per_capita_nominal_over_time.png", out,
        eu_agg=EU_WB, eu_label="EU average", scale=1000.0,
    )
    fig_uk_relative(df, out)
    fig_uk_relative(df, out, simplified=True)
    fig_median_income_oecd(df, out)
    _line_chart(
        df, "median_disposable_income",
        "Median disposable income: UK vs peers",
        "Household-size-adjusted income\n(purchasing power standards)",
        lambda v, _: f"{v/1000:.0f}k", SOURCE_EUROSTAT,
        "median_disposable_income_pps.png", out,
        eu_agg=EU_EUROSTAT, eu_label="EU-27", source_ha="right",
    )
    _line_chart(
        df, "median_income_pip",
        "Median daily income or consumption: UK vs peers",
        f"Per person per day ({pip.PPP_VERSION} international dollars)",
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
