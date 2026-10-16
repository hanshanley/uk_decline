"""Charts: UK age distribution over time, in the project's Substack-style theme.

Palette and rcParams mirror the sibling ``tax`` package / ``pre1870_reapportionment_package``
so visuals stay consistent. Every figure carries a proper source note crediting the data
collector (UN Population Division / World Bank; see :data:`age_data.config.FIGURE_SOURCE_NOTE`).
Rendering is headless (``Agg``) and needs only matplotlib.
"""

from __future__ import annotations

import os
import statistics
from math import isfinite
from typing import Iterable, Optional

import matplotlib

matplotlib.use("Agg")  # headless: no display required

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402

from . import config  # noqa: E402

# ── Substack-style theme (matches tax/charts.py + pre1870_reapportionment_package) ──
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, BLUE, GOLD, GREEN, house_style, save_chart, with_year_gaps

house_style()

SERIES_COLORS = {"uk": ACCENT, "europe_median": BLUE, "us": GOLD}
SERIES_LABELS = {"uk": "United Kingdom", "europe_median": "Europe (median)", "us": "United States"}
SOURCE_NOTE = config.FIGURE_SOURCE_NOTE


# --- helpers ----------------------------------------------------------------

def _projection_note(ax, years, *, hatched=False):
    if max(years) < config.PROJECTION_START_YEAR:
        return
    ax.axvspan(max(min(years), config.PROJECTION_START_YEAR - .5), max(years),
               facecolor="none" if hatched else MUTED, edgecolor=MUTED,
               hatch="////" if hatched else None, linewidth=0, alpha=.3 if hatched else .10)
    ax.text(.5, 1.015,
            f"{'Hatched' if hatched else 'Dashed / shaded'} from {config.PROJECTION_START_YEAR}: "
            "UN-based projected age distributions",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=10, color=MUTED)


