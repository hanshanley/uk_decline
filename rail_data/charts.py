"""House-style charts for the London rail-performance analysis.

Historical figures highlight London against Great Britain, weighting four consecutive
quarters by their planned-train counts. The current official figure uses ORR's published
moving annual average without recomputing it.

  - ``rail_london_casl.png`` — Cancellations & Significant Lateness (the disruption
    story: it has roughly doubled since the late 2000s).
  - ``rail_london_ppm.png``  — Public Performance Measure ("on time"), which has stayed
    broadly flat, i.e. the lenient headline hides the deterioration above.

Styling matches the sibling analyses (warm Substack tan, serif type, muted grid, UK/London
in the terracotta accent, italic source note).
"""

from __future__ import annotations

import pathlib
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import MUTED, TEXT, country_color, house_style, source_note, save_chart

LONDON = "London and South East"
GB = "Great Britain"

house_style()


def _load(source) -> pd.DataFrame:
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _maa(df: pd.DataFrame, region: str, metric: str) -> pd.DataFrame:
    """Planned-train-weighted share over four consecutive quarters, dated at quarter end."""
    sub = df[(df["region"] == region) & (df["metric"] == metric)].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    sub = sub.sort_values("date")
    if sub.empty:
        return sub.assign(maa=pd.Series(dtype=float))
    if "trains_planned" not in sub:
        raise ValueError("Rail annual shares require planned-train counts; refresh the ORR CSV")
    weights = pd.to_numeric(sub["trains_planned"], errors="coerce")
    if not (weights.notna() & weights.gt(0) & weights.lt(float("inf"))).all():
        raise ValueError("Rail annual shares require finite, positive planned-train counts")
    sub["trains_planned"] = weights
    sub = sub.set_index("date").reindex(
        pd.date_range(sub["date"].min(), sub["date"].max(), freq="QE")
    ).rename_axis("date").reset_index()
    weighted = (sub["value"] * sub["trains_planned"]).rolling(4, min_periods=4).sum()
    sub["maa"] = weighted / sub["trains_planned"].rolling(4, min_periods=4).sum()
    valid = sub.index[sub["maa"].notna()]
    if valid.empty:
        return sub.iloc[:0]
    return sub.loc[valid[0]:valid[-1]]


def _chart(df, metric, title, subtitle, ylabel, filename, out_dir):
    official = metric == "ppm_official_maa_pct"
    if official:
        selected = df[df["metric"] == metric].copy()
        selected["date"] = pd.to_datetime(selected["date"])
        selected["maa"] = selected["value"]
        series = []
        for region in (LONDON, GB):
            sub = selected[selected["region"] == region].set_index("date").sort_index()
            if not sub.empty:
                sub = sub.reindex(pd.date_range(sub.index.min(), sub.index.max(), freq="QE"))
            series.append(sub.rename_axis("date").reset_index())
        lon, gb = series
        if not selected.empty:
            latest = selected["date"].max()
            provisional = any("[p]" in str(period) for period in
                              selected.loc[selected["date"] == latest, "period"])
            subtitle += f" \u00b7 through {latest:%b %Y}" + (" (provisional)" if provisional else "")
    else:
        lon = _maa(df, LONDON, metric)
        gb = _maa(df, GB, metric)
    if lon.empty or gb.empty:
        return None
    if not official:
        latest = max(lon["date"].max(), gb["date"].max())
        subtitle += f" \u00b7 through {latest:%b %Y}"

    fig, ax = plt.subplots(figsize=(11, 6))
    line_style = {
        "markevery": 4,
        "markersize": 4.2,
        "markeredgecolor": "white",
        "markeredgewidth": 0.8,
    }
    ax.plot(gb["date"], gb["maa"], color=country_color("Great Britain"),
            label="Great Britain", linestyle="--", marker="s", linewidth=1.8, **line_style)
    ax.plot(lon["date"], lon["maa"], color=country_color("London"),
            label="London & South East", linestyle="-", marker="o", linewidth=2.4, **line_style)

    ax.set_title(title, fontweight="bold", pad=18)
    ax.text(0.5, 1.01, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10.5, color=MUTED)
    ax.set_xlabel("Year", labelpad=4)
    ax.set_ylabel(ylabel, labelpad=4)
    ax.yaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.xaxis.set_major_locator(mdates.YearLocator(1 if official else 4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.035)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 0.98),
        ncol=2,
        frameon=False,
        labelcolor=TEXT,
        columnspacing=1.8,
        handlelength=2.0,
    )
    fig.autofmt_xdate(rotation=30, ha="right")
    citation = (
        "Source: Office of Rail and Road (ORR), Data Portal Table 3113. "
        "Published sector aggregates and trains-weighted moving annual averages; "
        "not joined to the earlier reconstructed series."
        if official else
        "Source: Office of Rail and Road (ORR), Data Portal Table 3103. "
        "Reconstructed sector aggregates; percentages weighted by planned trains "
        "across four consecutive quarters, not official sector moving annual averages."
    )
    definition = (
        "Counts full or part cancellations and trains arriving more than 30 minutes late."
        if metric == "casl_pct" else
        "Arrival threshold: within 5 minutes for London, regional and other commuter trains; "
        "within 10 minutes for long-distance trains in the Great Britain comparison. "
        "This is not the stricter one-minute arrival measure."
    )
    source_note(fig, textwrap.fill(citation, width=145) + "\n"
                + textwrap.fill(definition, width=145))
    fig.tight_layout(rect=[0, 0.13, 1, 1], pad=0.7)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(source, out_dir="outputs/rail") -> list[pathlib.Path]:
    df = _load(source)
    written = []
    p = _chart(
        df, "casl_pct",
        "Rail disruption \u2014 London & South East",
        "Cancelled or more than 30 minutes late; four-quarter trains-weighted share",
        "Share of trains (%)\n(higher = worse)",
        "rail_london_casl.png", out_dir,
    )
    if p:
        written.append(p)
    p = _chart(
        df, "ppm_pct",
        "Rail punctuality \u2014 London & South East",
        "Arrivals within 5 or 10 minutes; four-quarter trains-weighted share",
        "Arrivals within 5 / 10 minutes (%)",
        "rail_london_ppm.png", out_dir,
    )
    if p:
        written.append(p)
    p = _chart(
        df, "ppm_official_maa_pct",
        "Rail punctuality \u2014 official London & South East series",
        "Arrivals within 5 or 10 minutes; published rolling annual average",
        "Arrivals within 5 / 10 minutes (%)",
        "rail_london_ppm_official.png", out_dir,
    )
    if p:
        written.append(p)
    return written
