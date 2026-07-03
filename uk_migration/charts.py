"""Render summary time-series charts (PNG) from the combined UK migration table.

Charts use the shared "Substack" serif theme (cream background, muted axes, no top/right
spines, frameless legends) so they match the sibling ``pre1870_reapportionment_package``
figures.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .combine import COMBINED_CSV

FIGURES_DIR = Path("figures")

# ---- Substack theme (matches pre1870_reapportionment_package) --------------
SUBSTACK_BG = "#F7F5F0"
SUBSTACK_TEXT = "#1A1A1A"
SUBSTACK_MUTED = "#6B6B6B"
SUBSTACK_ACCENT = "#C85A3D"
SUBSTACK_BLUE = "#3D6F8C"
SUBSTACK_GOLD = "#C2993E"
SUBSTACK_GREEN = "#4A7C59"
SUBSTACK_GRID = "#D6D3CC"

_THEME = {
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
}

plt.rcParams.update(_THEME)


def _load(source: pd.DataFrame | str | Path | None) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source
    return pd.read_csv(source or COMBINED_CSV)


def _series(df: pd.DataFrame, metric: str, category: str = "all") -> pd.DataFrame:
    sel = df[(df["metric"] == metric) & (df["category"] == category)]
    return sel.sort_values("period")


def _save(fig, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def _format_yaxis(ax, thousands: bool = True) -> None:
    """Apply the house y-axis grid and (optionally) a thousands separator."""
    if thousands:
        ax.yaxis.set_major_formatter(lambda v, _pos: f"{v:,.0f}")
    ax.grid(axis="y", linestyle="-", linewidth=0.5)


def _style_title(ax, title: str) -> None:
    ax.set_title(title, fontweight="bold", pad=14)


def chart_net_migration(df: pd.DataFrame) -> Path:
    ons = _series(df, "net_migration")
    wb = _series(df, "net_migration_wb")
    fig, ax = plt.subplots(figsize=(11, 6))
    if not wb.empty:
        ax.plot(
            wb["period"], wb["value"], marker="s", markersize=4, linestyle="--",
            color=SUBSTACK_MUTED, alpha=0.7, label="World Bank net migration (modelled)",
        )
    if not ons.empty:
        ax.plot(
            ons["period"], ons["value"], marker="o", color=SUBSTACK_BLUE,
            label="ONS net migration (annual)",
        )
    ax.axhline(0, color=SUBSTACK_TEXT, linewidth=0.8)
    _style_title(ax, "UK net long-term migration over time")
    ax.set_xlabel("Year")
    ax.set_ylabel("People (net)")
    ax.legend(loc="upper left", frameon=False)
    _format_yaxis(ax)
    return _save(fig, "net_migration.png")


def chart_inflow_outflow(df: pd.DataFrame) -> Path:
    imm = _series(df, "immigration")
    emi = _series(df, "emigration")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(imm["period"], imm["value"], marker="o", color=SUBSTACK_BLUE, label="Immigration (inflow)")
    ax.plot(emi["period"], emi["value"], marker="o", color=SUBSTACK_ACCENT, label="Emigration (outflow)")
    _style_title(ax, "UK immigration vs emigration (ONS long-term)")
    ax.set_xlabel("Year")
    ax.set_ylabel("People per year")
    ax.legend(loc="upper left", frameon=False)
    _format_yaxis(ax)
    return _save(fig, "immigration_vs_emigration.png")


def chart_visas_by_category(df: pd.DataFrame) -> Path:
    colors = {"work": SUBSTACK_BLUE, "study": SUBSTACK_GREEN, "family": SUBSTACK_GOLD}
    fig, ax = plt.subplots(figsize=(11, 6))
    for category, color in colors.items():
        s = _series(df, "visas_granted", category)
        if not s.empty:
            ax.plot(s["period"], s["value"], marker="o", color=color, label=category.capitalize())
    _style_title(ax, "UK entry-clearance visas granted by category")
    ax.set_xlabel("Year")
    ax.set_ylabel("Visas issued per year")
    ax.legend(loc="upper left", frameon=False)
    _format_yaxis(ax)
    return _save(fig, "visas_by_category.png")


def chart_asylum(df: pd.DataFrame) -> Path:
    s = _series(df, "asylum_applications", "main_applicant")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(s["period"], s["value"], marker="o", color=SUBSTACK_ACCENT)
    _style_title(ax, "UK asylum applications (main applicants)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Claims per year")
    _format_yaxis(ax)
    return _save(fig, "asylum_applications.png")


def chart_irregular(df: pd.DataFrame) -> Path:
    total = _series(df, "irregular_arrivals", "all")
    boats = _series(df, "irregular_arrivals", "small_boat")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(total["period"], total["value"], marker="o", color=SUBSTACK_BLUE, label="All irregular arrivals")
    ax.plot(boats["period"], boats["value"], marker="o", color=SUBSTACK_ACCENT, label="Small boats")
    _style_title(ax, "UK irregular arrivals detected")
    ax.set_xlabel("Year")
    ax.set_ylabel("Detections per year")
    ax.legend(loc="upper left", frameon=False)
    _format_yaxis(ax)
    return _save(fig, "irregular_arrivals.png")


def chart_legal_vs_irregular(df: pd.DataFrame) -> Path:
    legal = _series(df, "immigration")
    irregular = _series(df, "irregular_arrivals", "all")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(legal["period"], legal["value"], marker="o", color=SUBSTACK_BLUE, label="Legal immigration (ONS inflow)")
    ax.plot(irregular["period"], irregular["value"], marker="o", color=SUBSTACK_ACCENT, label="Irregular arrivals (Home Office)")
    ax.set_yscale("log")
    _style_title(ax, "UK legal immigration vs irregular arrivals (log scale)")
    ax.set_xlabel("Year")
    ax.set_ylabel("People per year (log)")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, which="both", axis="y", linestyle="-", linewidth=0.5)
    return _save(fig, "legal_vs_irregular.png")


CHARTS = (
    chart_net_migration,
    chart_inflow_outflow,
    chart_visas_by_category,
    chart_asylum,
    chart_irregular,
    chart_legal_vs_irregular,
)


def render_all(source: pd.DataFrame | str | Path | None = None) -> list[Path]:
    """Render every chart from the combined table, returning the written PNG paths."""
    df = _load(source)
    return [chart(df) for chart in CHARTS]
