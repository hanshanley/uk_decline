"""House-style charts for the crime analysis (five figures).

All use the shared ``vizstyle`` house theme (warm tan, serif, UK in the terracotta accent,
italic source note taken from the data's own ``source`` column):

  1. ``crime_csew_total.png``   — long-run total CSEW crime, England & Wales, 1981->latest:
     the large fall from the mid-1990s peak.
  2. ``crime_csew_21st_century.png`` — the same series zoomed to the 21st century.
  3. ``crime_fraud_gap.png``    — the same headline total *excluding* vs *including* fraud &
     computer misuse: once online harms are counted, "total crime" is far higher, i.e. crime
     has shifted online rather than simply disappearing.
  4. ``crime_homicide_peers.png`` — intentional homicide rate, UK vs US vs the EU-27 mean.
  5. ``crime_homicide_nations.png`` — homicide rates across England & Wales, Scotland,
     and Northern Ireland since 2000.
"""

from __future__ import annotations

import pathlib

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BLUE, GRID, MUTED, RC_PARAMS as _THEME, white_stroke

_STROKE = white_stroke()
_CRIME_THEME = {
    **_THEME,
    "font.family": "sans-serif",
    "font.sans-serif": ["Avenir Next", "Avenir", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.titlesize": 16,
    "axes.labelsize": 10.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "grid.alpha": 0.38,
    "grid.linewidth": 0.55,
}

TOTAL_EXCL = "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
TOTAL_INCL = "ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE"

# Minimum EU-27 members that must report a homicide rate in a given year before we plot the
# "EU-27 mean" for that year (a simple majority of 27).
_MIN_EU_REPORTERS = 14
_TWENTY_FIRST_CENTURY_START = pd.Timestamp("2000-01-01")


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _end_label(ax, x, y, text, color, *, dx=8, dy=0):
    """Label a series beside its end point using stable screen-space offsets."""
    ax.annotate(
        text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
        fontsize=9.8, fontweight="semibold", color=color, va="center", ha="left",
        path_effects=_STROKE, annotation_clip=False,
    )


def _source_note(fig, df):
    parts = {
        part.strip()
        for source in df["source"].dropna().unique()
        for part in str(source).split(";")
        if part.strip()
    }
    srcs = "; ".join(sorted(parts))
    fig.text(0.06, 0.025, f"Source: {srcs}.", ha="left", fontsize=7.5, color=MUTED)


def _series(df, offence_group) -> pd.DataFrame:
    sub = df[df["offence_group"] == offence_group].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    return sub.sort_values("date")


def _heading(ax, title, subtitle):
    ax.set_title(title, loc="left", fontsize=17, fontweight="bold", pad=22)
    ax.text(
        0, 1.012, subtitle, transform=ax.transAxes, ha="left", va="bottom",
        fontsize=10.5, color=MUTED,
    )


def _style_axes(ax):
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#C9C6BF")
    ax.tick_params(axis="x", pad=7)
    ax.tick_params(axis="y", pad=6)


def _style_incidents_axes(ax, title, subtitle, ymax):
    """Shared scaffolding for CSEW incidents charts, measured in millions."""
    _heading(ax, title, subtitle)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}M"))
    ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=6, integer=True))
    ax.set_ylim(0, ymax)
    _style_axes(ax)


