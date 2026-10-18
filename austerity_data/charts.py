"""Publication-quality chart of Britain's austerity-era spending squeeze."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from vizstyle import (ACCENT, BG, BLUE, GOLD, GREEN, GRID, MUTED, TEXT, house_style,
                      save_chart, with_year_gaps, mark_year_breaks)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "austerity" / "uk_austerity_spending_investment.png"
BASE_YEAR = "2010-11"
END_YEAR = "2019-20"
START_YEAR = "2000-01"

SERIES = {
    "housing_community": ("Housing", ACCENT, 3.2),
    "recreation_culture": ("Recreation, culture & religion", GOLD, 2.6),
    "public_order_safety": ("Public safety", BLUE, 2.6),
    "health": ("Health", GREEN, 2.8),
}


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source.copy()
    return pd.read_csv(source)


def indexed_function_series(
    df: pd.DataFrame,
    category: str,
    start_year: str = START_YEAR,
    base_year: str = BASE_YEAR,
    end_year: str | None = None,
) -> pd.DataFrame:
    """Return a linked official-vintage index with ``base_year=100``.

    PESA 2012 supplies 2000-01 to 2002-03; the latest PSS vintage supplies
    2003-04 onward. Each segment is indexed to its own official 2010-11 value,
    so no cash levels are fabricated or inflation bases mixed.
    """
    current = df[
        (df["metric"] == "functional_spending_real")
        & (df["category"] == category)
        & (df["financial_year"] >= start_year)
        & (True if end_year is None else df["financial_year"] <= end_year)
    ].sort_values("year")
    if current.empty or base_year not in set(current["financial_year"]):
        raise ValueError(f"missing {category!r} base year {base_year}")
    current_base = float(
        current.loc[current["financial_year"] == base_year, "value"].iloc[0]
    )
    current = current[["financial_year", "year", "value"]].copy()
    current["index"] = current["value"] / current_base * 100
    current["vintage"] = "current"

    historical_all = df[
        (df["metric"] == "functional_spending_historical_real")
        & (df["category"] == category)
    ].sort_values("year")
    if historical_all.empty:
        return current.reset_index(drop=True)
    if base_year not in set(historical_all["financial_year"]):
        raise ValueError(f"missing historical {category!r} base year {base_year}")
    historical_base = float(
        historical_all.loc[
            historical_all["financial_year"] == base_year, "value"
        ].iloc[0]
    )
    historical = historical_all[
        (historical_all["financial_year"] >= start_year)
        & (historical_all["financial_year"] < current["financial_year"].min())
    ][["financial_year", "year", "value"]].copy()
    historical["index"] = historical["value"] / historical_base * 100
    historical["vintage"] = "historical"
    return pd.concat([historical, current], ignore_index=True).sort_values("year")


def trough_change(
    df: pd.DataFrame,
    category: str,
    base_year: str = BASE_YEAR,
    end_year: str = END_YEAR,
) -> tuple[float, str]:
    """Return the minimum indexed change and its fiscal year during austerity."""
    indexed = indexed_function_series(
        df,
        category,
        start_year=base_year,
        base_year=base_year,
        end_year=end_year,
    )
    trough = indexed.loc[indexed["index"].idxmin()]
    return float(trough["index"] - 100), str(trough["financial_year"])


def _label(ax, x, y, text, color, *, dx=0.12, size=10.5) -> None:
    ax.text(
        x + dx,
        y,
        text,
        color=color,
        fontsize=size,
        fontweight="bold",
        va="center",
        path_effects=[pe.withStroke(linewidth=3.5, foreground=BG)],
    )


def _style_axis(ax) -> None:
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def make_chart(source, output: Path | str = DEFAULT_OUTPUT) -> Path:
    """Render the combined austerity spending/investment figure."""
    df = _load(source)
    house_style()
    latest_year = int(df.loc[
        df["metric"].isin(["functional_spending_real", "public_sector_net_investment_pct_gdp"]),
        "year",
    ].max())
    ticks = sorted(set([*range(2000, latest_year + 1, 5), latest_year]))

    fig = plt.figure(figsize=(14.2, 9.6), facecolor=BG)
    grid = fig.add_gridspec(
        2, 4,
        height_ratios=[1.08, 1],
        hspace=0.48,
        wspace=0.28,
    )
    service_axes = [fig.add_subplot(grid[0, i]) for i in range(4)]
    ax_invest = fig.add_subplot(grid[1, :])

    fig.suptitle(
        "UK public spending before and after austerity",
        x=0.06,
        y=0.978,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.062,
        0.934,
        "Selected services in real terms, indexed to 2010–11 = 100; "
        "public sector net investment shown as a share of GDP.",
        ha="left",
        fontsize=13,
        color=MUTED,
    )

    # Four small multiples avoid the misleading visual tangle of differently shaped series.
    panel_order = [
        "housing_community",
        "public_order_safety",
        "recreation_culture",
        "health",
    ]
    panel_titles = {
        "housing_community": "Housing & community",
        "public_order_safety": "Public safety",
        "recreation_culture": "Recreation, culture\n& religion",
        "health": "Health",
    }
    for ax, category in zip(service_axes, panel_order):
        _label_text, color, _width = SERIES[category]
        series = indexed_function_series(df, category)
        ax.axvspan(2010, 2019.9, color=ACCENT, alpha=0.055, linewidth=0)
        breaks = series.loc[series["vintage"].ne(series["vintage"].shift())
                            & series["vintage"].shift().notna(), "year"]
        observed = series.set_index("year")["index"]
        annual = with_year_gaps(observed, breaks=breaks)
        ax.plot(
            annual.index,
            annual.values,
            color=color,
            label=_label_text,
            linewidth=2.8,
            zorder=4,
        )
        ax.scatter(series["year"], series["index"], s=10, color=color, zorder=5)
        mark_year_breaks(ax, observed, breaks=breaks, color=color, linewidth=2.8)
        ax.axhline(100, color=TEXT, linewidth=0.8, alpha=0.45)
        last = series.iloc[-1]
        first = series.iloc[0]
        ax.text(
            0.02, 0.93,
            panel_titles[category],
            transform=ax.transAxes,
            fontsize=11.8,
            fontweight="bold",
            color=TEXT,
            va="top",
        )
        ax.text(
            0.02, 0.73 if "\n" in panel_titles[category] else 0.83,
            f"{first['financial_year']}: {first['index']:.0f}\n"
            f"{last['financial_year']}: {last['index']:.0f}",
            transform=ax.transAxes,
            fontsize=9.2,
            color=color,
            fontweight="bold",
            va="top",
            linespacing=1.25,
        )
        ax.set_xlim(1999.7, latest_year + .4)
        ax.set_ylim(min(45, series["index"].min() - 5), max(170, series["index"].max() + 5))
        panel_ticks = sorted(set([*range(2000, latest_year + 1, 10), latest_year]))
        ax.set_xticks(panel_ticks)
        ax.set_xticklabels([str(year) for year in panel_ticks])
        ax.set_yticks([50, 75, 100, 125, 150])
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        if ax is service_axes[0]:
            ax.set_ylabel("Index (2010–11 = 100)", fontsize=10)
        else:
            ax.set_yticklabels([])

    fig.text(
        0.062,
        0.862,
        f"Real public spending by function, 2000–01 to {latest_year}–{(latest_year + 1) % 100:02d}",
        fontsize=15.5,
        fontweight="bold",
        color=TEXT,
    )
    # Public sector net investment, with the austerity period shaded.
    investment = df[
        (df["metric"] == "public_sector_net_investment_pct_gdp")
        & (df["year"] >= 2000)
    ].sort_values("year")
    ax_invest.axvspan(2010, 2019.9, color=ACCENT, alpha=0.07, linewidth=0)
    annual_investment = with_year_gaps(investment.set_index("year")["value"])
    ax_invest.fill_between(annual_investment.index, annual_investment.values, 0,
                           color=ACCENT, alpha=0.13)
    ax_invest.plot(
        annual_investment.index,
        annual_investment.values,
        color=ACCENT,
        label="Public sector net investment",
        linewidth=3,
        marker="o",
        markersize=5,
        markeredgecolor=BG,
        markeredgewidth=0.8,
    )
    austerity_investment = investment[
        investment["financial_year"].between(BASE_YEAR, END_YEAR)
    ]
    trough = austerity_investment.loc[austerity_investment["value"].idxmin()]
    start = investment[investment["financial_year"] == BASE_YEAR].iloc[0]
    ax_invest.scatter([start["year"], trough["year"]],
                      [start["value"], trough["value"]],
                      s=42, color=[TEXT, ACCENT], edgecolor=BG, linewidth=1, zorder=6)
    ax_invest.annotate(
        f"2010–11\n{start['value']:.1f}% of GDP",
        xy=(start["year"], start["value"]),
        xytext=(22, 22),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=10.5,
        color=TEXT,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": TEXT, "linewidth": 0.8},
    )
    ax_invest.annotate(
        f"{trough['financial_year']} low\n{trough['value']:.1f}% of GDP",
        xy=(trough["year"], trough["value"]),
        xytext=(0, -30),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=10.5,
        color=ACCENT,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": ACCENT, "linewidth": 0.8},
    )
    ax_invest.set_title(
        "Public sector net investment",
        loc="left",
        fontsize=16,
        pad=12,
    )
    ax_invest.text(
        0,
        1.01,
        "Percent of GDP",
        transform=ax_invest.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax_invest.set_xlim(1999.7, latest_year + .4)
    ax_invest.set_ylim(min(0, float(investment["value"].min()) * 1.08),
                      float(investment["value"].max()) * 1.08)
    ax_invest.set_xticks(ticks)
    ax_invest.set_xticklabels(
        [f"{year}–{(year + 1) % 100:02d}" for year in ticks]
    )
    ax_invest.yaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda value, _pos: f"{value:.0f}%" if value.is_integer() else f"{value:.1f}%"
        )
    )
    ax_invest.yaxis.set_major_locator(mticker.MultipleLocator(0.5))
    _style_axis(ax_invest)

    fig.text(
        0.057,
        0.018,
        textwrap.fill(
            "Note: Shading marks 2010–11 to 2019–20. "
            "2000–01 to 2002–03 use Public Expenditure Statistical Analyses 2012; "
            "later years use the saved Public Spending Statistics vintage. Each "
            "vintage is indexed to its own 2010–11 value; revision and definition "
            "differences remain at the seam; dotted links are not like-for-like growth. "
            "Missing years are not joined. "
            "Education is omitted because of an accounting "
            "break. Net investment is after depreciation and includes net capital grants.",
            width=185,
        )
        + "\n"
        + textwrap.fill(
            "Source: " + "; ".join(sorted(df["source"].dropna().unique())) + ".",
            width=185,
        )
        + "\nContext: New York Times / Institute for Fiscal Studies, 2019.",
        ha="left",
        va="bottom",
        fontsize=8.4,
        color=MUTED,
        style="italic",
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.065, right=0.955, top=0.79, bottom=0.16)
    save_chart(fig, output, dpi=220, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return output
