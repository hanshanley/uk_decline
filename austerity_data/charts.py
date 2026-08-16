"""Publication-quality chart of Britain's austerity-era spending squeeze."""

from __future__ import annotations

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GREEN, GRID, MUTED, TEXT, house_style

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "austerity" / "uk_austerity_spending_investment.png"
BASE_YEAR = "2010-11"
END_YEAR = "2019-20"
LATEST_YEAR = "2025-26"
START_YEAR = "2000-01"

SERIES = {
    "housing_community": ("Housing", ACCENT, 3.2),
    "recreation_culture": ("Culture & recreation", GOLD, 2.6),
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
    end_year: str = LATEST_YEAR,
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
        & (df["financial_year"] <= end_year)
    ].sort_values("year")
    if current.empty or base_year not in set(current["financial_year"]):
        raise ValueError(f"missing {category!r} base year {base_year}")
    current_base = float(
        current.loc[current["financial_year"] == base_year, "value"].iloc[0]
    )
    current = current[["financial_year", "year", "value"]].copy()
    current["index"] = current["value"] / current_base * 100

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

    fig = plt.figure(figsize=(14.2, 10.6), facecolor=BG)
    grid = fig.add_gridspec(
        2, 4,
        height_ratios=[1.15, 1],
        hspace=0.68,
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
        "recreation_culture": "Culture & recreation",
        "health": "Health",
    }
    for ax, category in zip(service_axes, panel_order):
        _label_text, color, _width = SERIES[category]
        series = indexed_function_series(df, category)
        ax.axvspan(2010, 2019.9, color=ACCENT, alpha=0.055, linewidth=0)
        ax.plot(
            series["year"],
            series["index"],
            color=color,
            linewidth=2.8,
            zorder=4,
        )
        ax.scatter(series["year"], series["index"], s=10, color=color, zorder=5)
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
            0.02, 0.83,
            f"{first['index']:.0f} in 2000  ·  {last['index']:.0f} in 2025",
            transform=ax.transAxes,
            fontsize=9.2,
            color=color,
            fontweight="bold",
            va="top",
        )
        ax.set_xlim(1999.7, 2025.4)
        ax.set_ylim(45, 170)
        ax.set_xticks([2000, 2010, 2020, 2025])
        ax.set_xticklabels(["2000", "2010", "2020", "2025"])
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
        "Real public spending by function, 2000–01 to 2025–26",
        fontsize=15.5,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.94,
        0.862,
        "shading marks 2010–19",
        ha="right",
        fontsize=9.5,
        color=MUTED,
    )

    # Public sector net investment, with the austerity period shaded.
    investment = df[
        (df["metric"] == "public_sector_net_investment_pct_gdp")
        & (df["year"] >= 2000)
        & (df["financial_year"] <= LATEST_YEAR)
    ].sort_values("year")
    ax_invest.axvspan(2010, 2019.9, color=ACCENT, alpha=0.07, linewidth=0)
    ax_invest.axvspan(2020, 2021.9, color=MUTED, alpha=0.06, linewidth=0)
    ax_invest.fill_between(investment["year"], investment["value"], 0,
                           color=ACCENT, alpha=0.13)
    ax_invest.plot(
        investment["year"],
        investment["value"],
        color=ACCENT,
        linewidth=3,
        marker="o",
        markersize=5,
        markeredgecolor=BG,
        markeredgewidth=0.8,
    )
    austerity_investment = investment[investment["financial_year"] >= BASE_YEAR]
    trough = austerity_investment.loc[austerity_investment["value"].idxmin()]
    start = investment[investment["financial_year"] == BASE_YEAR].iloc[0]
    ax_invest.scatter([start["year"], trough["year"]],
                      [start["value"], trough["value"]],
                      s=42, color=[TEXT, ACCENT], edgecolor=BG, linewidth=1, zorder=6)
    ax_invest.text(start["year"], start["value"] + 0.18,
                   f"{start['value']:.1f}%", ha="center", fontsize=11,
                   color=TEXT, fontweight="bold")
    ax_invest.text(trough["year"], trough["value"] - 0.28,
                   f"{trough['value']:.1f}% low", ha="center", fontsize=11,
                   color=ACCENT, fontweight="bold")
    ax_invest.text(
        2010.2,
        3.18,
        "2010–19",
        color=MUTED,
        fontsize=9,
        style="italic",
        alpha=0.9,
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
        "Per cent of GDP",
        transform=ax_invest.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax_invest.set_xlim(1999.7, 2025.4)
    ax_invest.set_ylim(0, 3.35)
    ax_invest.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax_invest.set_xticklabels(
        ["2000–01", "2005–06", "2010–11", "2015–16", "2020–21", "2025–26"]
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
        0.041,
        "Note: 2000–01 to 2002–03 use PESA 2012; later years use PSS 2026. Each "
        "vintage is indexed to its own 2010–11 value; their overlap differs by no "
        "more than one index point.\nEducation is omitted because of an accounting "
        "break. Net investment is after depreciation and includes net capital grants.",
        ha="left",
        fontsize=8.4,
        color=MUTED,
        style="italic",
    )
    fig.text(
        0.057,
        0.015,
        "Source: HM Treasury, PESA 2012 Table 4.3 and Public Spending Statistics "
        "July 2026, Tables 4.1 and 4.3. Context: New York Times / IFS, 2019.",
        ha="left",
        fontsize=8.4,
        color=MUTED,
        style="italic",
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.065, right=0.955, top=0.79, bottom=0.12)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return output
