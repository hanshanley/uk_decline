#!/usr/bin/env python3
"""Generate the UK-decline figures from the combined Europe dataset.

Reads ``data/europe_combined_wide.csv`` (produced by ``fetch_data.py``) and writes
PNGs to ``outputs/``. Styling deliberately mirrors the "Substack-style" theme used in
the pre1870_reapportionment_package figures (warm tan background, serif fonts, muted
palette, italic source note, no top/right spines).

Figures:
  - gdp_per_capita_ppp_over_time.png   UK vs European peers + EU-27, GDP/capita PPP
  - uk_gdp_relative_to_peers.png       UK GDP/capita as a share of Germany and the EU-27
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

# ── Substack-style theme (matches pre1870_reapportionment_package figures) ──
SUBSTACK_BG = "#F7F5F0"
SUBSTACK_CARD = "#EFEDE8"
SUBSTACK_TEXT = "#1A1A1A"
SUBSTACK_MUTED = "#6B6B6B"
SUBSTACK_ACCENT = "#C85A3D"
SUBSTACK_BLUE = "#3D6F8C"
SUBSTACK_GOLD = "#C2993E"
SUBSTACK_GREEN = "#4A7C59"
SUBSTACK_GRID = "#D6D3CC"

plt.rcParams.update({
    "figure.facecolor": SUBSTACK_BG,
    "axes.facecolor": SUBSTACK_BG,
    "savefig.facecolor": SUBSTACK_BG,
    "text.color": SUBSTACK_TEXT,
    "axes.labelcolor": SUBSTACK_TEXT,
    "xtick.color": SUBSTACK_MUTED,
    "ytick.color": SUBSTACK_MUTED,
    "axes.edgecolor": SUBSTACK_GRID,
    "grid.color": SUBSTACK_GRID,
    "grid.alpha": 0.6,
    "grid.linewidth": 0.5,
    "font.family": "serif",
    "font.size": 12,
    "axes.titlesize": 16,
    "axes.labelsize": 13,
    "figure.titlesize": 18,
    "legend.framealpha": 0.0,
    "legend.fontsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

LABEL_STROKE = [pe.withStroke(linewidth=4, foreground="white")]

# UK is always the warm accent; peers use the cooler/earthy palette. The US (a key
# non-European peer) is near-black. Spain removed per request; US added.
PEERS = [
    ("United Kingdom", SUBSTACK_ACCENT, "-", 2.8),
    ("United States", SUBSTACK_TEXT, "-", 1.8),
    ("Germany", SUBSTACK_BLUE, "-", 1.8),
    ("France", SUBSTACK_GOLD, "-", 1.8),
    ("Italy", SUBSTACK_GREEN, "-", 1.8),
]
EU_EUROSTAT = ("European Union (27, 2020)", SUBSTACK_MUTED, "--", 1.6)  # Eurostat, income

# GDP per capita is shown as REAL (inflation-adjusted) values from Maddison; the World
# Bank PPP series is nominal-current and only starts in 1990, so it is not plotted.
GDP_METRIC = "gdp_per_capita_real_maddison"

SOURCE_MADDISON = ("Source: Maddison Project Database 2023 (Bolt & van Zanden), via Our "
                   "World in Data. Real GDP per capita, PPP, constant 2011 international $ "
                   "(inflation-adjusted).")
SOURCE_EUROSTAT = ("Source: Eurostat ilc_di03 (median equivalised net income, PPS). "
                   "UK left EU-SILC after Brexit, so its series ends ~2018.")
SOURCE_PIP = ("Source: World Bank Poverty & Inequality Platform (median income, real "
              "2017 PPP $ per day). Multiply by 365 for an annual figure.")


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
    ``EU_EUROSTAT`` for income). It is omitted for the Maddison GDP charts because the
    Maddison source provides no EU aggregate and we never synthesize one. ``scale``
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
    metric = GDP_METRIC  # real Maddison series (a country-vs-country ratio is inflation-invariant)
    uk = _series(df, "United Kingdom", metric).set_index("year")[metric]
    fig, ax = plt.subplots(figsize=(11, 6))

    refs = [
        ("Germany", SUBSTACK_BLUE, "vs Germany"),
        ("United States", SUBSTACK_TEXT, "vs United States"),
    ]
    for country, color, label in refs:
        ref = _series(df, country, metric).set_index("year")[metric]
        ratio = (uk / ref).dropna() * 100.0
        if ratio.empty:
            continue
        ax.plot(ratio.index, ratio.values, color=color, linewidth=2.4)
        _end_label(ax, ratio.index, ratio.values, label, color)

    ax.axhline(100, color=SUBSTACK_MUTED, linewidth=1.0, linestyle=":")
    ax.text(ax.get_xlim()[0], 100.6, "parity (100%)", fontsize=9,
            color=SUBSTACK_MUTED, style="italic", va="bottom")

    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("UK GDP per capita as % of reference", labelpad=2)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("The relative decline: UK real GDP per capita\nas a share of Germany "
                 "and the United States, 1970\u20132022", fontweight="bold", pad=14)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.1)
    _source_note(fig, SOURCE_MADDISON)
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.12)
    plt.savefig(out / "uk_gdp_relative_to_peers.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    root = pathlib.Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="Plot the UK-decline figures.")
    p.add_argument("--data", default=str(root / "data" / "europe_combined_wide.csv"))
    p.add_argument("--out", default=str(root / "outputs"))
    args = p.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.data)

    _line_chart(
        df, GDP_METRIC,
        "Real GDP per capita: the UK falls behind its peers, 1970\u20132022",
        "Real GDP per capita (000s int'l $, 2011 PPP)",
        lambda v, _: f"${v:.0f}k", SOURCE_MADDISON,
        "gdp_per_capita_real_over_time.png", out,
        scale=1000.0, source_ha="left",
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
