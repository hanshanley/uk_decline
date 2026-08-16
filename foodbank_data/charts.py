"""Clean long-run chart for Trussell emergency food parcel data."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GRID, MUTED, TEXT, house_style, source_note

from .sources import ACCESSED_DATE, OUTPUT_DIR

house_style()

PRIMARY_OUTPUT = OUTPUT_DIR / "trussell_food_parcels.png"


def _millions(value: float, _position: int | None = None) -> str:
    if value == 0:
        return "0"
    return f"{value / 1_000_000:.1f}m"


def _label(ax, x: float, y: float, text: str, *, color: str, dx=0, dy=0) -> None:
    ax.annotate(
        text,
        (x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=color,
        fontweight="bold",
    )


def foodbank_chart(
    fiscal: pd.DataFrame,
    annual: pd.DataFrame,
    out_path: Path = PRIMARY_OUTPUT,
) -> Path:
    """Render one clear long-run chart, keeping reporting-period changes explicit."""
    fiscal = fiscal.sort_values("end_year")
    annual = annual.sort_values("year")

    # The fiscal series is the only sourced national series before 2015. Calendar
    # reporting is shown only for 2024-25 so the latest point is current without
    # pretending the two reporting periods are identical.
    calendar_tail = annual[annual["year"] >= 2024].copy()

    fig, ax = plt.subplots(figsize=(13.4, 7.6))

    ax.plot(
        fiscal["end_year"],
        fiscal["total"],
        color=BLUE,
        linewidth=3,
        solid_capstyle="round",
        label="Financial years",
        zorder=3,
    )
    ax.scatter(
        fiscal["end_year"],
        fiscal["total"],
        s=26,
        color=BLUE,
        edgecolor=BG,
        linewidth=0.8,
        zorder=4,
    )

    ax.plot(
        calendar_tail["year"],
        calendar_tail["total"],
        color=ACCENT,
        linewidth=3,
        solid_capstyle="round",
        label="Calendar years",
        zorder=5,
    )
    ax.scatter(
        calendar_tail["year"],
        calendar_tail["total"],
        s=38,
        color=ACCENT,
        edgecolor=BG,
        linewidth=0.9,
        zorder=6,
    )

    # One quiet divider explains the reporting change; there are no event bands or boxes.
    ax.axvline(2024.5, color=GRID, linewidth=1, linestyle=(0, (3, 4)), zorder=0)
    ax.text(
        2024.42,
        380_000,
        "calendar-year\nreporting",
        ha="right",
        va="bottom",
        fontsize=8.8,
        color=MUTED,
        style="italic",
    )

    # Sparse labels: first national observation, pre-pandemic level, fiscal peak, latest.
    points = {
        "2005/06": ("2,814", BLUE, -2, 11),
        "2011/12": ("129k", BLUE, 0, 10),
        "2018/19": ("1.61m", BLUE, 0, 10),
        "2023/24": ("3.12m", BLUE, -12, 10),
    }
    for period, (text, color, dx, dy) in points.items():
        row = fiscal.loc[fiscal["period_label"] == period].iloc[0]
        _label(
            ax,
            float(row["end_year"]),
            float(row["total"]),
            text,
            color=color,
            dx=dx,
            dy=dy,
        )

    latest = calendar_tail.iloc[-1]
    _label(
        ax,
        float(latest["year"]),
        float(latest["total"]),
        "2.64m in 2025",
        color=ACCENT,
        dx=0,
        dy=12,
    )

    ax.set_xlim(1999.7, 2026.2)
    ax.set_ylim(0, 3_500_000)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_xticklabels(["2000", "2005", "2010", "2015", "2020", "2025"])
    ax.yaxis.set_major_locator(mtick.MultipleLocator(500_000))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax.set_ylabel("Emergency food parcels distributed")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper left", frameon=False, ncol=2, handlelength=2.4)

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
        "UK totals. The national series begins in 2005/06; years before then are "
        "unreported, not zero.",
        ha="left",
        fontsize=11,
        color=MUTED,
    )

    source_note(
        fig,
        "Sources: Trussell archived reports and official 2023/24 fiscal dataset; "
        f"2025 calendar-year workbook. Accessed {ACCESSED_DATE}.\n"
        "Counts are distribution instances, not unique people. Reporting basis and "
        "parcel-duration definitions change; the fiscal and calendar lines are not joined.",
        x=0.075,
        y=0.025,
    )

    fig.subplots_adjust(left=0.075, right=0.975, top=0.84, bottom=0.15)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
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
    return [foodbank_chart(fiscal, annual, out_dir / PRIMARY_OUTPUT.name)]
