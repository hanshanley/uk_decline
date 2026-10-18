"""Plot the historical tuition series (real, constant 2022 USD).

Reads ``data/processed/tuition_history.csv`` (built by build_history.py) and writes to
``outputs/`` in the shared Substack style. Every value is inflation-adjusted (constant
2022 USD) and traceable to a primary source (see the source note on the figure).

Usage:
    python plot_history.py
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import textwrap

import matplotlib.pyplot as plt
import pandas as pd

from tuition import config, theme
from tuition.fetch_collegeboard import BREAK_YEAR
from vizstyle import with_year_gaps, save_chart

# region key -> (label, colour, matplotlib draw style)
SERIES = {
    config.US: ("US — public 4-year, in-state (College Board)", theme.country_color("US"), "line"),
    config.UK: ("UK — England fee cap (statutory)", theme.country_color("UK"), "line"),
    config.EU: ("Germany — zero-fee reference years only", theme.country_color("Germany"), "points"),
}
SOURCE_NOTE = (
    "Real 2022 US dollars (inflation-adjusted). Sources: US — College Board Table CP-2 "
    "(current dollars); UK — England statutory fee caps (legislation.gov.uk / "
    "GOV.UK), converted at World Bank market exchange rates. "
    "Both deflated with the US Bureau of Labor Statistics' annual consumer price index for urban consumers; "
    "2025 averages 11 published months. "
    "Fee years are academic start years. US line breaks at the 1987 collection/weighting change. "
    "UK zero-fee anchors shown separately, without interpolation to fee introduction. "
    "Germany: zero-fee reference points only; some states charged fees in 2006–14."
)


def load_history(value_key: str = "real_2022_usd") -> dict[str, list[tuple[int, float]]]:
    by_region: dict[str, list[tuple[int, float]]] = {}
    with open(config.HISTORY_OUT_CSV, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get(value_key) in (None, ""):
                continue
            by_region.setdefault(r["region"], []).append((int(r["year"]), float(r[value_key])))
    for region in by_region:
        by_region[region].sort()
    return by_region


def plot(out_path: str) -> None:
    theme.apply()
    data = load_history()

    fig, ax = plt.subplots(figsize=(12, 7))
    for region, (label, color, style) in SERIES.items():
        pts = data.get(region)
        if not pts:
            continue
        xs = [y for y, _ in pts]
        ys = [v for _, v in pts]
        if region == config.UK:
            series = with_year_gaps(pd.Series(
                [v if v > 0 else float("nan") for v in ys], index=xs))
            ax.plot(series.index, series.values,
                    color=color, linewidth=2.4, marker="o", markersize=4,
                    markeredgecolor=theme.BG, markeredgewidth=0.8, label=label)
            zero_years = [y for y, v in pts if v == 0]
            ax.plot(zero_years, [0] * len(zero_years), "o", color=color,
                    markersize=7, markerfacecolor="none", markeredgecolor=color,
                    markeredgewidth=1.2, zorder=3)
        elif style == "points":
            ax.plot(xs, ys, "o", color=color, markersize=5,
                    markeredgecolor=theme.BG, markeredgewidth=0.8, label=label)
        elif style == "step":
            ax.step(xs, ys, where="post", color=color, linewidth=2.4, label=label)
            ax.plot(xs, ys, "o", color=color, markersize=5, markeredgecolor=theme.BG, markeredgewidth=0.8)
        else:
            series = with_year_gaps(
                pd.Series(ys, index=xs),
                breaks=(BREAK_YEAR,) if region == config.US else (),
            )
            ax.plot(series.index, series.values, color=color, linewidth=2.4, marker="o", markersize=4,
                    markeredgecolor=theme.BG, markeredgewidth=0.8, label=label)

    ax.set_ylabel("Annual domestic tuition (constant 2022 US dollars)")
    ax.set_xlabel("Academic start year")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    all_years = [y for pts in data.values() for y, _ in pts]
    span = f"{min(all_years)}\u2013{max(all_years)}" if all_years else ""
    ax.set_title(
        f"Tuition fees, {span} (constant 2022 US dollars)\n"
        "England statutory cap versus US public in-state average",
        fontweight="bold", pad=14,
    )
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.margins(x=0.02)
    ax.legend(loc="upper left", frameon=False)

    theme.source_note(fig, textwrap.fill(SOURCE_NOTE, width=150))
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18)
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_nominal_cap(out_path: str) -> None:
    """Show the current statutory cap without requiring unavailable annual FX/CPI."""
    theme.apply()
    points = [(year, value) for year, value in load_history("nominal_local").get(config.UK, [])
              if value > 0 and year <= dt.date.today().year]
    if not points:
        raise ValueError("No current England fee-cap observations to plot")
    years, values = zip(*points)
    series = with_year_gaps(pd.Series(values, index=years))
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.step(series.index, series.values, where="post", color=theme.ACCENT, linewidth=2.4, label="England undergraduate tuition cap")
    ax.plot(years[-1], values[-1], "o", color=theme.ACCENT)
    ax.set_title(
        "England's undergraduate tuition cap\n"
        f"£{values[-1]:,.0f} in {years[-1]}/{str(years[-1] + 1)[-2:]} (nominal pounds)",
        fontweight="bold", pad=14,
    )
    ax.set_xlabel("Academic start year")
    ax.set_ylabel("Maximum annual fee (pounds, not inflation-adjusted)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"£{value:,.0f}"))
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    theme.source_note(
        fig,
        "Sources: England statutory caps, legislation.gov.uk / Hansard / GOV.UK; "
        "per-year citations in tuition_history.csv.\n"
        "Standard full-time home undergraduate maximum; not average UK tuition. "
        "The separate real-dollar history requires same-year exchange rates and consumer-price data.",
    )
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.17)
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    plot(os.path.join(config.OUTPUTS_DIR, "tuition_history_real_usd.png"))
    plot_nominal_cap(os.path.join(config.OUTPUTS_DIR, "tuition_england_cap_nominal.png"))


if __name__ == "__main__":
    main()
