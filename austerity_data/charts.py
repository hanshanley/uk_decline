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
    end_year: str = END_YEAR,
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

    fig = plt.figure(figsize=(15.2, 9.6), facecolor=BG)
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[2.15, 1],
        height_ratios=[1.45, 1],
        hspace=0.42,
        wspace=0.28,
    )
    ax_lines = fig.add_subplot(grid[0, 0])
    ax_bars = fig.add_subplot(grid[0, 1])
    ax_invest = fig.add_subplot(grid[1, :])

    fig.suptitle(
        "Austerity did not shrink every budget equally",
        x=0.055,
        y=0.985,
        ha="left",
        fontsize=25,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.057,
        0.932,
        "By 2019, the IFS estimated £40bn had been cut from departmental spending. "
        "Protected health rose; housing, culture, policing and investment absorbed the squeeze.",
        ha="left",
        fontsize=13.5,
        color=MUTED,
    )

    # Panel A: two decades of real functional spending around austerity.
    for category, (label, color, width) in SERIES.items():
        series = indexed_function_series(df, category)
        ax_lines.plot(
            series["year"],
            series["index"],
            color=color,
            linewidth=width,
            marker="o",
            markersize=4.5,
            markeredgecolor=BG,
            markeredgewidth=0.8,
            zorder=4,
        )
        last = series.iloc[-1]
        _label(
            ax_lines,
            float(last["year"]),
            float(last["index"]),
            f"{label}  {last['index']:.0f}",
            color,
        )

    ax_lines.axvspan(2000, 2009.9, color=BLUE, alpha=0.035, linewidth=0)
    ax_lines.text(
        2000.25,
        119.2,
        "PRE-AUSTERITY EXPANSION",
        color=BLUE,
        fontsize=8.5,
        fontweight="bold",
    )
    ax_lines.axhline(100, color=TEXT, linewidth=0.8, alpha=0.45)
    ax_lines.text(2010.05, 101.2, "2010–11 level", color=MUTED, fontsize=9.5)
    ax_lines.set_title(
        "Two decades of real public spending by function",
        loc="left",
        fontsize=16,
        pad=12,
    )
    ax_lines.text(
        0,
        1.01,
        "Index, 2010–11 = 100",
        transform=ax_lines.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax_lines.set_xlim(1999.7, 2022.35)
    ax_lines.set_ylim(48, 130)
    ax_lines.set_xticks([2000, 2005, 2010, 2015, 2019])
    ax_lines.set_xticklabels(
        ["2000–01", "2005–06", "2010–11", "2015–16", "2019–20"]
    )
    ax_lines.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    _style_axis(ax_lines)

    housing = indexed_function_series(df, "housing_community")
    austerity_housing = housing[housing["financial_year"] >= BASE_YEAR]
    low = austerity_housing.loc[austerity_housing["index"].idxmin()]
    ax_lines.annotate(
        f"Housing bottomed at {low['index']:.0f}\n({low['financial_year']})",
        xy=(low["year"], low["index"]),
        xytext=(2011.4, 59),
        color=ACCENT,
        fontsize=10.5,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1.2},
    )

    # Panel B: the deepest fall each selected service experienced by 2019-20.
    bar_categories = [
        "housing_community",
        "recreation_culture",
        "public_order_safety",
        "defence",
        "health",
    ]
    labels = {
        "housing_community": "Housing & community",
        "recreation_culture": "Culture & recreation",
        "public_order_safety": "Public order & safety",
        "defence": "Defence",
        "health": "Health",
    }
    colors = [ACCENT, GOLD, BLUE, MUTED, GREEN]
    changes = [trough_change(df, category) for category in bar_categories]
    values = [change for change, _year in changes]
    y = list(range(len(bar_categories)))
    ax_bars.barh(y, values, color=colors, height=0.58, alpha=0.95)
    ax_bars.axvline(0, color=TEXT, linewidth=0.8)
    for pos, value, (_change, year), color in zip(y, values, changes, colors):
        ax_bars.text(
            -1.1 if value < -5 else value + 0.7,
            pos,
            f"{value:.0f}%",
            va="center",
            ha="right" if value < -5 else "left",
            color="white" if value < -5 else color,
            fontsize=10.5,
            fontweight="bold",
        )
        ax_bars.text(
            -35.8,
            pos + 0.31,
            f"trough {year}",
            color=MUTED,
            fontsize=8.3,
            va="top",
        )
    ax_bars.set_yticks([])
    for pos, category in zip(y, bar_categories):
        ax_bars.text(
            -37.2,
            pos - 0.12,
            labels[category],
            color=TEXT,
            fontsize=10.2,
            va="center",
            ha="left",
        )
    ax_bars.invert_yaxis()
    ax_bars.set_xlim(-38, 4)
    ax_bars.set_title("Deepest real-terms fall", loc="left", fontsize=16, pad=12)
    ax_bars.text(
        0,
        1.01,
        "From 2010–11, through 2019–20",
        transform=ax_bars.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax_bars.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=100, decimals=0))
    ax_bars.grid(axis="x")
    ax_bars.spines["left"].set_visible(False)
    ax_bars.spines["bottom"].set_visible(False)
    ax_bars.tick_params(axis="x", labelbottom=False)

    # Panel C: public sector net investment, with the austerity period shaded.
    investment = df[
        (df["metric"] == "public_sector_net_investment_pct_gdp")
        & (df["year"] >= 2000)
        & (df["year"] <= 2019)
    ].sort_values("year")
    ax_invest.axvspan(2010, 2019.9, color=ACCENT, alpha=0.07, linewidth=0)
    ax_invest.fill_between(
        investment["year"],
        investment["value"],
        0,
        color=ACCENT,
        alpha=0.16,
    )
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
    ax_invest.annotate(
        f"{start['value']:.1f}% of GDP",
        (start["year"], start["value"]),
        xytext=(2009.25, 2.72),
        fontsize=11,
        color=TEXT,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 1},
    )
    ax_invest.annotate(
        f"{trough['value']:.1f}% — the low",
        (trough["year"], trough["value"]),
        xytext=(2014.2, 1.25),
        fontsize=11,
        color=ACCENT,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1.2},
    )
    ax_invest.text(
        2010.25,
        3.22,
        "AUSTERITY PERIOD",
        color=ACCENT,
        fontsize=9,
        fontweight="bold",
        alpha=0.9,
    )
    ax_invest.set_title(
        "Public sector net investment was cut first",
        loc="left",
        fontsize=16,
        pad=12,
    )
    ax_invest.text(
        0,
        1.01,
        "Net capital investment as a share of GDP",
        transform=ax_invest.transAxes,
        color=MUTED,
        fontsize=10,
    )
    ax_invest.set_xlim(1999.7, 2019.4)
    ax_invest.set_ylim(0, 3.4)
    ax_invest.set_xticks([2000, 2005, 2010, 2013, 2016, 2019])
    ax_invest.set_xticklabels(
        ["2000–01", "2005–06", "2010–11", "2013–14", "2016–17", "2019–20"]
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
        0.035,
        "Note: Functional series for 2000–01 to 2002–03 use PESA 2012 and later "
        "years use PSS 2026; each vintage is indexed to its own 2010–11 value "
        "(their 2003–04 overlap differs by no more than one index point). Troughs "
        "are minima through 2019–20. Education is omitted because of an accounting break.",
        ha="left",
        fontsize=8.4,
        color=MUTED,
        style="italic",
    )
    fig.text(
        0.057,
        0.014,
        "Source: HM Treasury, PESA 2012 Table 4.3 and Public Spending Statistics, "
        "July 2026, Tables 4.1 and 4.3. Context: New York Times, 24 Feb. 2019, citing the Institute "
        "for Fiscal Studies (£40bn departmental cuts; some budgets cut 30–40%).",
        ha="left",
        fontsize=8.4,
        color=MUTED,
        style="italic",
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.07, right=0.95, top=0.84, bottom=0.11)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return output
