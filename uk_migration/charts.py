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
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from .combine import COMBINED_CSV

# Showcase charts are written here (a committable, non-git-ignored folder matching the
# sibling projects' `outputs/` convention). Each PNG carries a data-source caption.
FIGURES_DIR = Path("outputs/migration")

# Canonical data-source citations (stable landing pages / indicator IDs, not volatile
# per-quarter file URLs). Rendered as a caption on each chart and into SOURCES.md.
SOURCE_ONS = "ONS Long-Term International Migration (ons.gov.uk)"
SOURCE_ONS_IPS = "ONS IPS Long-Term International Migration, 1964\u20132015, ad hoc 006408 (ons.gov.uk)"
SOURCE_HO = "Home Office Immigration System Statistics (gov.uk)"
SOURCE_WB = "World Bank WDI (api.worldbank.org)"

# ---- Substack theme (shared vizstyle house style) --------------------------
from vizstyle import (  # noqa: E402
    BG as SUBSTACK_BG, TEXT as SUBSTACK_TEXT, MUTED as SUBSTACK_MUTED,
    ACCENT as SUBSTACK_ACCENT, BLUE as SUBSTACK_BLUE, GOLD as SUBSTACK_GOLD,
    GREEN as SUBSTACK_GREEN, GRID as SUBSTACK_GRID, house_style,
)

house_style()
# This analysis draws a log-scale axis whose tick labels use mathtext (10^6); the shared
# house style disables mathtext (to protect literal "$" labels elsewhere), so re-enable it
# here — uk_migration has no "$" labels, matching its original default behaviour.
plt.rcParams["text.parse_math"] = True


def _load(source: pd.DataFrame | str | Path | None) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source
    return pd.read_csv(source or COMBINED_CSV)


def _series(df: pd.DataFrame, metric: str, category: str = "all") -> pd.DataFrame:
    sel = df[(df["metric"] == metric) & (df["category"] == category)]
    return sel.sort_values("period")


