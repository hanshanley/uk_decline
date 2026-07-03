"""Charts: UK age distribution over time, in the project's Substack-style theme.

Palette and rcParams mirror the sibling ``tax`` package / ``pre1870_reapportionment_package``
so visuals stay consistent. Every figure carries a proper source note crediting the data
collector (UN Population Division / World Bank; see :data:`age_data.config.FIGURE_SOURCE_NOTE`).
Rendering is headless (``Agg``) and needs only matplotlib.
"""

from __future__ import annotations

import os
import statistics
from typing import Iterable, Optional

import matplotlib

matplotlib.use("Agg")  # headless: no display required

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402

from . import config  # noqa: E402

# ── Substack-style theme (matches tax/charts.py + pre1870_reapportionment_package) ──
BG = "#FFFFFF"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"
ACCENT = "#C0392B"   # UK / 65+
BLUE = "#1F5C99"     # Europe (median) / 15-64
GOLD = "#D19000"     # US / 0-14
GREEN = "#2A9D8F"

plt.rcParams.update(
    {
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "text.color": TEXT,
        "axes.labelcolor": TEXT,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.edgecolor": GRID,
        "grid.color": GRID,
        "grid.alpha": 1.0,
        "grid.linewidth": 0.9,
        "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 12,
        "axes.titlesize": 16,
        "axes.labelsize": 13,
        "figure.titlesize": 18,
        "legend.framealpha": 0.0,
        "legend.fontsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

SERIES_COLORS = {"uk": ACCENT, "europe_median": BLUE, "us": GOLD}
SERIES_LABELS = {"uk": "United Kingdom", "europe_median": "Europe (median)", "us": "United States"}
SOURCE_NOTE = config.FIGURE_SOURCE_NOTE


# --- helpers ----------------------------------------------------------------

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
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, SOURCE_NOTE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.14)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
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
    years = sorted(set().union(*[set(d) for d in uk.values()]))
    if len(years) < 2:
        return None
    stacks = [[uk[m].get(y, 0.0) for y in years] for m, _, _ in bands]
    colors = [c for _, _, c in bands]
    labels = [lbl for _, lbl, _ in bands]

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.stackplot(years, *stacks, colors=colors, labels=labels, edgecolor=BG, linewidth=0.4)
    ax.set_ylim(0, 100)
    ax.margins(x=0)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of UK population")
    ax.set_title("The UK is getting older: population by age group over time",
                 fontweight="bold", pad=14)
    handles, lbls = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], lbls[::-1], loc="center left", frameon=False)
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
        xs = [y for y, v in zip(years, series[key]) if v is not None]
        ys = [v for v in series[key] if v is not None]
        ax.plot(xs, ys, color=SERIES_COLORS[key], linewidth=2.6, marker=markers[key],
                markersize=5, markeredgecolor="white", markeredgewidth=1.0,
                markevery=max(1, len(xs) // 12), label=SERIES_LABELS[key])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Year")
    ax.set_ylabel("Population aged 65+")
    ax.set_title("Share of the population aged 65+: UK vs Europe vs US",
                 fontweight="bold", pad=14)
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
        xs = [y for y, v in zip(years, series[key]) if v is not None]
        ys = [v for v in series[key] if v is not None]
        ax.plot(xs, ys, color=SERIES_COLORS[key], linewidth=2.6, marker=markers[key],
                markersize=5, markeredgecolor="white", markeredgewidth=1.0,
                markevery=max(1, len(xs) // 12), label=SERIES_LABELS[key])
    ax.set_xlabel("Year")
    ax.set_ylabel("Median age (years, derived)")
    ax.set_title("Median age over time: UK vs Europe vs US",
                 fontweight="bold", pad=14)
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
        d = {r["age_band"]: r["value"] for r in recs if r["year"] == year and r["sex"] == sex}
        return [d.get(b, 0.0) for b in bands]

    male_new = share(y_new, "male")
    female_new = share(y_new, "female")
    male_old = share(y_old, "male")
    female_old = share(y_old, "female")

    fig, ax = plt.subplots(figsize=(10.5, 8))
    ax.barh(ypos, [-v for v in male_new], color=BLUE, alpha=0.85, label=f"Male {y_new}")
    ax.barh(ypos, female_new, color=ACCENT, alpha=0.85, label=f"Female {y_new}")
    # Outline the earlier year for comparison.
    ax.step([-v for v in male_old], ypos, where="mid", color=TEXT, linewidth=1.3,
            linestyle="--", label=f"{y_old} outline")
    ax.step(female_old, ypos, where="mid", color=TEXT, linewidth=1.3, linestyle="--")

    ax.set_yticks(list(ypos))
    ax.set_yticklabels(bands)
    ax.set_xlabel("Share of total population (%)")
    ax.set_ylabel("Age band")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{abs(v):.0f}%"))
    ax.set_title(f"UK population pyramid: {y_old} vs {y_new}", fontweight="bold", pad=14)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, SOURCE_NOTE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.10)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
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
