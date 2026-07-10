"""House-style charts for the crime analysis (three figures).

All use the shared ``vizstyle`` house theme (warm tan, serif, UK in the terracotta accent,
italic source note taken from the data's own ``source`` column):

  1. ``crime_csew_total.png``   — long-run total CSEW crime, England & Wales, 1981->latest:
     the large fall from the mid-1990s peak.
  2. ``crime_fraud_gap.png``    — the same headline total *excluding* vs *including* fraud &
     computer misuse: once online harms are counted, "total crime" is far higher, i.e. crime
     has shifted online rather than simply disappearing.
  3. ``crime_homicide_peers.png`` — intentional homicide rate, UK vs US vs the EU-27 mean.
"""

from __future__ import annotations

import pathlib

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BLUE, MUTED, RC_PARAMS as _THEME, white_stroke

_STROKE = white_stroke()

TOTAL_EXCL = "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
TOTAL_INCL = "ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE"

# Minimum EU-27 members that must report a homicide rate in a given year before we plot the
# "EU-27 mean" for that year (a simple majority of 27).
_MIN_EU_REPORTERS = 14


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _end_label(ax, x, y, text, color, *, pad="  ", dy=0.0):
    """Label a series near its end point. ``pad`` is a text prefix (leading spaces for
    horizontal spacing); ``dy`` is a numeric vertical offset in data units."""
    ax.text(x, y + dy, f"{pad}{text}", fontsize=10.5, fontweight="bold", color=color,
            va="center", ha="left", path_effects=_STROKE)


def _source_note(fig, df):
    srcs = "; ".join(sorted(str(s) for s in df["source"].dropna().unique()))
    fig.text(0.01, 0.01, f"Source: {srcs}.", ha="left", fontsize=8, color=MUTED,
             style="italic")


def _series(df, offence_group) -> pd.DataFrame:
    sub = df[df["offence_group"] == offence_group].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    return sub.sort_values("date")


def _style_incidents_axes(ax, title, subtitle):
    """Shared axis/subtitle scaffolding for the two CSEW incidents charts (millions)."""
    ax.set_title(title, fontweight="bold", pad=30)
    ax.text(0.5, 1.015, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("Incidents per year (millions)", labelpad=2)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}M"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)


# ── 1. Long-run total crime ──────────────────────────────────────────────────
def chart_csew_total(df, out_dir):
    plt.rcParams.update(_THEME)
    s = _series(df, TOTAL_EXCL)
    if s.empty:
        return None
    x, y = s["date"], s["value"] / 1_000.0  # 1,000s of incidents -> millions

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(x, y, color=ACCENT, linewidth=2.8)
    ax.fill_between(x, y, y.min(), color=ACCENT, alpha=0.10)

    peak = y.idxmax()
    ax.plot([x[peak]], [y[peak]], "o", color=ACCENT, markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, zorder=5)
    ax.annotate(f"peak {y[peak]:.1f}M in {x[peak].year}",
                xy=(x[peak], y[peak]), xytext=(0, 12), textcoords="offset points",
                fontsize=10, color=MUTED, ha="center")
    _end_label(ax, x.iloc[-1], y.iloc[-1], f"{y.iloc[-1]:.1f}M", ACCENT)

    _style_incidents_axes(
        ax,
        "Crime has fallen sharply since the mid-1990s \u2014 England & Wales",
        "Total CSEW headline crime (excluding fraud & computer misuse), incidents per year",
    )
    ax.margins(x=0.04)
    _source_note(fig, s)
    return _save(fig, out_dir, "crime_csew_total.png")