def _save(fig, name: str, source: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.text(
        0.005, 0.005, f"Source: {source}", ha="left", va="bottom",
        fontsize=8, style="italic", color=SUBSTACK_MUTED,
    )
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def _style_axes(ax, thousands: bool = True, logy: bool = False) -> None:
    """Apply the house axes styling: integer year ticks, y grid, thousands separator."""
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    if thousands and not logy:
        ax.yaxis.set_major_formatter(lambda v, _pos: f"{v:,.0f}")
    which = "both" if logy else "major"
    ax.grid(which=which, axis="y", linestyle="-", linewidth=0.5)


def _style_title(ax, title: str) -> None:
    ax.set_title(title, fontweight="bold", pad=14)


def _plot_ons_methods(
    ax,
    df: pd.DataFrame,
    ips_metric: str,
    admin_metric: str,
    *,
    color: str = SUBSTACK_BLUE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Plot the two official ONS methods without splicing them into a fake single series."""
    ips = _series(df, ips_metric)
    admin = _series(df, admin_metric)
    if not ips.empty:
        ax.plot(
            ips["period"], ips["value"], color=color, linewidth=2.0,
            label="ONS IPS survey estimate (1964–2015)",
        )
    if not admin.empty:
        ax.plot(
            admin["period"], admin["value"], marker="o", color=color, linewidth=2.6,
            label="ONS administrative estimate (2012–2025)",
        )
    return ips, admin


def _annotate_peak_and_latest(ax, data: pd.DataFrame) -> None:
    if data.empty:
        return
    peak = data.loc[data["value"].idxmax()]
    latest = data.iloc[-1]
    for row, label, offset in (
        (peak, f"Peak {row_value_millions(peak['value'])}", (0, 12)),
        (latest, f"{int(latest['period'])}: {row_value_millions(latest['value'])}", (0, -20)),
    ):
        ax.annotate(
            label,
            xy=(row["period"], row["value"]),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=SUBSTACK_TEXT,
        )


def row_value_millions(value: float) -> str:
    return f"{value / 1_000_000:.2f}M"


def chart_immigration(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    _ips, admin = _plot_ons_methods(
        ax, df, "immigration_by_origin", "immigration"
    )
    _annotate_peak_and_latest(ax, admin)
    _style_title(ax, "UK long-term immigration over time (ONS only)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Immigration per year")
    ax.legend(loc="upper left", frameon=False)
    _style_axes(ax)
    return _save(fig, "immigration_over_time.png", _SOURCE_BY_ORIGIN)


def chart_net_migration(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    _ips, admin = _plot_ons_methods(
        ax, df, "net_migration_by_origin", "net_migration"
    )
    _annotate_peak_and_latest(ax, admin)
    ax.axhline(0, color=SUBSTACK_TEXT, linewidth=0.8)
    _style_title(ax, "UK net long-term migration over time (ONS only)")
    ax.set_xlabel("Year")
    ax.set_ylabel("People (net)")
    ax.legend(loc="upper left", frameon=False)
    _style_axes(ax)
    return _save(fig, "net_migration.png", _SOURCE_BY_ORIGIN)


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
    _style_axes(ax)
    return _save(fig, "immigration_vs_emigration.png", SOURCE_ONS)


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
    _style_axes(ax)
    return _save(fig, "visas_by_category.png", SOURCE_HO)


def chart_asylum(df: pd.DataFrame) -> Path:
    s = _series(df, "asylum_applications", "main_applicant")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(s["period"], s["value"], marker="o", color=SUBSTACK_ACCENT)
    _style_title(ax, "UK asylum applications (main applicants)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Claims per year")
    _style_axes(ax)
    return _save(fig, "asylum_applications.png", SOURCE_HO)


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
    _style_axes(ax)
    return _save(fig, "irregular_arrivals.png", SOURCE_HO)


def chart_legal_vs_irregular(df: pd.DataFrame) -> Path:
    total = _series(df, "immigration")
    irregular = _series(df, "irregular_arrivals", "all")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(total["period"], total["value"], marker="o", color=SUBSTACK_BLUE,
            label="Total long-term immigration (ONS)")
    ax.plot(irregular["period"], irregular["value"], marker="o", color=SUBSTACK_ACCENT, label="Irregular arrivals (Home Office)")
    ax.set_yscale("log")
    _style_title(ax, "UK total immigration vs detected irregular arrivals (log scale)")
    ax.set_xlabel("Year")
    ax.set_ylabel("People per year (log)")
    ax.legend(loc="upper left", frameon=False)
    _style_axes(ax, thousands=False, logy=True)
    return _save(fig, "legal_vs_irregular.png", f"{SOURCE_ONS}; {SOURCE_HO}")


def chart_net_migration_per_capita(df: pd.DataFrame) -> Path:
    ips = _series(df, "net_migration_by_origin_per_1000_pop")
    ons = _series(df, "net_migration_per_1000_pop")
    fig, ax = plt.subplots(figsize=(11, 6))
    if not ips.empty:
        ax.plot(
            ips["period"], ips["value"], color=SUBSTACK_BLUE, linewidth=2.0,
            label="ONS IPS survey estimate",
        )
    if not ons.empty:
        ax.plot(
            ons["period"], ons["value"], marker="o", color=SUBSTACK_BLUE, linewidth=2.6,
            label="ONS administrative estimate",
        )
    ax.axhline(0, color=SUBSTACK_TEXT, linewidth=0.8)
    _style_title(ax, "UK net migration per 1,000 population (ONS only)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Per 1,000 population")
    ax.legend(loc="upper left", frameon=False)
    _style_axes(ax, thousands=False)
    return _save(
        fig, "net_migration_per_capita.png",
        f"{SOURCE_ONS_IPS}; {SOURCE_ONS}; {SOURCE_WB} (population denominator only)",
    )


_ORIGIN_GROUPS = [
    ("all", SUBSTACK_TEXT, "All citizenships"),
    ("british", SUBSTACK_MUTED, "British"),
    ("eu", SUBSTACK_BLUE, "EU / EU+"),
    ("non_eu", SUBSTACK_ACCENT, "Non-EU / Non-EU+"),
]

# solid = historical IPS series (1964-2015); dashed = admin-based ONS series (2012+).
_METHOD_LEGEND = [
    Line2D([0], [0], color=SUBSTACK_TEXT, linestyle="-", label="IPS survey (1964\u20132015)"),
    Line2D([0], [0], color=SUBSTACK_TEXT, linestyle="--", label="Admin-based (2012\u20132025)"),
]
_SOURCE_BY_ORIGIN = f"{SOURCE_ONS_IPS}; {SOURCE_ONS} (admin-based, 2012+)"


def _chart_by_origin(df: pd.DataFrame, ips_metric: str, admin_metric: str,
                     title: str, ylabel: str, name: str, zero_line: bool) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    for cat, color, label in _ORIGIN_GROUPS:
        ips = _series(df, ips_metric, cat)
        if not ips.empty:
            ax.plot(ips["period"], ips["value"], marker="o", markersize=3, color=color, label=label)
        admin = _series(df, admin_metric, cat)
        if not admin.empty:
            ax.plot(admin["period"], admin["value"], marker="o", markersize=3,
                    linestyle="--", color=color)
    if zero_line:
        ax.axhline(0, color=SUBSTACK_TEXT, linewidth=0.8)
    _style_title(ax, title)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    group_legend = ax.legend(loc="upper left", frameon=False)
    ax.add_artist(group_legend)
    ax.legend(handles=_METHOD_LEGEND, loc="lower right", frameon=False, fontsize=9)
    _style_axes(ax)
    return _save(fig, name, _SOURCE_BY_ORIGIN)


def chart_immigration_by_origin(df: pd.DataFrame) -> Path:
    return _chart_by_origin(
        df, "immigration_by_origin", "immigration",
        "UK immigration by citizenship group (1964\u20132025)",
        "Immigration per year", "immigration_by_origin.png", zero_line=False,
    )


def chart_net_migration_by_origin(df: pd.DataFrame) -> Path:
    return _chart_by_origin(
        df, "net_migration_by_origin", "net_migration",
        "UK net migration by citizenship group (1964\u20132025)",
        "Net migration per year", "net_migration_by_origin.png", zero_line=True,
    )


CHARTS = (
    chart_immigration,
    chart_net_migration,
    chart_inflow_outflow,
    chart_immigration_by_origin,
    chart_net_migration_by_origin,
    chart_visas_by_category,
    chart_asylum,
    chart_irregular,
    chart_legal_vs_irregular,
    chart_net_migration_per_capita,
)

# chart file -> (what it shows, data sources)
_CHART_DOCS: list[tuple[str, str, str]] = [
    ("immigration_over_time.png", "UK long-term immigration over time, 1964–2025",
     _SOURCE_BY_ORIGIN),
    ("net_migration.png", "UK net long-term migration over time, 1964–2025",
     _SOURCE_BY_ORIGIN),
    ("immigration_vs_emigration.png", "Annual immigration vs emigration flows (2012+)", SOURCE_ONS),
    ("immigration_by_origin.png", "Immigration by citizenship group, 1964\u20132025 (IPS + admin-based)", _SOURCE_BY_ORIGIN),
    ("net_migration_by_origin.png", "Net migration by citizenship group, 1964\u20132025 (IPS + admin-based)", _SOURCE_BY_ORIGIN),
    ("visas_by_category.png", "Entry-clearance visas granted by category (2005+)",
     f"{SOURCE_HO}, entry-clearance-visa-outcomes dataset"),
    ("asylum_applications.png", "Asylum applications, main applicants (2001+)",
     f"{SOURCE_HO}, asylum-claims dataset"),
    ("irregular_arrivals.png", "Detected irregular arrivals incl. small boats (2018+)",
     f"{SOURCE_HO}, illegal-entry-routes dataset"),
    ("legal_vs_irregular.png", "Total immigration vs detected irregular arrivals, log scale",
     f"{SOURCE_ONS}; {SOURCE_HO}"),
    ("net_migration_per_capita.png", "ONS net migration per 1,000 population, 1964–2025",
     f"{SOURCE_ONS_IPS}; {SOURCE_ONS}; {SOURCE_WB} (SP.POP.TOTL denominator only)"),
]


def write_sources_doc() -> Path:
    """Write ``SOURCES.md`` next to the charts, citing the data source for each figure."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / "SOURCES.md"
    lines = [
        "# UK immigration charts — data sources",
        "",
        "All figures are generated by `python -m uk_migration.run` from live public data.",
        "No values are hand-entered, interpolated, or synthesised; each traces to a source below.",
        "",
        "## Primary sources",
        "",
        "- **ONS Long-Term International Migration** — immigration, emigration, net migration.",
        "  <https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/internationalmigration/datasets/longterminternationalimmigrationemigrationandnetmigrationflowsprovisional>",
        "- **ONS IPS Long-Term International Migration, 1964\u20132015, by citizenship** (ad hoc 006408)",
        "  \u2014 the long-run historical series (International Passenger Survey), values in thousands.",
        "  <https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/internationalmigration/adhocs/006408longterminternationalmigrationintoandoutoftheukbycitizenship1964to2015>",
        "- **Home Office Immigration System Statistics** — visas, asylum, irregular arrivals.",
        "  <https://www.gov.uk/government/statistical-data-sets/immigration-system-statistics-data-tables>",
        "- **World Bank WDI** (country `GBR`) — total population (`SP.POP.TOTL`), used only",
        "  as the denominator for per-capita charts. The pipeline retains the World Bank's",
        "  modelled migration series as reference data, but the headline charts do not plot it.",
        "  <https://api.worldbank.org/v2/country/GBR/indicator/SP.POP.TOTL?format=json>",
        "",
        "The `*_per_1000_pop` series are **derived** (flow ÷ World Bank population × 1000) — a",
        "population adjustment, since headcounts are not monetary and CPI inflation does not apply.",
        "",
        "## Figures",
        "",
        "| File | Shows | Source |",
        "|---|---|---|",
    ]
    for fname, desc, src in _CHART_DOCS:
        lines.append(f"| `{fname}` | {desc} | {src} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_all(source: pd.DataFrame | str | Path | None = None) -> list[Path]:
    """Render every chart from the combined table plus SOURCES.md; return written paths."""
    df = _load(source)
    paths = [chart(df) for chart in CHARTS]
    paths.append(write_sources_doc())
    return paths
