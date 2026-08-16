"""Publication-quality charts for Trussell emergency food parcel data."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GRID, MUTED, TEXT, house_style, source_note

from .sources import ACCESSED_DATE, OUTPUT_DIR

house_style()

ADULT = ACCENT
CHILD = GOLD
TOTAL = TEXT


def _millions(value: float, _position: int | None = None) -> str:
    return f"{value / 1_000_000:.1f}m"


def _percent(value: float) -> str:
    return f"{value:+.0f}%"


def _stacked_parcels(
    ax,
    frame: pd.DataFrame,
    *,
    highlight_year: int,
    width: float = 0.72,
) -> None:
    x = frame["year"].to_numpy()
    adults = frame["adults"].to_numpy()
    children = frame["children"].to_numpy()
    colors_adult = [ADULT if year == highlight_year else "#D99A88" for year in x]
    colors_child = [CHILD if year == highlight_year else "#D8C58D" for year in x]

    ax.bar(x, adults, width=width, color=colors_adult, edgecolor=BG, linewidth=0.7)
    ax.bar(
        x,
        children,
        width=width,
        bottom=adults,
        color=colors_child,
        edgecolor=BG,
        linewidth=0.7,
    )
    ax.plot(
        x,
        frame["total"],
        color=TOTAL,
        linewidth=1.8,
        marker="o",
        markersize=3.8,
        markerfacecolor=BG,
        markeredgewidth=1.2,
        zorder=4,
    )
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.set_xticks(x)
    ax.margins(x=0.025)


def annual_chart(
    frame: pd.DataFrame,
    out_path: Path = OUTPUT_DIR / "trussell_food_parcels_annual.png",
) -> Path:
    frame = frame.sort_values("year")
    latest = frame.iloc[-1]

    fig, ax = plt.subplots(figsize=(13.2, 7.4))
    _stacked_parcels(ax, frame, highlight_year=int(latest["year"]))

    ax.axvspan(2019.55, 2021.45, color="#73808A", alpha=0.08, linewidth=0)
    ax.text(
        2020.5,
        3_425_000,
        "pandemic",
        ha="center",
        color=MUTED,
        fontsize=9,
        style="italic",
    )
    ax.axvline(2016, color=GRID, linewidth=1.1, linestyle=(0, (3, 3)), zorder=0)
    ax.text(
        2016.08,
        2_790_000,
        "four-year working-age\nbenefit freeze begins",
        color=MUTED,
        fontsize=8.5,
        va="top",
    )
    ax.axvspan(2021.55, 2023.45, color=GOLD, alpha=0.055, linewidth=0)
    ax.text(
        2022.5,
        3_425_000,
        "cost-of-living shock",
        ha="center",
        color=MUTED,
        fontsize=9,
        style="italic",
    )

    for _, row in frame.iterrows():
        if int(row["year"]) in {2015, 2019, 2023, 2024, 2025}:
            ax.text(
                row["year"],
                row["total"] + 68_000,
                f"{row['total'] / 1_000_000:.2f}m",
                ha="center",
                va="bottom",
                fontsize=9.2,
                fontweight="bold" if row["year"] == latest["year"] else "normal",
                color=TOTAL if row["year"] == latest["year"] else MUTED,
            )

    ax.annotate(
        (
            f"{latest['total'] / 1_000_000:.2f}m parcels in 2025\n"
            f"{_percent(latest['change_vs_previous_pct'])} vs 2024; "
            f"{_percent(latest['change_vs_2019_pct'])} vs 2019"
        ),
        xy=(latest["year"], latest["total"]),
        xytext=(2021.8, 1_510_000),
        fontsize=12.5,
        fontweight="bold",
        color=TEXT,
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1.6},
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": BG,
            "edgecolor": ACCENT,
            "linewidth": 1.1,
        },
    )

    ax.set_ylim(0, 3_620_000)
    ax.set_ylabel("Emergency food parcels distributed")
    ax.set_xlabel("Calendar year")
    ax.set_title(
        "The UK’s food-bank emergency has receded from its peak — not gone away",
        loc="left",
        fontsize=19,
        pad=24,
    )
    ax.text(
        0,
        1.02,
        (
            "Food banks in Trussell’s UK community, full calendar years. "
            "Each parcel records an emergency food supply for one recipient."
        ),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        color=MUTED,
        fontsize=11,
    )

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=ADULT),
        plt.Rectangle((0, 0), 1, 1, color=CHILD),
        plt.Line2D([0], [0], color=TOTAL, marker="o", markerfacecolor=BG, linewidth=1.8),
    ]
    ax.legend(
        legend_handles,
        ["Adults", "Children", "Total"],
        loc="upper left",
        ncol=3,
        bbox_to_anchor=(0, 0.96),
        frameon=False,
        handlelength=1.7,
        columnspacing=1.6,
    )

    source_note(
        fig,
        (
            "Source: Trussell, End of year food bank stats and official 2025 "
            f"parcel-statistics workbook; accessed {ACCESSED_DATE}.\n"
            "Parcels measure supplies distributed, not unique people, and exclude "
            "independent food banks. Three- and seven-day parcels are combined; "
            "context markers are descriptive, not causal."
        ),
        x=0.075,
        y=0.012,
    )
    fig.tight_layout(rect=[0.04, 0.07, 0.99, 0.98])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out_path


def midyear_chart(
    frame: pd.DataFrame,
    out_path: Path = OUTPUT_DIR / "trussell_food_parcels_midyear.png",
) -> Path:
    frame = frame.sort_values("year")
    latest = frame.iloc[-1]

    fig, ax = plt.subplots(figsize=(11.8, 6.6))
    _stacked_parcels(ax, frame, highlight_year=int(latest["year"]), width=0.67)
    ax.set_ylim(0, 1_710_000)
    ax.set_ylabel("Emergency food parcels distributed")
    ax.set_xlabel("Six-month period (1 April–30 September)")
    ax.set_title(
        "The latest mid-year count dipped — but remained 69% above 2019",
        loc="left",
        fontsize=18,
        pad=23,
    )
    ax.text(
        0,
        1.02,
        "A separate, like-for-like six-month series; do not compare its height with full-year totals.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        color=MUTED,
        fontsize=10.5,
    )

    for _, row in frame.iterrows():
        ax.text(
            row["year"],
            row["total"] + 36_000,
            f"{row['total'] / 1_000_000:.2f}m",
            ha="center",
            fontsize=8.8,
            color=TOTAL if row["year"] == latest["year"] else MUTED,
            fontweight="bold" if row["year"] == latest["year"] else "normal",
        )

    ax.annotate(
        (
            f"Apr–Sep 2024: {latest['total']:,}\n"
            f"{_percent(latest['change_vs_previous_pct'])} vs 2023; "
            f"{_percent(latest['change_vs_2019_pct'])} vs 2019"
        ),
        xy=(latest["year"], latest["total"]),
        xytext=(2020.8, 510_000),
        fontsize=12,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1.5},
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": BG,
            "edgecolor": ACCENT,
            "linewidth": 1.1,
        },
    )

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=ADULT),
        plt.Rectangle((0, 0), 1, 1, color=CHILD),
        plt.Line2D([0], [0], color=TOTAL, marker="o", markerfacecolor=BG, linewidth=1.8),
    ]
    ax.legend(
        legend_handles,
        ["Adults", "Children", "Total"],
        loc="upper left",
        ncol=3,
        bbox_to_anchor=(0, 0.96),
        frameon=False,
        handlelength=1.7,
        columnspacing=1.6,
    )

    source_note(
        fig,
        (
            f"Source: Trussell, Mid-year stats and official 2024 workbook; accessed "
            f"{ACCESSED_DATE}. Periods always cover 1 April–30 September.\n"
            "Parcels are not unique people and exclude independent food banks. Trussell "
            "did not publish 2025/26 mid-year figures while moving to calendar-year reporting."
        ),
        x=0.075,
        y=0.012,
    )
    fig.tight_layout(rect=[0.04, 0.075, 0.99, 0.98])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out_path


def history_chart(
    frame: pd.DataFrame,
    out_path: Path = OUTPUT_DIR / "trussell_food_parcels_history.png",
) -> Path:
    """Show the archived fiscal series without inventing pre-series zeros."""
    frame = frame.sort_values("start_year")
    early = frame[frame["end_year"] <= 2012]
    later = frame[frame["end_year"] > 2012]

    fig = plt.figure(figsize=(13.6, 8.6))
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.15, 4.2],
        width_ratios=[1.02, 2.35],
        hspace=0.18,
        wspace=0.22,
    )
    timeline = fig.add_subplot(grid[0, :])
    ax_early = fig.add_subplot(grid[1, 0])
    ax_later = fig.add_subplot(grid[1, 1])

    fig.suptitle(
        "From one food bank to millions of emergency food parcels",
        x=0.07,
        y=0.97,
        ha="left",
        fontsize=20,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.925,
        (
            "Trussell’s financial-year archive begins in 2005/06. "
            "The years before that are history milestones — not zero parcel counts."
        ),
        ha="left",
        color=MUTED,
        fontsize=11,
    )

    timeline.set_xlim(1999.5, 2025.7)
    timeline.set_ylim(0, 1)
    timeline.axhline(0.5, color=GRID, linewidth=2)
    timeline.axvspan(1999.5, 2005, color="#73808A", alpha=0.08, linewidth=0)
    timeline.text(
        2002.4,
        0.51,
        "No national annual series\n(not zero)",
        ha="center",
        va="bottom",
        color=MUTED,
        fontsize=9,
        style="italic",
    )
    milestones = [
        (2000, "First Trussell\nfood bank", 0.18, "top"),
        (2004, "Foodbank Network\nlaunched", 0.82, "bottom"),
        (2005.45, "First archived\nannual observation", 0.18, "top"),
        (2017.45, "Modern methodology:\ncomparable from 2017/18", 0.82, "bottom"),
        (2025, "Reporting moves to\ncalendar years", 0.18, "top"),
    ]
    for x, label, y, va in milestones:
        timeline.scatter(x, 0.5, s=42, color=ACCENT, edgecolor=BG, zorder=3)
        timeline.plot([x, x], [0.5, y], color=GRID, linewidth=1)
        timeline.text(
            x,
            y,
            label,
            ha="center",
            va=va,
            fontsize=8.8,
            color=TEXT,
            fontweight="bold" if x in {2000, 2005.45} else "normal",
        )
    timeline.set_xticks([])
    timeline.set_yticks([])
    for spine in timeline.spines.values():
        spine.set_visible(False)

    early_x = range(len(early))
    ax_early.bar(
        early_x,
        early["total"],
        width=0.72,
        color=BLUE,
        edgecolor=BG,
        linewidth=0.7,
    )
    ax_early.set_xticks(list(early_x), early["period_label"], rotation=45, ha="right")
    ax_early.set_ylim(0, 145_000)
    ax_early.yaxis.set_major_formatter(
        mtick.FuncFormatter(lambda value, _pos: f"{value / 1000:.0f}k")
    )
    ax_early.set_title(
        "The network’s first seven annual counts",
        loc="left",
        fontsize=12.5,
        pad=12,
    )
    ax_early.set_ylabel("Reported people fed / parcels")
    ax_early.grid(axis="y")
    ax_early.set_axisbelow(True)
    for x, total in zip(early_x, early["total"]):
        ax_early.text(
            x,
            total + 3_200,
            f"{int(total):,}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=TEXT,
            rotation=90 if total < 20_000 else 0,
        )

    later_x = range(len(later))
    later_colors = [
        BLUE if group == "historical_archive" else ACCENT
        for group in later["comparability_group"]
    ]
    ax_later.bar(
        later_x,
        later["total"],
        width=0.72,
        color=later_colors,
        edgecolor=BG,
        linewidth=0.7,
    )
    ax_later.set_xticks(list(later_x), later["period_label"], rotation=45, ha="right")
    ax_later.set_ylim(0, 3_430_000)
    ax_later.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax_later.set_title(
        "Financial-year totals rose above three million",
        loc="left",
        fontsize=12.5,
        pad=12,
    )
    ax_later.grid(axis="y")
    ax_later.set_axisbelow(True)

    boundary_index = later.index[later["comparability_group"] == "modern_fiscal"][0]
    boundary_position = later.index.get_loc(boundary_index) - 0.5
    ax_later.axvline(
        boundary_position,
        color=GRID,
        linewidth=1.2,
        linestyle=(0, (3, 3)),
    )
    ax_later.text(
        boundary_position - 0.1,
        3_300_000,
        "archive reports",
        ha="right",
        va="top",
        fontsize=8.5,
        color=BLUE,
        style="italic",
    )
    ax_later.text(
        boundary_position + 0.1,
        3_300_000,
        "modern fiscal table",
        ha="left",
        va="top",
        fontsize=8.5,
        color=ACCENT,
        style="italic",
    )

    label_periods = {"2012/13", "2013/14", "2017/18", "2018/19", "2020/21", "2023/24"}
    for x, (_, row) in zip(later_x, later.iterrows()):
        if row["period_label"] in label_periods:
            ax_later.text(
                x,
                row["total"] + 72_000,
                f"{row['total'] / 1_000_000:.2f}m",
                ha="center",
                va="bottom",
                fontsize=8.8,
                color=TEXT,
                fontweight="bold" if row["period_label"] == "2023/24" else "normal",
            )

    ax_later.annotate(
        "2023/24 fiscal peak\n3,121,404 parcels",
        xy=(len(later) - 1, later.iloc[-1]["total"]),
        xytext=(len(later) - 4.2, 2_250_000),
        fontsize=11.5,
        fontweight="bold",
        color=TEXT,
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1.4},
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": BG,
            "edgecolor": ACCENT,
            "linewidth": 1,
        },
    )

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE),
        plt.Rectangle((0, 0), 1, 1, color=ACCENT),
    ]
    ax_later.legend(
        legend_handles,
        ["Figures in archived annual reports", "Official 2023/24 fiscal dataset"],
        loc="upper left",
        frameon=False,
        fontsize=9,
    )

    source_note(
        fig,
        (
            "Sources: Trussell UK foodbank network report (2012); Trussell filed accounts "
            "and annual reports (2012/13–2017/18); official 2023/24 slide dataset and "
            f"methodology; accessed {ACCESSED_DATE}.\n"
            "Breaks matter: archive wording evolved from ‘people fed’ to three-day supplies; "
            "the modern source is explicitly comparable from 2017/18 and combines three- "
            "and seven-day parcels from April 2020. Fiscal totals are not joined to the "
            "separate calendar-year series."
        ),
        x=0.07,
        y=0.012,
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.89, bottom=0.14)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out_path


def make_charts(
    annual: pd.DataFrame,
    midyear: pd.DataFrame,
    fiscal: pd.DataFrame | None = None,
    out_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    out_dir = Path(out_dir)
    written = [
        annual_chart(annual, out_dir / "trussell_food_parcels_annual.png"),
        midyear_chart(midyear, out_dir / "trussell_food_parcels_midyear.png"),
    ]
    if fiscal is not None:
        written.insert(
            0,
            history_chart(fiscal, out_dir / "trussell_food_parcels_history.png"),
        )
    return written