# ── 2. The fraud / online-crime gap ──────────────────────────────────────────
def chart_fraud_gap(df, out_dir):
    plt.rcParams.update(_THEME)
    excl, incl = _series(df, TOTAL_EXCL), _series(df, TOTAL_INCL)
    if incl.empty:
        return None
    # Restrict the "excluding" line to the period the "including" line exists, for a fair gap.
    start = incl["date"].min()
    excl = excl[excl["date"] >= start]
    if excl.empty:
        return None

    fig, ax = plt.subplots(figsize=(11, 6))
    xe, ye = excl["date"], excl["value"] / 1_000.0
    xi, yi = incl["date"], incl["value"] / 1_000.0
    # Shade the gap between the two totals over their shared periods (the "online" crime).
    gap = incl.merge(excl, on="date", suffixes=("_incl", "_excl"))
    if not gap.empty:
        ax.fill_between(gap["date"], gap["value_incl"] / 1_000.0,
                        gap["value_excl"] / 1_000.0, color=ACCENT, alpha=0.10)
    ax.plot(xi, yi, color=ACCENT, linewidth=2.8)
    ax.plot(xe, ye, color=BLUE, linewidth=2.2)
    _end_label(ax, xi.iloc[-1], yi.iloc[-1], f"incl. fraud  {yi.iloc[-1]:.1f}M", ACCENT)
    _end_label(ax, xe.iloc[-1], ye.iloc[-1], f"excl. fraud  {ye.iloc[-1]:.1f}M", BLUE)

    _style_incidents_axes(
        ax,
        "Counting fraud & computer misuse roughly doubles 'total crime'",
        "CSEW headline crime, England & Wales \u2014 the headline fall hides a shift online",
    )
    ax.margins(x=0.10)
    _source_note(fig, incl)
    return _save(fig, out_dir, "crime_fraud_gap.png")


# ── 3. Homicide vs peers ─────────────────────────────────────────────────────
def chart_homicide_peers(df, out_dir):
    from . import countries

    plt.rcParams.update(_THEME)
    sub = df[df["metric"] == "homicide_rate_per_100k"].copy()
    if sub.empty:
        return None
    sub["year"] = sub["year"].astype(int)

    def line(iso3):
        s = sub[sub["iso3"] == iso3].sort_values("year")
        return s["year"], s["value"]

    fig, ax = plt.subplots(figsize=(11, 6))
    # EU-27 mean per year (comparison band). Only plot years where a majority of the 27
    # members actually reported, so the "EU-27 mean" label is not distorted by the sparse
    # tail years in the World Bank/UNODC series.
    eu = sub[sub["iso3"].map(countries.group_for_iso3) == countries.EU]
    eu_grp = eu.groupby("year")["value"]
    eu_mean = eu_grp.mean()[eu_grp.size() >= _MIN_EU_REPORTERS]
    ax.plot(eu_mean.index, eu_mean.values, color=MUTED, linewidth=1.8, linestyle="--")
    xus, yus = line("USA")
    ax.plot(xus, yus, color=BLUE, linewidth=2.2)
    xuk, yuk = line("GBR")
    ax.plot(xuk, yuk, color=ACCENT, linewidth=2.8)

    if len(eu_mean):
        _end_label(ax, eu_mean.index[-1], eu_mean.values[-1], "EU-27 mean", MUTED, dy=-0.35)
    if len(xus):
        _end_label(ax, xus.iloc[-1], yus.iloc[-1], "United States", BLUE)
    if len(xuk):
        _end_label(ax, xuk.iloc[-1], yuk.iloc[-1], "United Kingdom", ACCENT, dy=0.35)

    ax.set_title("Homicide: the UK is far below the US, near its European peers",
                 fontweight="bold", pad=30)
    ax.text(0.5, 1.015, "Intentional homicides per 100,000 people",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("Homicides per 100,000", labelpad=2)
    ax.set_ylim(0, None)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.08)
    _source_note(fig, sub)
    return _save(fig, out_dir, "crime_homicide_peers.png")


def _save(fig, out_dir, filename) -> pathlib.Path:
    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(bottom=0.12)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(csew_source=None, homicide_source=None,
                out_dir="outputs/crime") -> list[pathlib.Path]:
    """Render all crime charts that have data. Returns the written paths."""
    written: list[pathlib.Path] = []
    if csew_source is not None:
        cdf = _load(csew_source)
        for fn in (chart_csew_total, chart_fraud_gap):
            p = fn(cdf, out_dir)
            if p:
                written.append(p)
    if homicide_source is not None:
        hdf = _load(homicide_source)
        p = chart_homicide_peers(hdf, out_dir)
        if p:
            written.append(p)
    return written
