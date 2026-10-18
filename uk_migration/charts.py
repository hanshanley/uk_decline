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
from matplotlib.ticker import MaxNLocator
from ppp_data.figure import labelled_ends

from .combine import COMBINED_CSV

# Showcase charts are written here (a committable, non-git-ignored folder matching the
# sibling projects' `outputs/` convention). Each PNG carries a data-source caption.
FIGURES_DIR = Path("outputs/migration")

# Canonical data-source citations (stable landing pages / indicator IDs, not volatile
# per-quarter file URLs). Rendered as a caption on each chart and into SOURCES.md.
SOURCE_ONS = "Office for National Statistics, Long-Term International Migration (ons.gov.uk)"
SOURCE_ONS_IPS = (
    "Office for National Statistics, International Passenger Survey, "
    "long-term migration 1964\u20132015, ad hoc 006408 (ons.gov.uk)"
)
SOURCE_HO = "Home Office Immigration System Statistics (gov.uk)"
SOURCE_WB = "World Bank, World Development Indicators (api.worldbank.org)"
METHOD_BREAK_YEAR = 2012
_METHOD_NOTE = (
    "Note: 2012 method break. Different methods are not directly comparable; "
    "lines are not joined across the break."
)
_SOURCE_ONS_METHODS = (
    "Office for National Statistics: International Passenger Survey (ad hoc 006408) "
    "through 2011; revised/admin-based long-term migration from 2012."
)

# ---- Substack theme (shared vizstyle house style) --------------------------
from vizstyle import (  # noqa: E402
    BG as SUBSTACK_BG, TEXT as SUBSTACK_TEXT, MUTED as SUBSTACK_MUTED,
    ACCENT as SUBSTACK_ACCENT, BLUE as SUBSTACK_BLUE, GOLD as SUBSTACK_GOLD,
    GREEN as SUBSTACK_GREEN, GRID as SUBSTACK_GRID, country_color, house_style, with_year_gaps, save_chart,
)

house_style()

def _load(source: pd.DataFrame | str | Path | None) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source
    return pd.read_csv(source or COMBINED_CSV)


def _series(df: pd.DataFrame, metric: str, category: str = "all") -> pd.DataFrame:
    sel = df[(df["metric"] == metric) & (df["category"] == category)]
    return sel.sort_values("period")


