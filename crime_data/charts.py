"""House-style charts for the crime analysis (five figures).

All use the shared ``vizstyle`` house theme (warm tan, serif, UK in the terracotta accent,
italic source note taken from the data's own ``source`` column):

  1. ``crime_csew_total.png``   — long-run total CSEW crime, England & Wales, 1981->latest:
     the large fall from the mid-1990s peak.
  2. ``crime_csew_21st_century.png`` — the same series zoomed to the 21st century.
  3. ``crime_fraud_gap.png``    — the same headline total *excluding* vs *including* fraud &
     computer misuse: the broader definition includes substantial additional harms.
  4. ``crime_homicide_peers.png`` — intentional homicide rate, UK vs US vs the EU-27 mean.
  5. ``crime_homicide_nations.png`` — homicide rates across England & Wales, Scotland,
     and Northern Ireland since 2000.
"""

from __future__ import annotations

import pathlib
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BLUE, GRID, MUTED, country_color, RC_PARAMS as _THEME, white_stroke, save_chart

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
    fig.text(
        0.06, 0.01, textwrap.fill(f"Source: {srcs}.", width=170),
        ha="left", va="bottom", fontsize=7.5, color=MUTED,
    )
    if "offence_group" in df.columns:
        fig.text(
            0.06, 0.049,
            "No comparable crime-survey estimates for years ending March 2021 or 2022; "
            "lines break at missing annual observations.",
            ha="left", fontsize=7.5, color=MUTED,
        )


def _series(df, offence_group) -> pd.DataFrame:
    sub = df[df["offence_group"] == offence_group].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    return sub.sort_values("date")


def _csew_segments(series):
    """Retain irregular early surveys, but do not bridge gaps in the annual series."""
    dates = series["date"]
    gaps = (
        (dates.diff() > pd.Timedelta(days=370))
        & (dates.shift() >= pd.Timestamp("2002-03-31"))
    )
    return series.groupby(gaps.cumsum())


