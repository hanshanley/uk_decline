#!/usr/bin/env python3
"""Generate the UK-decline figures from the combined Europe dataset.

Reads ``data/europe_combined_wide.csv`` (produced by ``fetch_data.py``) and writes
PNGs to ``outputs/``. Styling deliberately mirrors the "Substack-style" theme used in
the pre1870_reapportionment_package figures (warm tan background, serif fonts, muted
palette, italic source note, no top/right spines).

Figures:
  - us_uk_gdp_measures.png            Nominal, PPP, real-volume ratios and annual FX
  - gdp_per_capita_real_over_time.png  National-accounts real growth, 2007 = 100
  - gdp_per_capita_nominal_over_time.png  Nominal valuations at annual market FX
  - uk_gdp_relative_to_peers.png       Peer nominal GDP/capita as a share of the UK
  - uk_gdp_relative_to_peers_simple.png  US, EU and Poland nominal GDP, UK = 100
  - uk_real_gdp_relative_to_peers.png    US, EU and Poland real PPP volumes, UK = 100
  - uk_ppp_gdp_relative_to_peers.png     US, EU and Poland current-price PPP GDP, UK = 100
  - median_disposable_income_pps.png   Median income (Eurostat PPS), UK ends ~2018
  - median_disposable_income_oecd.png  Median income (OECD, household-consumption PPP)
  - median_income_pip.png              Recent PIP surveys (2021 PPP $/day), since 2000

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
from europe_data import combine, gdp_comparisons, oecd_income, pip
from ppp_data.figure import labelled_ends

# ── Professional house style (shared vizstyle house style) ───────────────────
from vizstyle import (  # noqa: E402
    BG as SUBSTACK_BG, CARD as SUBSTACK_CARD, TEXT as SUBSTACK_TEXT,
    MUTED as SUBSTACK_MUTED, ACCENT as SUBSTACK_ACCENT, BLUE as SUBSTACK_BLUE,
    GOLD as SUBSTACK_GOLD, GREEN as SUBSTACK_GREEN, GRID as SUBSTACK_GRID,
    country_color, house_style, with_year_gaps, mark_year_breaks, save_chart,
)

house_style()

# UK is always the warm accent; peers use the cooler/earthy palette. The US (a key
# non-European peer) is near-black. Spain removed per request; US added.
PEERS = [
    ("United Kingdom", country_color("GBR"), "-", 2.8),
    ("United States", country_color("USA"), "-", 1.8),
    ("Germany", country_color("DEU"), "-", 1.8),
    ("France", country_color("FRA"), "-", 1.8),
    ("Italy", country_color("ITA"), "-", 1.8),
    ("Poland", country_color("POL"), "--", 2.1),
]
INCOME_PEERS = list(PEERS)
EU_WB = ("European Union", country_color("EUU"), "--", 2.0)                    # World Bank EU aggregate, for GDP
EU_EUROSTAT = ("European Union (27, 2020)", country_color("EUU"), "--", 1.6)  # Eurostat, income

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
SOURCE_EUROSTAT = ("Data: Eurostat (European Commission), "
                   "EU Statistics on Income and Living Conditions \u2014 median household-size-adjusted "
                   "net income, current purchasing power standards (ilc_di03). Survey year; income usually refers "
                   "to the preceding year, with country exceptions including the UK. "
                   "Current-price PPS, not real-income growth. Missing years and flagged method breaks "
                   "remain explicit. Dotted links mark methodology changes; missing years remain blank. "
                   "The display starts when all plotted series have begun; "
                   "earlier observations remain in the CSV. "
                   "US data are unavailable in this Eurostat dataset; use the OECD comparison.")
SOURCE_PIP = ("Data: World Bank Group, Poverty and Inequality Platform \u2014 median "
              f"per-person income/consumption, {pip.PPP_VERSION} international dollars per day "
              "(purchasing power parity). Survey observations only; "
              "missing years and welfare-definition changes are not connected; dotted links mark survey-method changes. "
              "Recent comparison since 2000; sparse earlier surveys remain in the CSV. "
              "No comparable EU aggregate is supplied. Not household-equivalised disposable income. "
              "Multiply by 365 for an annual figure.")
SOURCE_OECD = (
    "Data: OECD Income Distribution Database (2012 methodology); OECD annual household-consumption "
    "purchasing power parities. Median disposable household income divided by the square root of household size. "
    "Current-price purchasing-power dollars, not a real-income-growth index. OECD income-year labels retained "
    "(UK financial years). "
    "Missing years remain blank; dotted links mark definition changes, not like-for-like growth. "
    "Not spliced to Eurostat."
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


def _plot_annual_series(ax, s, metric, country, color, ls, lw, *, label=None, scale=1.0):
    status_column = f"{metric}__status"
    breaks = (
        s.loc[s[status_column].fillna("").astype(str).str.lower().str.contains("b", regex=False), "year"].tolist()
        if status_column in s.columns else []
    )
    welfare_breaks = set()
    for field in ("survey_comparability", "welfare_type", "income_definition"):
        column = f"{metric}__{field}"
        if column in s.columns:
            metadata = s[column]
            known = metadata.notna() & metadata.ne("")
            changed = known & known.shift(fill_value=False) & metadata.ne(metadata.shift())
            breaks.extend(s.loc[changed, "year"])
            if field == "welfare_type":
                welfare_breaks.update(s.loc[changed, "year"])
    observed = s.set_index("year")[metric] / scale
    annual = with_year_gaps(observed, breaks=breaks)
    is_uk = country == "United Kingdom"
    ax.plot(annual.index, annual.values, color=color, linestyle=ls, linewidth=lw,
            label=label or country, marker="o" if is_uk or metric.startswith("median") else None,
            markersize=5 if is_uk else 2.5,
            markeredgecolor="white", markeredgewidth=1.0 if is_uk else 0)
    mark_year_breaks(ax, observed, breaks=set(breaks) - welfare_breaks, color=color, linewidth=lw)


def _line_chart(df: pd.DataFrame, metric: str, title: str, ylabel: str, yfmt,
                source: str, filename: str, out: pathlib.Path, *,
                eu_agg: tuple | None = None, eu_label: str | None = None,
                scale: float = 1.0, source_ha: str = "left",
                xlabel: str | None = None, baseline_year: int | None = None,
                subtitle: str | None = None, end_labels: bool = False) -> None:
    """Draw a UK-vs-peers line chart for one metric and save it to ``out/filename``.

    ``eu_agg``/``eu_label`` optionally add an EU reference series (Eurostat
    ``EU_EUROSTAT`` for income, ``EU_WB`` for GDP). No aggregate is synthesized.
    ``scale``
    divides the values (e.g. 1000 to show GDP in 000s).
    """
    peers = INCOME_PEERS if metric.startswith("median") else PEERS
    series = [*peers, eu_agg] if eu_agg is not None else list(peers)
    fig, ax = plt.subplots(figsize=(11, 6))
    plotted = False
    ends = []
    last_year = None
    for country, color, ls, lw in series:
        s = _series(df, country, metric)
        if s.empty:
            continue
        if baseline_year is not None:
            baseline = s.loc[s["year"] == baseline_year, metric]
            if baseline.empty or baseline.iloc[0] <= 0:
                raise ValueError(f"{country}: missing positive {baseline_year} real-GDP baseline")
            s = s.loc[s["year"] >= baseline_year].copy()
            s[metric] = 100 * s[metric] / baseline.iloc[0]
        plotted = True
        label = eu_label if country.startswith("European Union") else country
        _plot_annual_series(ax, s, metric, country, color, ls, lw, label=label, scale=scale)
        if end_labels:
            last = s.iloc[-1]
            ends.append((last[metric] / scale, f"{label} ({int(last['year'])})", color, int(last["year"])))
            last_year = max(int(last["year"]), last_year or int(last["year"]))

    ax.set_xlabel(xlabel or ("Survey year" if metric == "median_disposable_income" else "Year"), labelpad=2)
    if baseline_year is not None or metric.startswith("median"):
        ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=9, integer=True))
    ax.set_ylabel(ylabel, labelpad=2)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(yfmt))
    ax.set_title(title, fontweight="bold", pad=30 if subtitle else 14)
    if subtitle:
        ax.text(.5, 1.015, subtitle, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=10.5, color=SUBSTACK_MUTED)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.02)
    if ax.collections and end_labels:
        ax.text(.015, .975, "Dotted segments: survey or definition change", transform=ax.transAxes,
                va="top", fontsize=8.5, color=SUBSTACK_MUTED)
    if end_labels and ends:
        low, high = ax.get_ylim()
        labelled_ends(ax, ends, min_gap=(high - low) * .055, x=last_year, fontsize=9)
    elif plotted:
        ax.legend(loc="upper left", frameon=False, labelcolor="linecolor", fontsize=10)
    _source_note(fig, source, ha=source_ha)
    plt.tight_layout(pad=0.5)
    bottom = 0.22 if metric == oecd_income.METRIC or end_labels else (
        0.18 if metric == "median_disposable_income" else 0.15
    )
    plt.subplots_adjust(bottom=bottom)
    save_chart(fig, out / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _eurostat_income_chart(selected: pd.DataFrame, out: pathlib.Path) -> None:
    metric = "median_disposable_income"
    start, end = int(selected["year"].min()), int(selected["year"].max())
    uk_end = int(selected.loc[selected["country"] == "United Kingdom", "year"].max())
    split = end > uk_end
    fig, axes = plt.subplots(1, 2 if split else 1, figsize=(13.5 if split else 11, 6.8),
                             sharey=True, squeeze=False)
    peers = [peer for peer in INCOME_PEERS if peer[0] != "United States"] + [EU_EUROSTAT]
    for i, ax in enumerate(axes[0]):
        first, last = (start, uk_end) if i == 0 else (uk_end + 1, end)
        panel = selected.loc[selected["year"].between(first, last)]
        for country, color, ls, lw in peers:
            s = _series(panel, country, metric)
            if not s.empty:
                _plot_annual_series(
                    ax, s, metric, country, color, ls, lw,
                    label="EU-27" if country == EU_EUROSTAT[0] else country,
                )
        ax.set_title(
            f"UK and Europe, {first}\u2013{last}" if i == 0 else f"Europe only, {first}\u2013{last}",
            fontsize=14, fontweight="bold", pad=12,
        )
        ax.set_xlabel("Survey year")
        ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=5, integer=True))
        ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=5, steps=[1, 2, 5, 10]))
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda value, _: f"{value / 1000:g}k"))
        ax.grid(axis="y", linewidth=.5)
        ax.set_axisbelow(True)
        ax.margins(x=.04, y=.08)
    axes[0, 0].set_ylabel("Household-size-adjusted income\n(current purchasing power standards)")
    fig.suptitle("Median disposable income: Eurostat", fontsize=20, fontweight="bold", y=.985)
    fig.text(.5, .925, f"UK observations end in {uk_end}; US not covered \u2014 use OECD for current UK/US comparisons",
             ha="center", fontsize=10.5, color=SUBSTACK_MUTED)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .89), ncol=3,
               frameon=False, labelcolor="linecolor", fontsize=10)
    _source_note(fig, SOURCE_EUROSTAT)
    fig.subplots_adjust(left=.08, right=.985, top=.73, bottom=.25, wspace=.12)
    save_chart(fig, out / "median_disposable_income_pps.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_median_income_non_oecd(df: pd.DataFrame, out: pathlib.Path, *, source: str) -> None:
    if source == "eurostat":
        metric = "median_disposable_income"
        required = [country for country, *_ in INCOME_PEERS if country != "United States"]
        required.append(EU_EUROSTAT[0])
    elif source == "pip":
        metric = pip.METRIC
        required = [country for country, *_ in INCOME_PEERS]
    else:
        raise ValueError(f"Unknown income comparison source: {source}")
    selected = df.loc[df["country"].isin(required) & df[metric].notna()].copy()
    for country in required:
        if selected.loc[selected["country"] == country].empty:
            raise ValueError(f"Missing {source} income observations: {country}")
    start = (
        int(selected.groupby("country")["year"].min().max())
        if source == "eurostat" else 2000
    )
    selected = selected.loc[selected["year"] >= start]
    if not set(required) <= set(selected["country"]):
        raise ValueError(f"Missing {source} income observations in the recent comparison")
    if source == "eurostat":
        _eurostat_income_chart(selected, out)
        return
    end = int(selected["year"].max())
    _line_chart(
        selected, metric, f"Median daily income or consumption: PIP, {start}\u2013{end}",
        f"Per person per day ({pip.PPP_VERSION} international dollars)",
        lambda value, _: f"${value:.0f}", SOURCE_PIP, "median_income_pip.png", out,
        xlabel="Income reporting year",
        subtitle="Per-person survey measure; dated end labels \u2014 not household-equivalised disposable income",
        end_labels=True,
    )


def fig_median_income_oecd(df: pd.DataFrame, out: pathlib.Path) -> None:
    income = df[df[oecd_income.METRIC].notna()]
    coverage = []
    for country, *_ in INCOME_PEERS:
        series = income[income["country"] == country]
        if series.empty:
            raise ValueError(f"Missing OECD median disposable income: {country}")
        coverage.append(set(series["year"]))
    selected = income[income["country"].isin([country for country, *_ in INCOME_PEERS])]
    shared = set.intersection(*coverage)
    if not shared:
        raise ValueError("OECD income has no complete common annual comparison")
    common_end = max(shared)
    common_start = common_end
    while common_start - 1 in shared:
        common_start -= 1
    if common_start == common_end:
        raise ValueError("OECD income has no complete common annual comparison spanning multiple years")
    comparison = selected[selected["year"].between(common_start, common_end)]
    _line_chart(
        comparison, oecd_income.METRIC,
        f"Median disposable income: UK vs peers, {int(common_start)}\u2013{int(common_end)}",
        "Annual household-size-adjusted income\n(current purchasing-power dollars)",
        lambda value, _: f"${value / 1000:.0f}k",
        SOURCE_OECD + " Complete shared annual period only. The separate full-history figure "
        "retains every earlier observation and any later country-specific releases.",
        "median_disposable_income_oecd.png", out, xlabel="Income year (OECD labels)",
        subtitle="The same six countries, with an observation in every year",
        end_labels=True,
    )
    start, end = int(selected["year"].min()), int(selected["year"].max())
    _line_chart(
        selected, oecd_income.METRIC,
        f"Median disposable income: full published history, {start}\u2013{end}",
        "Annual household-size-adjusted income\n(current purchasing-power dollars)",
        lambda value, _: f"${value / 1000:.0f}k",
        SOURCE_OECD + " All available years retained; country coverage differs. "
        "Use the companion common-period figure for the complete six-country comparison.",
        "median_disposable_income_oecd_history.png", out, xlabel="Income year (OECD labels)",
        subtitle="Coverage varies by country; missing observations are not filled",
    )


def fig_uk_relative(
    df: pd.DataFrame, out: pathlib.Path, *, simplified: bool = False, basis: str = "nominal",
) -> None:
    metric, title, source, comparison_filename = {
        "nominal": (
            NOMINAL_GDP_METRIC, "Nominal GDP per capita relative to the UK",
            SOURCE_NOMINAL_GDP, "uk_gdp_relative_to_peers_simple.png",
        ),
        "real": (
            "gdp_per_capita_ppp_constant", "Real GDP per person at fixed 2021 PPPs relative to the UK",
            "Data: World Bank WDI, NY.GDP.PCAP.PP.KD. Constant 2021 international dollars "
            "(ICP 2021 PPP benchmark): benchmark-valued output volumes, not current market dollars. "
            "Real output growth at fixed purchasing power parities; annual market FX is not applied. "
            "Country levels depend on the fixed benchmark; the EU aggregate uses PPP valuation weights.",
            "uk_real_gdp_relative_to_peers.png",
        ),
        "ppp": (
            "gdp_per_capita_ppp_current", "GDP per person at current PPPs relative to the UK",
            "Data: World Bank WDI, NY.GDP.PCAP.PP.CD. Current international dollars (ICP 2021 vintage). "
            "Each year's purchasing power parities and prices, not annual market exchange rates. "
            "Same-year output comparisons; movements include changing price weights and parity estimates, "
            "not just real growth. GDP is not household income.",
            "uk_ppp_gdp_relative_to_peers.png",
        ),
    }[basis]
    # Match the coverage of the companion World Bank PPP comparison.
    start = 1990
    uk = _series(df, "United Kingdom", metric).set_index("year")[metric]
    uk = uk[uk.index >= start]
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    refs = [
        ("United States", country_color("USA"), "-", 2.8, "United States"),
        ("Germany", country_color("DEU"), "-", 2.0, "Germany"),
        ("France", country_color("FRA"), "-", 2.0, "France"),
        ("European Union", country_color("EUU"), "--", 2.0, "EU average"),
        ("Poland", country_color("POL"), "--", 2.1, "Poland"),
    ]
    if simplified or basis != "nominal":
        refs = [ref for ref in refs if ref[0] in {"United States", "European Union", "Poland"}]
    plotted_years = []
    labels = []
    ratios = {}
    for country, color, ls, lw, label in refs:
        ref = _series(df, country, metric).set_index("year")[metric]
        ratio = (ref / uk).dropna() * 100.0  # peer as % of the UK
        if ratio.empty:
            if simplified or basis != "nominal":
                raise ValueError(f"Missing {country} observations for the {basis} UK comparison")
            continue
        plotted_years.extend(ratio.index)
        ratios[country] = ratio
        annual = with_year_gaps(ratio)
        ax.plot(annual.index, annual.values, color=color, linewidth=lw, linestyle=ls, label=label,
                marker="o" if len(ratio) == 1 else None, markersize=2.5)
        labels.append((ratio.iloc[-1], f"{label} ({ratio.index[-1]})", color, ratio.index[-1]))
    if not plotted_years:
        plt.close(fig)
        raise ValueError(f"no overlapping {basis} GDP observations from 1990 onward")
    labelled_ends(ax, labels, min_gap=5.0, x=max(plotted_years), fontsize=10)

    ax.axhline(100, color=SUBSTACK_ACCENT, linewidth=1.4, linestyle="-")
    ax.text(ax.get_xlim()[0], 102, "United Kingdom = 100", fontsize=9.5,
            color=SUBSTACK_ACCENT, style="italic", fontweight="bold", va="bottom")

    ax.set_xlabel("Year", labelpad=2)
    ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=9, integer=True))
    ax.set_ylabel("GDP per capita as % of the UK (UK = 100)", labelpad=2)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    # Centered title + centered subtitle (the subtitle carries the two turning-point facts,
    # so it stays aligned under the headline instead of drifting to a corner).
    ax.set_title(f"{title}, "
                 f"{min(plotted_years)}\u2013{max(plotted_years)}",
                 fontweight="bold", pad=30)
    facts = []
    fact_peers = (
        (("United States", "US"), ("European Union", "EU"), ("Poland", "Poland"))
        if simplified or basis != "nominal" else
        (("United States", "US"), ("Poland", "Poland"))
    )
    for country, label in fact_peers:
        ratio = ratios.get(country)
        if ratio is not None:
            facts.append(f"{label}: {ratio.iloc[-1]:.1f}% of the UK in {ratio.index[-1]}")
    if facts:
        ax.text(0.5, 1.015, "; ".join(facts),
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=12, color=SUBSTACK_MUTED)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.04)
    _source_note(fig, source)
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.17)
    filename = (
        comparison_filename if simplified or basis != "nominal" else "uk_gdp_relative_to_peers.png"
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
    gdp_comparisons.make_chart(df, out)

    _line_chart(
        df, GDP_METRIC,
        "Real GDP per person: growth since 2007",
        "Real GDP per person index (each economy: 2007 = 100)",
        lambda v, _: f"{v:.0f}", SOURCE_GDP + " Each economy divided by its own observed "
        "2007 value: compares real growth, not countries' starting GDP levels.",
        "gdp_per_capita_real_over_time.png", out,
        eu_agg=EU_WB, eu_label="EU average", source_ha="left", baseline_year=2007,
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
    fig_uk_relative(df, out, simplified=True, basis="real")
    fig_uk_relative(df, out, simplified=True, basis="ppp")
    fig_median_income_oecd(df, out)
    fig_median_income_non_oecd(df, out, source="eurostat")
    fig_median_income_non_oecd(df, out, source="pip")

    print(f"Wrote figures to {out}/:")
    for png in sorted(out.glob("*.png")):
        print(f"  {png.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
