"""Clear long-run charts for Trussell emergency food parcel data."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, MUTED, TEXT, house_style, source_note

from .sources import ACCESSED_DATE, OUTPUT_DIR

house_style()

PRIMARY_OUTPUT = OUTPUT_DIR / "trussell_food_parcels.png"


def _millions(value: float, _position: int | None = None) -> str:
    if value == 0:
        return "0"
    return f"{value / 1_000_000:.2g}m"


def _label(ax, x: float, y: float, text: str, color: str, *, dx=0, dy=9) -> None:
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
    """Render aligned total and child-recipient panels on one timeline."""
    fiscal = fiscal.sort_values("end_year")
    annual = annual.sort_values("year")
    latest = annual.iloc[-1]

    total_history = fiscal[["end_year", "total"]].rename(columns={"end_year": "year"})
    child_history = fiscal.dropna(subset=["children"])[
        ["end_year", "children"]
    ].rename(columns={"end_year": "year"})

    fig, (ax_total, ax_child) = plt.subplots(
        2,
        1,
        figsize=(13.4, 8.8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.55, 1], "hspace": 0.36},
    )

    ax_total.plot(
        total_history["year"],
        total_history["total"],
        color=BLUE,
        linewidth=3,
        solid_capstyle="round",
    )
    ax_total.scatter(
        total_history["year"],
        total_history["total"],
        s=24,
        color=BLUE,
        edgecolor=BG,
        linewidth=0.8,
        zorder=4,
    )
    ax_total.scatter(
        [latest["year"]],
        [latest["total"]],
        s=44,
        color=ACCENT,
        edgecolor=BG,
        linewidth=0.9,
        zorder=5,
    )
    ax_total.plot(
        [total_history.iloc[-1]["year"], latest["year"]],
        [total_history.iloc[-1]["total"], latest["total"]],
        color=ACCENT,
        linewidth=1.4,
        linestyle=(0, (2, 3)),
        alpha=0.75,
    )

    ax_child.plot(
        child_history["year"],
        child_history["children"],
        color=GOLD,
        linewidth=3,
        solid_capstyle="round",
    )
    ax_child.scatter(
        child_history["year"],
        child_history["children"],
        s=27,
        color=GOLD,
        edgecolor=BG,
        linewidth=0.8,
        zorder=4,
    )
    ax_child.scatter(
        [latest["year"]],
        [latest["children"]],
        s=44,
        color=ACCENT,
        edgecolor=BG,
        linewidth=0.9,
        zorder=5,
    )
    ax_child.plot(
        [child_history.iloc[-1]["year"], latest["year"]],
        [child_history.iloc[-1]["children"], latest["children"]],
        color=ACCENT,
        linewidth=1.4,
        linestyle=(0, (2, 3)),
        alpha=0.75,
    )

    # Sparse direct labels only.
    first = total_history.iloc[0]
    fiscal_peak = total_history.iloc[-1]
    _label(ax_total, first["year"], first["total"], "2,814", BLUE)
    _label(ax_total, fiscal_peak["year"], fiscal_peak["total"], "3.12m", BLUE, dx=-8)
    _label(ax_total, latest["year"], latest["total"], "2.64m", ACCENT)

    first_child = child_history.iloc[0]
    last_child = child_history.iloc[-1]
    _label(ax_child, first_child["year"], first_child["children"], "586k", GOLD)
    _label(ax_child, last_child["year"], last_child["children"], "1.14m", GOLD, dx=-8)
    _label(ax_child, latest["year"], latest["children"], "912k", ACCENT)

    for ax in (ax_total, ax_child):
        ax.set_xlim(1999.7, 2026.2)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(_millions))

    ax_total.set_ylim(0, 3_500_000)
    ax_total.yaxis.set_major_locator(mtick.MultipleLocator(500_000))
    ax_total.set_title(
        "All emergency food parcels",
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=TEXT,
        pad=8,
    )

    ax_child.set_ylim(0, 1_300_000)
    ax_child.yaxis.set_major_locator(mtick.MultipleLocator(250_000))
    ax_child.set_title(
        "Parcels distributed for children",
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=TEXT,
        pad=8,
    )
    ax_child.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax_child.set_xticklabels(["2000", "2005", "2010", "2015", "2020", "2025"])
    ax_child.set_xlabel("Reporting year ending")

    fig.suptitle(
        "Emergency food parcels distributed by Trussell food banks",
        x=0.075,
        y=0.972,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.075,
        0.925,
        "UK totals. Child-recipient breakdowns are available from 2018/19.",
        ha="left",
        fontsize=11,
        color=MUTED,
    )

    source_note(
        fig,
        "Sources: Trussell archived reports and official 2023/24 fiscal dataset; "
        f"2025 calendar-year workbook. Accessed {ACCESSED_DATE}.\n"
        "2005/06–2023/24 observations are financial years; the dotted final segment "
        "leads to calendar-year 2025. Counts are distribution instances, not unique people.",
        x=0.075,
        y=0.018,
    )

    fig.subplots_adjust(left=0.075, right=0.975, top=0.86, bottom=0.13)
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