def _plot_age_trend(ax, annual, key, marker):
    start = config.PROJECTION_START_YEAR
    historical = annual[annual.index < start]
    projected = annual[annual.index >= start]
    style = dict(color=SERIES_COLORS[key], linewidth=2.6, marker=marker,
                 markersize=5, markeredgecolor="white", markeredgewidth=1.0,
                 markevery=max(1, len(annual) // 12))
    if historical.notna().any():
        ax.plot(historical.index, historical.values, label=SERIES_LABELS[key], **style)
    if projected.notna().any():
        ax.plot(projected.index, projected.values, linestyle="--",
                label="_nolegend_" if historical.notna().any() else SERIES_LABELS[key],
                **{**style, "markevery": max(1, len(projected) // 12)})
    if (start - 1 in annual.index and start in annual.index
            and all(isfinite(annual.loc[year]) for year in (start - 1, start))):
        ax.add_collection(LineCollection(
            [[(start - 1, annual.loc[start - 1]), (start, annual.loc[start])]],
            colors=[SERIES_COLORS[key]], linewidths=2.6, linestyles="--",
        ))


def _rows(rows: Iterable[dict], metric: str, age_band: str = "", sex: str = "") -> list[dict]:
    return [
        r for r in rows
        if r["metric"] == metric and r["age_band"] == age_band and r["sex"] == sex
    ]


def _region_series(recs: list[dict], years: list[int]) -> dict[str, list[Optional[float]]]:
    series: dict[str, list[Optional[float]]] = {"uk": [], "europe_median": [], "us": []}
    for y in years:
        yr = [r for r in recs if r["year"] == y]
        by_iso = {r["iso3"]: r["value"] for r in yr}
        europe = [r["value"] for r in yr if r["region"] == config.EUR]
        series["uk"].append(by_iso.get("GBR"))
        series["us"].append(by_iso.get("USA"))
        series["europe_median"].append(statistics.median(europe) if europe else None)
    return series


def _finish(fig, ax, out_path: str) -> str:
    ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=8, integer=True))
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, SOURCE_NOTE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.14)
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


# --- charts -----------------------------------------------------------------

def uk_age_structure_over_time(rows: list[dict], out_path: str) -> Optional[str]:
    """Stacked area: UK share aged 0-14 / 15-64 / 65+ over time."""
    bands = [
        ("pop_share_0_14_pct", "0-14", GOLD),
        ("pop_share_15_64_pct", "15-64 (working age)", BLUE),
        ("pop_share_65plus_pct", "65+", ACCENT),
    ]
    uk = {m: {r["year"]: r["value"] for r in _rows(rows, m) if r["iso3"] == "GBR"} for m, _, _ in bands}
    years = sorted(set.intersection(*[set(d) for d in uk.values()]))
    if len(years) < 2:
        return None
    stacks = [[uk[m][y] for y in years] for m, _, _ in bands]
    colors = [c for _, _, c in bands]
    labels = [lbl for _, lbl, _ in bands]
    import pandas as pd
    annual = [with_year_gaps(pd.Series(values, index=years)) for values in stacks]

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.stackplot(annual[0].index, *[values.values for values in annual],
                 colors=colors, labels=labels, edgecolor=BG, linewidth=0.4)
    ax.set_ylim(0, 100)
    ax.margins(x=0)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of UK population")
    ax.set_title("The UK is getting older: population by age group over time",
                 fontweight="bold", pad=38)
    _projection_note(ax, years, hatched=True)
    handles, lbls = ax.get_legend_handles_labels()
    ax.legend(
        handles[::-1], lbls[::-1], loc="center left",
        bbox_to_anchor=(1.01, 0.5), frameon=False,
    )
    return _finish(fig, ax, out_path)


def share_65plus_over_time(rows: list[dict], out_path: str) -> Optional[str]:
    """Line chart: % aged 65+, UK vs Europe median vs US, over time."""
    recs = _rows(rows, "pop_share_65plus_pct")
    years = sorted({r["year"] for r in recs})
    if len(years) < 2:
        return None
    series = _region_series(recs, years)
    fig, ax = plt.subplots(figsize=(11, 6))
    markers = {"uk": "o", "europe_median": "s", "us": "^"}
    for key in ("uk", "europe_median", "us"):
        import pandas as pd
        annual = with_year_gaps(pd.Series(series[key], index=years, dtype=float))
        _plot_age_trend(ax, annual, key, markers[key])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Year")
    ax.set_ylabel("Population aged 65+")
    ax.set_title("Share of the population aged 65+: UK vs Europe vs US",
                 fontweight="bold", pad=14)
    _projection_note(ax, years)
    ax.legend(loc="upper left", frameon=False)
    return _finish(fig, ax, out_path)


def median_age_over_time(rows: list[dict], out_path: str) -> Optional[str]:
    """Line chart: derived median age, UK vs Europe median vs US, over time."""
    recs = _rows(rows, "median_age_years")
    years = sorted({r["year"] for r in recs})
    if len(years) < 2:
        return None
    series = _region_series(recs, years)
    fig, ax = plt.subplots(figsize=(11, 6))
    markers = {"uk": "o", "europe_median": "s", "us": "^"}
    for key in ("uk", "europe_median", "us"):
        import pandas as pd
        annual = with_year_gaps(pd.Series(series[key], index=years, dtype=float))
        _plot_age_trend(ax, annual, key, markers[key])
    ax.set_xlabel("Year")
    ax.set_ylabel("Median age (years, derived)")
    ax.set_title("Median age over time: UK vs Europe vs US",
                 fontweight="bold", pad=14)
    _projection_note(ax, years)
    ax.legend(loc="upper left", frameon=False)
    return _finish(fig, ax, out_path)


def uk_population_pyramid(rows: list[dict], out_path: str,
                          years: Optional[tuple[int, int]] = None) -> Optional[str]:
    """Back-to-back population pyramid for the UK, comparing an early vs latest year."""
    recs = _rows_pyramid(rows, "GBR")
    if not recs:
        return None
    avail = sorted({r["year"] for r in recs})
    if len(avail) < 2:
        return None
    y_old, y_new = (years or (avail[0], avail[-1]))
    if y_old not in avail:
        y_old = avail[0]
    if y_new not in avail:
        y_new = avail[-1]

    bands = config.BAND_ORDER
    ypos = range(len(bands))

    def share(year: int, sex: str) -> list[float]:
        selected = [r for r in recs if r["year"] == year and r["sex"] == sex]
        d = {r["age_band"]: r["value"] for r in selected}
        if len(d) != len(selected) or set(d) != set(bands):
            raise ValueError(f"Incomplete or duplicate UK population pyramid profile: {year}/{sex}")
        return [d[b] for b in bands]

    male_new = share(y_new, "male")
    female_new = share(y_new, "female")
    male_old = share(y_old, "male")
    female_old = share(y_old, "female")

    fig, ax = plt.subplots(figsize=(10.5, 8))
    projected = y_new >= config.PROJECTION_START_YEAR
    suffix = " (projected age shares)" if projected else ""
    bar_style = dict(alpha=.85, hatch="//" if projected else None, edgecolor=BG)
    ax.barh(ypos, [-v for v in male_new], color=BLUE, label=f"Male {y_new}{suffix}", **bar_style)
    ax.barh(ypos, female_new, color=ACCENT, label=f"Female {y_new}{suffix}", **bar_style)
    # Outline the earlier year for comparison.
    old_suffix = " (projected age shares; outline)" if y_old >= config.PROJECTION_START_YEAR else " (outline)"
    ax.step([-v for v in male_old], ypos, where="mid", color=TEXT, linewidth=1.3,
            linestyle="--", label=f"Male {y_old}{old_suffix}")
    ax.step(female_old, ypos, where="mid", color=TEXT, linewidth=1.3,
            linestyle="--", label=f"Female {y_old}{old_suffix}")

    ax.set_yticks(list(ypos))
    ax.set_yticklabels(bands)
    ax.set_xlabel("Share of total population (%)")
    ax.set_ylabel("Age band")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{abs(v):.0f}%"))
    ax.set_title(f"UK population pyramid: {y_old} vs {y_new}", fontweight="bold", pad=14)
    if projected:
        ax.text(.5, 1.015, f"{y_new} age shares use UN-based projections (hatched bars)",
                transform=ax.transAxes, ha="center", va="bottom", fontsize=10, color=MUTED)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .075),
               ncol=2, frameon=False, fontsize=9)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, SOURCE_NOTE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.21)
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _rows_pyramid(rows: Iterable[dict], iso3: str) -> list[dict]:
    return [r for r in rows if r["metric"] == "pop_band_share_pct" and r["iso3"] == iso3]


def render_all(rows: list[dict], out_dir: str) -> list[str]:
    """Render all age-distribution charts into ``out_dir``; returns written file paths."""
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    for fn, name in (
        (lambda p: uk_age_structure_over_time(rows, p), "uk_age_structure_over_time.png"),
        (lambda p: share_65plus_over_time(rows, p), "share_65plus_over_time.png"),
        (lambda p: median_age_over_time(rows, p), "median_age_over_time.png"),
        (lambda p: uk_population_pyramid(rows, p), "uk_population_pyramid.png"),
    ):
        path = fn(os.path.join(out_dir, name))
        if path:
            written.append(path)
    return written