def _plot_csew(ax, series, **style):
    for _, segment in _csew_segments(series):
        ax.plot(segment["date"], segment["value"] / 1_000.0,
                marker="o", markersize=3, solid_capstyle="round", **style)


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
    _plot_csew(ax, s, color=ACCENT, linewidth=2.7, label="Traditional crime (million incidents)")

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
        f"Traditional crime is down {decline:.0f}% from its {x[peak].year} peak",
        "England & Wales · household crime survey, excluding fraud and computer misuse",
        y.max() * 1.10,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(x.iloc[0] - pd.DateOffset(years=1),
                x.iloc[-1] + (x.iloc[-1] - x.iloc[0]) * 0.02)
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
    _plot_csew(ax, s, color=ACCENT, linewidth=2.7, label="Traditional crime (million incidents)")

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
        "England & Wales · household crime survey, excluding fraud and computer misuse",
        y.max() * 1.10,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(x.iloc[0] - pd.DateOffset(years=1),
                x.iloc[-1] + (x.iloc[-1] - x.iloc[0]) * 0.02)
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

    gap = incl.merge(excl, on="date", suffixes=("_incl", "_excl"))
    if gap.empty:
        raise ValueError("fraud-gap chart requires matching CSEW survey periods")
    gap = gap.sort_values("date")
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    xe, ye = excl["date"], excl["value"] / 1_000.0
    xi, yi = incl["date"], incl["value"] / 1_000.0
    for _, segment in _csew_segments(gap):
        ax.fill_between(
            segment["date"], segment["value_incl"] / 1_000.0,
            segment["value_excl"] / 1_000.0, color=ACCENT, alpha=0.075,
        )
    _plot_csew(ax, incl, color=ACCENT, linewidth=2.7, label="Including fraud and computer misuse (million incidents)")
    _plot_csew(ax, excl, color=BLUE, linewidth=2.25, label="Excluding fraud and computer misuse (million incidents)")
    ax.plot([xi.iloc[-1]], [yi.iloc[-1]], "o", color=ACCENT, markersize=5, zorder=5)
    ax.plot([xe.iloc[-1]], [ye.iloc[-1]], "o", color=BLUE, markersize=5, zorder=5)
    _end_label(ax, xi.iloc[-1], yi.iloc[-1], f"Including fraud &\ncomputer misuse  {yi.iloc[-1]:.1f}M",
               ACCENT)
    _end_label(ax, xe.iloc[-1], ye.iloc[-1], f"Excluding fraud &\ncomputer misuse  {ye.iloc[-1]:.1f}M",
               BLUE)

    latest = gap.iloc[-1]
    fraud_and_misuse_share = (
        (latest["value_incl"] - latest["value_excl"]) / latest["value_incl"] * 100
    )
    latest_gap = (latest["value_incl"] - latest["value_excl"]) / 1_000.0
    ax.annotate(
        f"{latest_gap:.1f}M fraud &\ncomputer misuse",
        xy=(latest["date"], (latest["value_incl"] + latest["value_excl"]) / 2_000.0),
        xytext=(-48, 0), textcoords="offset points", ha="right", va="center",
        fontsize=9, color=MUTED,
    )
    _style_incidents_axes(
        ax,
        f"Fraud & computer misuse: {fraud_and_misuse_share:.0f}% of headline crime "
        f"(year ending {latest['date']:%B %Y})",
        "England & Wales · household crime survey, with and without fraud and computer misuse",
        max(yi.max(), ye.max()) * 1.12,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(xi.iloc[0] - pd.DateOffset(months=8),
                xi.iloc[-1] + (xi.iloc[-1] - xi.iloc[0]) * 0.02)
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
        linestyle=(0, (4, 3)), label="EU-27 reporting-country mean",
    )
    xus, yus = line("USA")
    ax.plot(xus, yus, color=country_color("USA"), linewidth=2.2, solid_capstyle="round", label="United States")
    xuk, yuk = line("GBR")
    ax.plot(xuk, yuk, color=ACCENT, linewidth=2.7, solid_capstyle="round", label="United Kingdom")

    if len(eu_mean):
        _end_label(ax, eu_mean.index[-1], eu_mean.values[-1],
                   f"EU-27  {eu_mean.values[-1]:.1f} ({int(eu_mean.index[-1])})", MUTED, dy=-13)
    if len(xus):
        _end_label(ax, xus.iloc[-1], yus.iloc[-1],
                   f"United States  {yus.iloc[-1]:.1f} ({int(xus.iloc[-1])})", country_color("USA"))
    if len(xuk):
        _end_label(ax, xuk.iloc[-1], yuk.iloc[-1],
                   f"United Kingdom  {yuk.iloc[-1]:.1f} ({int(xuk.iloc[-1])})", ACCENT, dy=11)
    for xs, ys, color in ((xus, yus, country_color("USA")), (xuk, yuk, country_color("UK"))):
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
    ax.set_xlim(sub["year"].min() - 1, sub["year"].max() + 0.5)
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
        "England & Wales": (country_color("England & Wales"), "-", 2.7, 0),
        "Scotland": (country_color("Scotland"), "-", 2.15, -13),
        "Northern Ireland": (country_color("Northern Ireland"), (0, (4, 3)), 1.65, 13),
    }
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    for jurisdiction, (color, linestyle, width, label_offset) in styles.items():
        series = sub[sub["jurisdiction"] == jurisdiction].sort_values("year")
        if series.empty:
            continue
        ax.plot(
            series["year"], series["value"], color=color, linestyle=linestyle,
            linewidth=width, solid_capstyle="round", label=jurisdiction,
        )
        ax.plot([series["year"].iloc[-1]], [series["value"].iloc[-1]], "o",
                color=color, markersize=5, zorder=5)
        _end_label(ax, series["year"].iloc[-1], series["value"].iloc[-1],
                   f"{jurisdiction}  {series['value'].iloc[-1]:.1f}"
                   f" ({int(series['year'].iloc[-1])})",
                   color, dy=label_offset)

    _heading(
        ax,
        "Homicide rates have converged across the UK",
        "Recorded victims per million people since 2000 · England and Wales reported jointly",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xlim(2000, sub["year"].max() + 0.5)
    ax.set_ylim(0, sub["value"].max() * 1.08)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=6))
    _style_axes(ax)
    _source_note(fig, sub)
    fig.text(
        0.06, 0.075,
        "Periods: England & Wales and Scotland = financial-year ends; "
        "Northern Ireland = calendar years. NI counts are chart-derived.",
        ha="left", fontsize=7.5, color=MUTED,
    )
    return _save(fig, out_dir, "crime_homicide_nations.png", bottom=0.12)


def _save(fig, out_dir, filename, *, bottom=0.075) -> pathlib.Path:
    plt.tight_layout(rect=(0.045, bottom, 0.985, 0.985), pad=0.35)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    save_chart(plt.gcf(), out_path, dpi=200, bbox_inches="tight")
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