# ── 1. Long-run total crime ──────────────────────────────────────────────────
def chart_csew_total(df, out_dir):
    plt.rcParams.update(_CRIME_THEME)
    s = _series(df, TOTAL_EXCL)
    if s.empty:
        return None
    x, y = s["date"], s["value"] / 1_000.0  # 1,000s of incidents -> millions

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.plot(x, y, color=ACCENT, linewidth=2.7, solid_capstyle="round")

    peak = y.idxmax()
    ax.plot([x[peak]], [y[peak]], "o", color=ACCENT, markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, zorder=5)
    ax.annotate(
        f"{y[peak]:.1f}M peak", xy=(x[peak], y[peak]), xytext=(0, 13),
        textcoords="offset points", fontsize=9.2, color=MUTED, ha="center",
    )
    ax.plot([x.iloc[-1]], [y.iloc[-1]], "o", color=ACCENT, markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, zorder=5)
    _end_label(
        ax, x.iloc[-1], y.iloc[-1],
        f"{y.iloc[-1]:.1f}M ({x.iloc[-1].year})", ACCENT,
    )

    decline = (1 - y.iloc[-1] / y[peak]) * 100
    _style_incidents_axes(
        ax,
        f"Traditional crime is down {decline:.0f}% from its 1995 peak",
        "England & Wales · CSEW headline crime excluding fraud and computer misuse",
        y.max() * 1.10,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(x.iloc[0] - pd.DateOffset(years=1),
                x.iloc[-1] + pd.DateOffset(months=31))
    _source_note(fig, s)
    return _save(fig, out_dir, "crime_csew_total.png")


# ── 2. Total crime in the 21st century ───────────────────────────────────────
def chart_csew_21st_century(df, out_dir):
    plt.rcParams.update(_CRIME_THEME)
    s = _series(df, TOTAL_EXCL)
    s = s[s["date"] >= _TWENTY_FIRST_CENTURY_START]
    if s.empty:
        return None

    x, y = s["date"], s["value"] / 1_000.0
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.plot(x, y, color=ACCENT, linewidth=2.7, solid_capstyle="round")

    first_value, latest_value = y.iloc[0], y.iloc[-1]
    ax.plot([x.iloc[0], x.iloc[-1]], [first_value, latest_value], "o", color=ACCENT,
            markersize=6, markeredgecolor="white", markeredgewidth=1.5, zorder=5)
    ax.annotate(
        f"{first_value:.1f}M", xy=(x.iloc[0], first_value), xytext=(0, 13),
        textcoords="offset points", fontsize=9.2, color=MUTED, ha="center",
    )
    _end_label(
        ax, x.iloc[-1], latest_value,
        f"{latest_value:.1f}M ({x.iloc[-1].year})", ACCENT,
    )

    if first_value:
        change = (latest_value / first_value - 1) * 100
        direction = "fallen" if change < 0 else "risen"
        title = (
            f"Traditional crime has {direction} {abs(change):.0f}% "
            f"since {x.iloc[0].year}"
        )
    else:
        title = "Traditional crime in the 21st century"

    _style_incidents_axes(
        ax,
        title,
        "England & Wales · CSEW headline crime excluding fraud and computer misuse",
        y.max() * 1.10,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(x.iloc[0] - pd.DateOffset(years=1),
                x.iloc[-1] + pd.DateOffset(months=31))
    _source_note(fig, s)
    return _save(fig, out_dir, "crime_csew_21st_century.png")


# ── 3. The fraud / online-crime gap ──────────────────────────────────────────
def chart_fraud_gap(df, out_dir):
    plt.rcParams.update(_CRIME_THEME)
    excl, incl = _series(df, TOTAL_EXCL), _series(df, TOTAL_INCL)
    if incl.empty:
        return None
    # Restrict the "excluding" line to the period the "including" line exists, for a fair gap.
    start = incl["date"].min()
    excl = excl[excl["date"] >= start]
    if excl.empty:
        return None

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    xe, ye = excl["date"], excl["value"] / 1_000.0
    xi, yi = incl["date"], incl["value"] / 1_000.0
    # Shade the gap between the two totals over their shared periods (the "online" crime).
    gap = incl.merge(excl, on="date", suffixes=("_incl", "_excl"))
    if not gap.empty:
        ax.fill_between(
            gap["date"], gap["value_incl"] / 1_000.0,
            gap["value_excl"] / 1_000.0, color=ACCENT, alpha=0.075,
        )
    ax.plot(xi, yi, color=ACCENT, linewidth=2.7, solid_capstyle="round")
    ax.plot(xe, ye, color=BLUE, linewidth=2.25, solid_capstyle="round")
    ax.plot([xi.iloc[-1]], [yi.iloc[-1]], "o", color=ACCENT, markersize=5, zorder=5)
    ax.plot([xe.iloc[-1]], [ye.iloc[-1]], "o", color=BLUE, markersize=5, zorder=5)
    _end_label(ax, xi.iloc[-1], yi.iloc[-1], f"Including fraud  {yi.iloc[-1]:.1f}M",
               ACCENT)
    _end_label(ax, xe.iloc[-1], ye.iloc[-1], f"Excluding fraud  {ye.iloc[-1]:.1f}M",
               BLUE)

    fraud_share = (yi.iloc[-1] - ye.iloc[-1]) / yi.iloc[-1] * 100
    latest_gap = yi.iloc[-1] - ye.iloc[-1]
    ax.annotate(
        f"{latest_gap:.1f}M fraud &\ncomputer misuse",
        xy=(xi.iloc[-2], (yi.iloc[-2] + ye.iloc[-2]) / 2),
        xytext=(-48, 0), textcoords="offset points", ha="right", va="center",
        fontsize=9, color=MUTED,
    )
    _style_incidents_axes(
        ax,
        f"Fraud now makes up about {fraud_share:.0f}% of headline crime",
        "England & Wales · CSEW crime including vs excluding fraud and computer misuse",
        max(yi.max(), ye.max()) * 1.12,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(xi.iloc[0] - pd.DateOffset(months=8),
                xi.iloc[-1] + pd.DateOffset(years=2))
    _source_note(fig, incl)
    return _save(fig, out_dir, "crime_fraud_gap.png")


# ── 4. Homicide vs peers ─────────────────────────────────────────────────────
def chart_homicide_peers(df, out_dir):
    from . import countries

    plt.rcParams.update(_CRIME_THEME)
    sub = df[df["metric"] == "homicide_rate_per_100k"].copy()
    if sub.empty:
        return None
    sub["year"] = sub["year"].astype(int)

    def line(iso3):
        s = sub[sub["iso3"] == iso3].sort_values("year")
        return s["year"], s["value"]

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    # EU-27 mean per year (comparison band). Only plot years where a majority of the 27
    # members actually reported, so the "EU-27 mean" label is not distorted by the sparse
    # tail years in the World Bank/UNODC series.
    eu = sub[sub["iso3"].map(countries.group_for_iso3) == countries.EU]
    eu_grp = eu.groupby("year")["value"]
    eu_mean = eu_grp.mean()[eu_grp.size() >= _MIN_EU_REPORTERS]
    ax.plot(
        eu_mean.index, eu_mean.values, color=MUTED, linewidth=1.6,
        linestyle=(0, (4, 3)), alpha=0.9,
    )
    xus, yus = line("USA")
    ax.plot(xus, yus, color=BLUE, linewidth=2.2, solid_capstyle="round")
    xuk, yuk = line("GBR")
    ax.plot(xuk, yuk, color=ACCENT, linewidth=2.7, solid_capstyle="round")

    if len(eu_mean):
        _end_label(ax, eu_mean.index[-1], eu_mean.values[-1],
                   f"EU-27  {eu_mean.values[-1]:.1f}", MUTED, dy=-13)
    if len(xus):
        _end_label(ax, xus.iloc[-1], yus.iloc[-1],
                   f"United States  {yus.iloc[-1]:.1f}", BLUE)
    if len(xuk):
        _end_label(ax, xuk.iloc[-1], yuk.iloc[-1],
                   f"United Kingdom  {yuk.iloc[-1]:.1f}", ACCENT, dy=11)
    for xs, ys, color in ((xus, yus, BLUE), (xuk, yuk, ACCENT)):
        if len(xs):
            ax.plot([xs.iloc[-1]], [ys.iloc[-1]], "o", color=color, markersize=5,
                    zorder=5)

    _heading(
        ax,
        "The UK's homicide rate remains far below the US",
        "Intentional homicides per 100,000 people · EU-27 is the annual reporting-country mean",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    plotted_max = max(
        eu_mean.max() if len(eu_mean) else 0,
        yus.max() if len(yus) else 0,
        yuk.max() if len(yuk) else 0,
    )
    ax.set_ylim(0, plotted_max * 1.08)
    ax.set_xlim(sub["year"].min() - 1, sub["year"].max() + 5)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=6))
    _style_axes(ax)
    _source_note(fig, sub)
    return _save(fig, out_dir, "crime_homicide_peers.png")


def chart_homicide_nations(df, out_dir):
    plt.rcParams.update(_CRIME_THEME)
    sub = df[df["metric"] == "homicide_rate_per_million"].copy()
    if sub.empty:
        return None
    sub["year"] = sub["year"].astype(int)
    sub = sub[sub["year"] >= 2000]
    if sub.empty:
        return None

    styles = {
        "England & Wales": (ACCENT, "-", 2.7, 0),
        "Scotland": (BLUE, "-", 2.15, -13),
        "Northern Ireland": (MUTED, (0, (4, 3)), 1.65, 13),
    }
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    for jurisdiction, (color, linestyle, width, label_offset) in styles.items():
        series = sub[sub["jurisdiction"] == jurisdiction].sort_values("year")
        if series.empty:
            continue
        ax.plot(
            series["year"], series["value"], color=color, linestyle=linestyle,
            linewidth=width, solid_capstyle="round",
        )
        ax.plot([series["year"].iloc[-1]], [series["value"].iloc[-1]], "o",
                color=color, markersize=5, zorder=5)
        _end_label(ax, series["year"].iloc[-1], series["value"].iloc[-1],
                   f"{jurisdiction}  {series['value'].iloc[-1]:.1f}",
                   color, dy=label_offset)

    _heading(
        ax,
        "Homicide rates have converged across the UK",
        "Recorded victims per million people since 2000 · England and Wales reported jointly",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xlim(2000, sub["year"].max() + 5)
    ax.set_ylim(0, sub["value"].max() * 1.08)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=6))
    _style_axes(ax)
    _source_note(fig, sub)
    return _save(fig, out_dir, "crime_homicide_nations.png")


def _save(fig, out_dir, filename) -> pathlib.Path:
    plt.tight_layout(rect=(0.045, 0.075, 0.985, 0.985), pad=0.35)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(csew_source=None, homicide_source=None, nations_source=None,
                out_dir="outputs/crime") -> list[pathlib.Path]:
    """Render all crime charts that have data. Returns the written paths."""
    written: list[pathlib.Path] = []
    if csew_source is not None:
        cdf = _load(csew_source)
        for fn in (chart_csew_total, chart_csew_21st_century, chart_fraud_gap):
            p = fn(cdf, out_dir)
            if p:
                written.append(p)
    if homicide_source is not None:
        hdf = _load(homicide_source)
        p = chart_homicide_peers(hdf, out_dir)
        if p:
            written.append(p)
    if nations_source is not None:
        ndf = _load(nations_source)
        p = chart_homicide_nations(ndf, out_dir)
        if p:
            written.append(p)
    return written