def _save(fig, name: str, source: str, *, publication: bool = False,
          right: float = 0.96) -> Path:
    import textwrap

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    source = "\n".join(textwrap.fill(line, width=145) for line in source.splitlines())
    if publication:
        fig.subplots_adjust(left=0.09, right=right, top=0.80, bottom=0.20)
    else:
        fig.subplots_adjust(bottom=0.20 if "\n" in source else 0.14)
    fig.text(
        0.09 if publication else 0.005, 0.025 if publication else 0.012,
        f"Source: {source}", ha="left", va="bottom",
        fontsize=9 if publication else 8, style="italic", color=SUBSTACK_MUTED,
    )
    save_chart(fig, path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def _style_axes(ax, thousands: bool = True, logy: bool = False) -> None:
    """Apply the house axes styling: integer year ticks, y grid, thousands separator."""
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    if thousands and not logy:
        ax.yaxis.set_major_formatter(lambda v, _pos: f"{v:,.0f}")
    if logy:
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
    color: str = SUBSTACK_ACCENT,
    category: str = "all",
    linewidth: float = 2.6,
    label: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Plot separate method segments; never draw a trend across the 2012 break."""
    ips = _series(df, ips_metric, category)
    ips = ips[ips["period"] < METHOD_BREAK_YEAR]
    admin = _series(df, admin_metric, category)
    admin = admin[admin["period"] >= METHOD_BREAK_YEAR]
    for segment in (ips, admin):
        if not segment.empty:
            ax.plot(
                segment["period"], segment["value"], color=color,
                linewidth=linewidth, label=label,
            )
    return ips, admin


def _compact_count(value: float, _position=None) -> str:
    if not value:
        return "0"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:g}m"
    if abs(value) >= 1000:
        return f"{value / 1000:g}k"
    return f"{value:g}"


def _style_ons_figure(fig, ax, segments: list[pd.DataFrame], title: str,
                      subtitle: str, ylabel: str, *, counts: bool = True) -> int:
    observed = [segment for segment in segments if not segment.empty]
    if not observed:
        raise ValueError("No ONS migration observations to plot")
    first = int(min(segment["period"].min() for segment in observed))
    latest = int(max(segment["period"].max() for segment in observed))
    low = min(float(segment["value"].min()) for segment in observed)
    high = max(0., max(float(segment["value"].max()) for segment in observed))
    padding = max(high - low, abs(high), 1) * 0.08
    ax.set_xlim(first - 0.6, latest + 0.6)
    ax.set_ylim(0 if low >= 0 else low - padding, high + padding)
    ax.set_xticks(sorted({first, *range((first // 10 + 1) * 10, latest + 1, 10), latest}))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    if counts:
        ax.yaxis.set_major_formatter(_compact_count)
    ax.set_xlabel("Year", fontsize=10.5, labelpad=5)
    ax.set_ylabel(ylabel, fontsize=10.5, labelpad=7)
    ax.tick_params(labelsize=10)
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.09, 0.89, f"{subtitle} \u00b7 {first}\u2013{latest}",
             fontsize=10.5, color=SUBSTACK_MUTED)
    return latest


def _ons_end_labels(ax, ends: list[tuple[float, str, str, int]], latest: int) -> None:
    low, high = ax.get_ylim()
    first_label = len(ax.texts)
    labelled_ends(ax, ends, min_gap=(high - low) * 0.045, x=latest, fontsize=9.5)
    for label in ax.texts[first_label:]:
        label.set_path_effects([])
        label.set_fontweight("normal")


def chart_immigration(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ips, admin = _plot_ons_methods(
        ax, df, "immigration_by_origin", "immigration",
        label="UK long-term immigration over time",
    )
    latest = _style_ons_figure(
        fig, ax, [ips, admin], "UK long-term immigration",
        "Annual arrivals", "Immigration per year",
    )
    last = (admin if not admin.empty else ips).iloc[-1]
    _ons_end_labels(ax, [(last["value"], f"{_compact_count(last['value'])} ({int(last['period'])})",
                         SUBSTACK_ACCENT, int(last["period"]))], latest)
    return _save(fig, "immigration_over_time.png", _SOURCE_BY_ORIGIN,
                 publication=True, right=0.83)


def chart_net_migration(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ips, admin = _plot_ons_methods(
        ax, df, "net_migration_by_origin", "net_migration",
        label="UK net long-term migration over time",
    )
    ax.axhline(0, color=SUBSTACK_MUTED, linewidth=0.8)
    latest = _style_ons_figure(
        fig, ax, [ips, admin], "UK net long-term migration",
        "Immigration minus emigration", "People (net)",
    )
    last = (admin if not admin.empty else ips).iloc[-1]
    _ons_end_labels(ax, [(last["value"], f"{_compact_count(last['value'])} ({int(last['period'])})",
                         SUBSTACK_ACCENT, int(last["period"]))], latest)
    return _save(fig, "net_migration.png", _SOURCE_BY_ORIGIN,
                 publication=True, right=0.83)


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
    data = {}
    for category in colors:
        s = _series(df, "visas_granted", category)
        if s.empty:
            raise ValueError(f"Missing published visa category: {category}")
        data[category] = s
    first = int(min(s["period"].min() for s in data.values()))
    latest = int(max(s["period"].max() for s in data.values()))
    house_style()
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ends = []
    for category, color in colors.items():
        s = data[category]
        annual = with_year_gaps(s.set_index("period")["value"] / 1000)
        ax.plot(annual.index, annual.values, color=color, linewidth=2.6, label=category.capitalize())
        last = s.iloc[-1]
        ax.scatter(last["period"], last["value"] / 1000, color=color, s=30, zorder=3, label=category.capitalize())
        ends.append((
            last["value"] / 1000,
            f"{category.capitalize()}: {last['value'] / 1000:,.0f}k ({int(last['period'])})",
            color, int(last["period"]),
        ))
    labelled_ends(ax, ends, min_gap=60, x=latest + 0.3, fontsize=11)
    ax.set_xlim(first - 0.3, latest + 0.3)
    ax.set_ylim(0, max(s["value"].max() for s in data.values()) / 1000 * 1.12)
    ax.set_xticks(list(range((first + 4) // 5 * 5, latest + 1, 5)))
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}k")
    ax.tick_params(labelsize=11)
    ax.set_xlabel("Year")
    ax.set_ylabel("Visas granted per year")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.suptitle("UK visas for work, study and family", x=0.09, y=0.97,
                 ha="left", fontsize=22, fontweight="bold")
    fig.text(0.09, 0.89, "Entry-clearance grants, including dependants; complete calendar years",
             fontsize=11.5, color=SUBSTACK_MUTED)
    return _save(
        fig, "visas_by_category.png",
        f"{SOURCE_HO}, entry-clearance outcomes, Data_Vis_D02. "
        f"{first}\u2013{latest}; visas granted, not arrivals or net migration. "
        "Visitor and other categories are not shown; missing years are not joined.",
        publication=True,
    )


def chart_asylum(df: pd.DataFrame) -> Path:
    s = _series(df, "asylum_applications", "main_applicant")
    if s.empty:
        raise ValueError("Missing published asylum applications")
    first, latest = int(s["period"].min()), int(s["period"].max())
    house_style()
    fig, ax = plt.subplots(figsize=(11, 5.8))
    annual = with_year_gaps(s.set_index("period")["value"] / 1000)
    ax.plot(annual.index, annual.values, color=SUBSTACK_ACCENT, linewidth=2.8)
    ax.fill_between(annual.index, annual.values, 0, color=SUBSTACK_ACCENT, alpha=0.08)
    last = s.iloc[-1]
    ax.scatter(last["period"], last["value"] / 1000, color=SUBSTACK_ACCENT, s=35, zorder=3)
    labelled_ends(
        ax, [(last["value"] / 1000, f"{last['value']:,.0f} in {latest}", SUBSTACK_ACCENT, latest)],
        min_gap=1, x=latest + 0.3, fontsize=11,
    )
    ax.set_xlim(first - 0.3, latest + 0.3)
    ax.set_ylim(0, s["value"].max() / 1000 * 1.12)
    ax.set_xticks(list(range((first + 4) // 5 * 5, latest + 1, 5)))
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}k")
    ax.tick_params(labelsize=11)
    ax.set_xlabel("Year")
    ax.set_ylabel("Asylum applications per year")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.suptitle("UK asylum applications", x=0.09, y=0.97, ha="left",
                 fontsize=22, fontweight="bold")
    fig.text(0.09, 0.89, "Main applicants only; complete calendar years",
             fontsize=11.5, color=SUBSTACK_MUTED)
    return _save(
        fig, "asylum_applications.png",
        f"{SOURCE_HO}, asylum claims, Data_Asy_D01. {first}\u2013{latest}. "
        "Dependants excluded; not decisions, the asylum backlog or all immigration. "
        "Missing years are not joined.",
        publication=True,
    )


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
            label="Total long-term immigration (official estimates)")
    ax.plot(irregular["period"], irregular["value"], marker="o", color=SUBSTACK_ACCENT, label="Irregular arrivals (Home Office)")
    ax.set_yscale("log")
    _style_title(ax, "UK total immigration vs detected irregular arrivals (log scale)")
    ax.set_xlabel("Year")
    ax.set_ylabel("People per year (log)")
    ax.legend(loc="upper left", frameon=False)
    _style_axes(ax, thousands=False, logy=True)
    return _save(
        fig, "legal_vs_irregular.png", f"{SOURCE_ONS}; {SOURCE_HO}\n"
        "Different measures: long-term migration estimates and arrival detections are not "
        "disjoint categories and must not be added or interpreted as a legal/illegal split.",
    )


def chart_net_migration_per_capita(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ips, admin = _plot_ons_methods(
        ax, df, "net_migration_by_origin_per_1000_pop", "net_migration_per_1000_pop",
        label="UK net migration per 1,000 population",
    )
    ax.axhline(0, color=SUBSTACK_MUTED, linewidth=0.8)
    latest = _style_ons_figure(
        fig, ax, [ips, admin], "UK net migration per 1,000 population",
        "Annual net flows, population-adjusted", "Per 1,000 population", counts=False,
    )
    last = (admin if not admin.empty else ips).iloc[-1]
    _ons_end_labels(ax, [(last["value"], f"{last['value']:.1f} ({int(last['period'])})",
                         SUBSTACK_ACCENT, int(last["period"]))], latest)
    return _save(
        fig, "net_migration_per_capita.png",
        f"{_SOURCE_ONS_METHODS}\nWorld Bank WDI: SP.POP.TOTL (population denominator only).\n"
        + _METHOD_NOTE, publication=True, right=0.83,
    )


_ORIGIN_GROUPS = [
    ("british", country_color("UK"), "British"),
    ("eu", country_color("EUU"), "EU / EU+"),
    ("non_eu", SUBSTACK_BLUE, "Non-EU / Non-EU+"),
]

_SOURCE_BY_ORIGIN = (
    _SOURCE_ONS_METHODS + "\n" + _METHOD_NOTE
)


def _chart_by_origin(df: pd.DataFrame, ips_metric: str, admin_metric: str,
                     title: str, ylabel: str, name: str, zero_line: bool) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    segments, ends = [], []
    for cat, color, label in _ORIGIN_GROUPS:
        ips, admin = _plot_ons_methods(
            ax, df, ips_metric, admin_metric, category=cat,
            color=color, linewidth=2.2, label=label,
        )
        segments.extend((ips, admin))
        observed = admin if not admin.empty else ips
        if not observed.empty:
            last = observed.iloc[-1]
            ends.append((
                last["value"], f"{label}  {_compact_count(last['value'])} ({int(last['period'])})",
                color, int(last["period"]),
            ))
    if zero_line:
        ax.axhline(0, color=SUBSTACK_MUTED, linewidth=0.8)
    latest = _style_ons_figure(
        fig, ax, segments, title, "Long-term flows by citizenship group", ylabel,
    )
    _ons_end_labels(ax, ends, latest)
    return _save(fig, name, _SOURCE_BY_ORIGIN, publication=True, right=0.76)


def chart_immigration_by_origin(df: pd.DataFrame) -> Path:
    return _chart_by_origin(
        df, "immigration_by_origin", "immigration",
        "UK immigration",
        "Immigration per year", "immigration_by_origin.png", zero_line=False,
    )


def chart_net_migration_by_origin(df: pd.DataFrame) -> Path:
    return _chart_by_origin(
        df, "net_migration_by_origin", "net_migration",
        "UK net migration",
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
