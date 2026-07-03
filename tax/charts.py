"""Charts: UK-vs-Europe-vs-US tax burden, in the project's Substack-style theme.

The palette and rcParams mirror the sibling ``pre1870_reapportionment_package`` figures
(cream background, serif type, muted grid, italic source note) so visuals stay
consistent across projects. Rendering is headless (``Agg``) and needs only matplotlib.
"""

from __future__ import annotations

import os
import statistics
from typing import Iterable, Optional

import matplotlib

matplotlib.use("Agg")  # headless: no display required

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402

from . import config  # noqa: E402

# ── Substack-style theme (matches pre1870_reapportionment_package) ──────────
BG = "#F7F5F0"
TEXT = "#1A1A1A"
MUTED = "#6B6B6B"
GRID = "#D6D3CC"
ACCENT = "#C85A3D"   # UK
BLUE = "#3D6F8C"     # Europe (median)
GOLD = "#C2993E"     # US
GREEN = "#4A7C59"

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
)

# Series colours: UK / Europe (median) / US.
SERIES_COLORS = {"uk": ACCENT, "europe_median": BLUE, "us": GOLD}
SERIES_LABELS = {"uk": "United Kingdom", "europe_median": "Europe (median)", "us": "United States"}

SOURCE_NOTE = config.FIGURE_SOURCE_NOTE

_LABEL_STROKE = [pe.withStroke(linewidth=3, foreground="white")]


# --- data reshaping ---------------------------------------------------------

def _variant_rows(rows: Iterable[dict], metric: str, household: str, earnings: str) -> list[dict]:
    return [
        r
        for r in rows
        if r["metric"] == metric
        and r["household"] == household
        and r["earnings"] == earnings
    ]


def _region_values(recs: list[dict]) -> dict[str, Optional[float]]:
    """UK / US point values and the Europe median for one metric-variant-year slice."""
    by_iso = {r["iso3"]: r["value"] for r in recs}
    europe = [r["value"] for r in recs if r["region"] == config.EUR]
    return {
        "uk": by_iso.get(config.UK_COUNTRY.iso3),
        "us": by_iso.get(config.US_COUNTRY.iso3),
        "europe_median": statistics.median(europe) if europe else None,
    }


def _latest_year(recs: list[dict]) -> Optional[int]:
    """Latest year with UK (then US) data; global max only if neither is present.

    Mirrors ``tax.stats._target_year`` so charts and the printed summary pin the same
    comparison year instead of a ragged latest OECD vintage that blanks the UK/US.
    """
    for iso3 in (config.UK_COUNTRY.iso3, config.US_COUNTRY.iso3):
        years = [r["year"] for r in recs if r["iso3"] == iso3]
        if years:
            return max(years)
    years = [r["year"] for r in recs]
    return max(years) if years else None


# --- charts -----------------------------------------------------------------

def _finish(fig, ax, out_path: str) -> str:
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, SOURCE_NOTE, ha="left", fontsize=8, color=MUTED, style="italic")
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.16)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def headline_bars(rows: list[dict], out_path: str, year: Optional[int] = None) -> Optional[str]:
    """Grouped bars: UK / Europe median / US across the three headline metrics."""
    variants = [
        ("tax_to_gdp_pct", "", "", "Total tax\n(% of GDP)"),
        ("tax_wedge_pct", "single_nokids", "100aw", "Labour tax wedge\n(avg-wage worker)"),
        ("net_personal_avg_tax_rate_pct", "single_nokids", "100aw", "Net personal\navg tax rate"),
    ]
    labels: list[str] = []
    series: dict[str, list[float]] = {"uk": [], "europe_median": [], "us": []}
    used_year: Optional[int] = None
    for metric, hh, aw, label in variants:
        recs = _variant_rows(rows, metric, hh, aw)
        target = year if year is not None else _latest_year(recs)
        if target is None:
            continue
        vals = _region_values([r for r in recs if r["year"] == target])
        if all(v is None for v in vals.values()):
            continue
        labels.append(label)
        used_year = used_year or target
        for k in series:
            series[k].append(vals[k] if vals[k] is not None else 0.0)
    if not labels:
        return None

    x = range(len(labels))
    width = 0.26
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for i, key in enumerate(("uk", "europe_median", "us")):
        offsets = [xi + (i - 1) * width for xi in x]
        bars = ax.bar(
            offsets, series[key], width, color=SERIES_COLORS[key], label=SERIES_LABELS[key],
            edgecolor=BG, linewidth=0.8,
        )
        for rect in bars:
            h = rect.get_height()
            ax.annotate(
                f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h),
                xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=TEXT, path_effects=_LABEL_STROKE,
            )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylabel("Tax burden")
    ax.set_title(
        f"How the UK's tax burden compares, {used_year}", fontweight="bold", pad=14
    )
    ax.legend(loc="upper right", frameon=False)
    return _finish(fig, ax, out_path)


