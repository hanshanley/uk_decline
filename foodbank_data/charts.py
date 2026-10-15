"""Publication-quality bar chart for Trussell emergency food parcel data."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GRID, MUTED, TEXT, house_style, source_note, save_chart

from .sources import ACCESSED_DATE, OUTPUT_DIR

house_style()

PRIMARY_OUTPUT = OUTPUT_DIR / "trussell_food_parcels.png"
TOTAL_ONLY = "#A8ADB0"
ADULT = BLUE
CHILD = GOLD


def _millions(value: float, _position: int | None = None) -> str:
    if value == 0:
        return "0"
    return f"{value / 1_000_000:.1f}m"


def _total_label(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}m"
    if value >= 100_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:,.0f}"


def foodbank_history_chart(
    fiscal: pd.DataFrame,
    annual: pd.DataFrame,
    out_path: Path = OUTPUT_DIR / "trussell_food_parcels_history.png",
) -> Path:
    """Render one long-run bar chart with age composition where available."""
    fiscal = fiscal.sort_values("end_year").copy()
    annual = annual.sort_values("year")
    latest = annual.iloc[-1]

    historical = fiscal.copy()
    historical["x"] = historical["end_year"].astype(float)

    no_age = historical[historical["children"].isna()]
    age = historical[historical["children"].notna()]

    fig, (ax, recent) = plt.subplots(
        1, 2, figsize=(13.6, 7.8), sharey=True,
        gridspec_kw={"width_ratios": [3.3, 1], "wspace": 0.12},
    )

    ax.bar(
        no_age["x"],
        no_age["total"],
        width=0.72,
        color=TOTAL_ONLY,
        edgecolor=BG,
        linewidth=0.8,
        label="Total (age breakdown unavailable)",
        zorder=3,
    )
    ax.bar(
        age["x"],
        age["adults"],
        width=0.72,
        color=ADULT,
        edgecolor=BG,
        linewidth=0.8,
        label="Adults",
        zorder=3,
    )
    ax.bar(
        age["x"],
        age["children"],
        width=0.72,
        bottom=age["adults"],
        color=CHILD,
        edgecolor=BG,
        linewidth=0.8,
        label="Children",
        zorder=3,
    )
    recent.bar(
        0,
        latest["adults"],
        width=0.72,
        color=ADULT,
        edgecolor=BG,
        linewidth=0.8,
        zorder=3,
    )
    recent.bar(
        0,
        latest["children"],
        width=0.72,
        bottom=latest["adults"],
        color=CHILD,
        edgecolor=BG,
        linewidth=0.8,
        zorder=3,
    )

    labels = {
        "2005/06": None,
        "2011/12": None,
        "2018/19": None,
        "2023/24": None,
    }
    for period in labels:
        row = historical.loc[historical["period_label"] == period].iloc[0]
        ax.text(
            row["x"],
            row["total"] + 72_000,
            _total_label(float(row["total"])),
            ha="center",
            va="bottom",
            fontsize=9.2,
            color=TEXT if period in {"2005/06", "2023/24"} else MUTED,
            fontweight="bold" if period in {"2005/06", "2023/24"} else "normal",
        )
    recent.text(
        0,
        latest["total"] + 72_000,
        _total_label(float(latest["total"])),
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=ACCENT,
        fontweight="bold",
    )

    for count, center, label, color in (
        (latest["adults"], latest["adults"] / 2, "adults", ADULT),
        (latest["children"], latest["adults"] + latest["children"] / 2,
         "children", CHILD),
    ):
        recent.annotate(
            f"{_total_label(float(count))} parcels\nfor {label}",
            xy=(0.36, center), xytext=(0.7, center),
            ha="left", va="center", fontsize=11, color=TEXT,
            arrowprops={"arrowstyle": "-", "color": color, "linewidth": 1.5},
        )

    ax.set_title(
        f"Financial years, {historical.iloc[0]['period_label']}"
        f"–{historical.iloc[-1]['period_label']}",
        loc="left", fontsize=12, fontweight="bold", pad=14,
    )
    recent.set_title(f"Calendar year {int(latest['year'])}",
                     loc="left", fontsize=12, fontweight="bold", pad=14)
    ax.set_xlim(historical["x"].min() - 0.7, historical["x"].max() + 0.8)
    recent.set_xlim(-0.65, 2.1)
    recent.set_xticks([])
    recent.tick_params(axis="y", left=False, labelleft=False)
    ax.set_ylim(0, max(float(historical["total"].max()), latest["total"]) * 1.14)
    ticks = historical[
        historical["end_year"].mod(5).eq(0)
        | historical["end_year"].isin(
            [historical.iloc[0]["end_year"], historical.iloc[-1]["end_year"]]
        )
    ]
    ax.set_xticks(ticks["x"], ticks["period_label"])
    ax.yaxis.set_major_locator(mtick.MultipleLocator(500_000))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax.set_ylabel("Emergency food parcels distributed")
    ax.set_xlabel("Financial year")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    recent.grid(axis="y")
    recent.set_axisbelow(True)
    recent.spines["left"].set_visible(False)
    ax.legend(
        loc="upper left",
        frameon=False,
        ncol=3,
        handlelength=1.5,
        columnspacing=1.5,
    )

    fig.suptitle(
        "Emergency food parcels distributed by Trussell food banks",
        x=0.075,
        y=0.965,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.075,
        0.91,
        "UK totals. Financial-year history and the latest calendar year shown separately.",
        ha="left",
        fontsize=11,
        color=MUTED,
    )

    source_note(
        fig,
        "Sources: Trussell archived reports and official 2023/24 fiscal dataset; "
        f"{int(latest['year'])} calendar-year workbook. Accessed {latest['accessed_date']}.\n"
        f"{historical.iloc[0]['period_label']}–{historical.iloc[-1]['period_label']} "
        f"are financial years; the right-hand panel is calendar-year {int(latest['year'])}. "
        "Counts are distribution instances, not unique people. "
        "From Apr 2020, 3-/7-day parcels are combined without duration adjustment.",
        x=0.075,
        y=0.022,
    )

    fig.subplots_adjust(left=0.075, right=0.975, top=0.8, bottom=0.15)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_chart(fig, out_path, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    return out_path


def foodbank_chart(
    annual: pd.DataFrame,
    out_path: Path = PRIMARY_OUTPUT,
) -> Path:
    """Compare complete January-December years without a reporting-basis break."""
    if annual.empty or not annual["period_type"].eq("calendar_year").all():
        raise ValueError("Primary food-bank chart requires calendar-year data")
    annual = annual.sort_values("year")
    first, latest = annual.iloc[0], annual.iloc[-1]
    peak = annual.loc[annual["total"].idxmax()]
    fig, ax = plt.subplots(figsize=(13.6, 7.8))
    ax.bar(
        annual["year"], annual["adults"], width=.72, color=ADULT,
        edgecolor=BG, linewidth=.8, label="Adults", zorder=3,
    )
    ax.bar(
        annual["year"], annual["children"], bottom=annual["adults"],
        width=.72, color=CHILD, edgecolor=BG, linewidth=.8,
        label="Children", zorder=3,
    )
    for year in sorted({int(first["year"]), int(peak["year"]), int(latest["year"])}):
        row = annual.loc[annual["year"] == year].iloc[0]
        ax.text(
            year, row["total"] + 65_000, _total_label(float(row["total"])),
            ha="center", va="bottom", fontsize=11, fontweight="bold",
            color=ACCENT if year == int(latest["year"]) else TEXT,
        )
    ax.set_xlim(first["year"] - .7, latest["year"] + .7)
    ax.set_ylim(0, float(annual["total"].max()) * 1.17)
    ax.set_xticks(annual["year"])
    ax.yaxis.set_major_locator(mtick.MultipleLocator(500_000))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax.set_ylabel("Emergency food parcels distributed")
    ax.set_xlabel("Calendar year (January-December)")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.suptitle(
        "Emergency food parcels distributed by Trussell food banks",
        x=.075, y=.965, ha="left", fontsize=20, fontweight="bold", color=TEXT,
    )
    fig.text(
        .075, .91,
        f"UK calendar years {int(first['year'])}-{int(latest['year'])}; "
        "every bar covers January-December.",
        fontsize=11, color=MUTED,
    )
    note = (
        f"Source: Trussell, {int(latest['year'])} calendar-year parcel-statistics workbook. "
        f"Accessed {latest['accessed_date']}. Counts are distribution instances, not unique people; "
        "Trussell's network, not all UK food banks. From Apr 2020, three- and seven-day "
        "parcels are combined without duration adjustment. Older April-March financial-year "
        "figures are preserved separately on GitHub, not spliced into this series."
    )
    source_note(fig, textwrap.fill(note, width=155), x=.075, y=.025)
    fig.subplots_adjust(left=.075, right=.975, top=.83, bottom=.18)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_chart(fig, out_path, dpi=220, bbox_inches="tight", pad_inches=.15, facecolor=BG)
    plt.close(fig)
    return out_path


def make_charts(
    annual: pd.DataFrame,
    midyear: pd.DataFrame,
    fiscal: pd.DataFrame | None = None,
    out_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    del midyear
    if fiscal is None:
        raise ValueError("fiscal history is required for the long-run food-bank chart")
    out_dir = Path(out_dir)
    return [
        foodbank_chart(annual, out_dir / PRIMARY_OUTPUT.name),
        foodbank_history_chart(fiscal, annual, out_dir / "trussell_food_parcels_history.png"),
    ]
