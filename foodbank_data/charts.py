"""Publication-quality bar chart for Trussell emergency food parcel data."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GRID, MUTED, TEXT, house_style, source_note

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


def foodbank_chart(
    fiscal: pd.DataFrame,
    annual: pd.DataFrame,
    out_path: Path = PRIMARY_OUTPUT,
) -> Path:
    """Render one long-run bar chart with age composition where available."""
    fiscal = fiscal.sort_values("end_year").copy()
    annual = annual.sort_values("year")
    latest = annual.iloc[-1]

    # The long-run series uses fiscal observations through 2023/24. The latest
    # calendar-year observation is appended at 2025 and identified in the note.
    historical = fiscal.copy()
    historical["x"] = historical["end_year"].astype(float)
    latest_row = pd.DataFrame(
        [{
            "period_label": "2025",
            "x": float(latest["year"]),
            "total": float(latest["total"]),
            "adults": float(latest["adults"]),
            "children": float(latest["children"]),
        }]
    )

    no_age = historical[historical["children"].isna()]
    age = historical[historical["children"].notna()]

    fig, ax = plt.subplots(figsize=(13.6, 7.8))

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
    ax.bar(
        latest_row["x"],
        latest_row["adults"],
        width=0.72,
        color=ADULT,
        edgecolor=BG,
        linewidth=0.8,
        zorder=3,
    )
    ax.bar(
        latest_row["x"],
        latest_row["children"],
        width=0.72,
        bottom=latest_row["adults"],
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
    ax.text(
        latest["year"],
        latest["total"] + 72_000,
        _total_label(float(latest["total"])),
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=ACCENT,
        fontweight="bold",
    )

    # Directly identify the child share without adding a second chart.
    ax.text(
        latest["year"],
        latest["adults"] + latest["children"] / 2,
        f"{latest['children'] / 1_000:.0f}k\nchildren",
        ha="center",
        va="center",
        fontsize=8.5,
        color=TEXT,
        fontweight="bold",
    )

    ax.set_xlim(1999.7, 2026.0)
    ax.set_ylim(0, 3_500_000)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_xticklabels(["2000", "2005", "2010", "2015", "2020", "2025"])
    ax.yaxis.set_major_locator(mtick.MultipleLocator(500_000))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))
    ax.set_ylabel("Emergency food parcels distributed")
    ax.set_xlabel("Reporting year ending")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
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
        "UK totals. Gold shows parcels distributed for children where the age "
        "breakdown is available.",
        ha="left",
        fontsize=11,
        color=MUTED,
    )

    source_note(
        fig,
        "Sources: Trussell archived reports and official 2023/24 fiscal dataset; "
        f"2025 calendar-year workbook. Accessed {ACCESSED_DATE}.\n"
        "2005/06–2023/24 are financial years; the final bar is calendar-year 2025. "
        "Counts are distribution instances, not unique people.",
        x=0.075,
        y=0.022,
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