def tax_to_gdp_over_time(rows: list[dict], out_path: str) -> Optional[str]:
    """Line chart: total tax revenue (% of GDP), UK vs Europe median vs US, over time."""
    recs = _variant_rows(rows, "tax_to_gdp_pct", "", "")
    years = sorted({r["year"] for r in recs})
    if len(years) < 2:
        return None
    series: dict[str, list[Optional[float]]] = {"uk": [], "europe_median": [], "us": []}
    for y in years:
        vals = _region_values([r for r in recs if r["year"] == y])
        for k in series:
            series[k].append(vals[k])

    fig, ax = plt.subplots(figsize=(11, 6))
    markers = {"uk": "o", "europe_median": "s", "us": "^"}
    for key in ("uk", "europe_median", "us"):
        xs = [y for y, v in zip(years, series[key]) if v is not None]
        ys = [v for v in series[key] if v is not None]
        ax.plot(
            xs, ys, color=SERIES_COLORS[key], linewidth=2.6, marker=markers[key],
            markersize=6, markeredgecolor="white", markeredgewidth=1.1,
            label=SERIES_LABELS[key],
        )
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Year")
    ax.set_ylabel("Total tax revenue (% of GDP)")
    ax.set_title(
        "Total tax burden over time: UK vs Europe vs US", fontweight="bold", pad=14
    )
    ax.legend(loc="best", frameon=False)
    return _finish(fig, ax, out_path)


def tax_wedge_by_earnings(rows: list[dict], out_path: str, year: Optional[int] = None) -> Optional[str]:
    """Grouped bars: single-worker tax wedge at 67/100/167% of the average wage."""
    order = [("67aw", "67% of\navg wage"), ("100aw", "100% of\navg wage"), ("167aw", "167% of\navg wage")]
    labels: list[str] = []
    series: dict[str, list[float]] = {"uk": [], "europe_median": [], "us": []}
    used_year: Optional[int] = None
    for aw, label in order:
        recs = _variant_rows(rows, "tax_wedge_pct", "single_nokids", aw)
        target = year if year is not None else _latest_year(recs)
        if target is None:
            continue
        vals = _region_values([r for r in recs if r["year"] == target])
        if all(v is None for v in vals.values()):
            continue
        labels.append(label)
        used_year = used_year or target
        for k in series:
            series[k].append(vals[k] if vals[k] is not None else 0.0)
    if not labels:
        return None

    x = range(len(labels))
    width = 0.26
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for i, key in enumerate(("uk", "europe_median", "us")):
        offsets = [xi + (i - 1) * width for xi in x]
        ax.bar(
            offsets, series[key], width, color=SERIES_COLORS[key], label=SERIES_LABELS[key],
            edgecolor=BG, linewidth=0.8,
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylabel("Labour tax wedge")
    ax.set_title(
        f"Labour tax wedge by earnings level, {used_year}", fontweight="bold", pad=14
    )
    ax.legend(loc="upper left", frameon=False)
    return _finish(fig, ax, out_path)


def render_all(rows: list[dict], out_dir: str, year: Optional[int] = None) -> list[str]:
    """Render all tax-burden charts into ``out_dir``; returns written file paths."""
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    for fn, name in (
        (lambda p: headline_bars(rows, p, year), "tax_burden_headline_bars.png"),
        (lambda p: tax_to_gdp_over_time(rows, p), "tax_to_gdp_over_time.png"),
        (lambda p: tax_wedge_by_earnings(rows, p, year), "tax_wedge_by_earnings.png"),
    ):
        path = fn(os.path.join(out_dir, name))
        if path:
            written.append(path)
    return written
