"""Generate trend charts from the combined trust table.

One chart per metric, with a line per country over time and the **UK highlighted** (bold,
dark line) against the EU-27 and US comparators (thin, faded). Charts are written to
``outputs/trust/``. Survey trust and WGI governance indicators are on different scales
(see :data:`trust_data.metrics.CAVEATS`), so each chart is a single-metric trend.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

from . import countries, metrics
from .paths import CHART_DIR, DEFAULT_LONG_CSV
from vizstyle import ACCENT, BLUE, GREEN, house_style, save_chart, with_year_gaps

# Group styling: the UK stands out; comparators are muted.
GROUP_STYLE = {
    countries.UK: {"color": ACCENT, "lw": 2.8, "alpha": 1.0, "zorder": 5},
    countries.EU: {"color": BLUE, "lw": 1.4, "alpha": 0.55, "zorder": 2},
    countries.US: {"color": GREEN, "lw": 1.8, "alpha": 0.9, "zorder": 4},
}


def _load(source):
    import pandas as pd

    if source is None:
        source = DEFAULT_LONG_CSV
    if hasattr(source, "columns"):  # already a DataFrame
        return source
    return pd.read_csv(source)


def chart_metric(df, metric_id: str, out_dir: Path | str = CHART_DIR):
    """Render a single metric's trend chart. Returns the output path or None if no data."""
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.ticker import PercentFormatter

    house_style()
    meta = metrics.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    sub["year"] = sub["year"].astype(int)
    sub = sub.sort_values("year")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sub = sub.copy()
    sub["group"] = sub["iso3"].map(countries.group_for_iso3)

    # EU-27: show a median line + interquartile band, not a spaghetti of 27 members.
    plotted_vals: list[float] = []
    eu = sub[sub["group"] == countries.EU]
    if not eu.empty:
        g = eu.groupby("year")["value"]
        med, q1, q3 = g.median(), g.quantile(0.25), g.quantile(0.75)
        if meta.family == "governance":
            med, q1, q3 = (with_year_gaps(values) for values in (med, q1, q3))
        eu_color = GROUP_STYLE[countries.EU]["color"]
        ax.fill_between(med.index, q1.values, q3.values, color=eu_color, alpha=0.15,
                        zorder=2, label="EU-27 reporters (middle 50%)")
        ax.plot(med.index, med.values, color=eu_color, linewidth=2.0, linestyle="--",
                marker="o" if meta.family == "governance" else None, markersize=2,
                zorder=3, label="EU-27 reporters median")
        plotted_vals += list(q1.values) + list(q3.values)

    for grp, lab in ((countries.US, "United States"), (countries.UK, "United Kingdom")):
        gg = sub[sub["group"] == grp].sort_values("year")
        if gg.empty:
            continue
        st = GROUP_STYLE[grp]
        values = pd.Series(gg["value"].values, index=gg["year"])
        if meta.family == "governance":
            values = with_year_gaps(values)
        ax.plot(values.index, values.values,
                marker="o" if grp == countries.UK or meta.family == "governance" else None,
                markersize=3, linewidth=st["lw"], color=st["color"],
                zorder=st["zorder"], label=lab)
        plotted_vals += list(gg["value"].astype(float))

    ax.set_title(meta.label)
    ax.set_xlabel("Pooled survey period ending" if meta.family == "survey" else "Year")
    direction = "more trust" if meta.family == "survey" else "better governance"
    unit = "Governance score" if meta.family == "governance" else meta.unit
    ax.set_ylabel(f"{unit} (higher = {direction})")
    if meta.unit == "percent" and plotted_vals:
        # Fit the axis to what is actually drawn (the EU middle-50% band + the US/UK
        # lines), rather than a fixed 0-100 that strands every line in empty space.
        lo, hi = min(plotted_vals), max(plotted_vals)
        pad = max((hi - lo) * 0.12, 1.0)
        ax.set_ylim(max(0.0, lo - pad), min(100.0, hi + pad))
        ax.yaxis.set_major_formatter(PercentFormatter())
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax.grid(True, axis="y", alpha=1.0)
    ax.legend(
        fontsize=9, frameon=False, loc="center left",
        bbox_to_anchor=(1.01, 0.5),
    )

    # Stamp the data source(s) straight from the data's own `source` column, mapped to a
    # formal short citation, so the caption is always traceable to the plotted rows.
    from . import citations

    sources = sorted(str(s) for s in sub["source"].dropna().unique())
    cites = "; ".join(citations.short_citation(s) for s in sources)
    year_lo, year_hi = int(sub["year"].min()), int(sub["year"].max())
    caption = f"Source: {cites}. Data: {year_lo}\u2013{year_hi}."
    if meta.family == "survey":
        caption += "\nSurvey values are 2- or 3-year pooled averages, labelled by period end."
    else:
        caption += "\nLines break at missing annual observations; isolated estimates are shown as points."
    if not eu.empty:
        counts = eu.groupby("year")["iso3"].nunique()
        coverage = str(counts.min()) if counts.min() == counts.max() else f"{counts.min()}\u2013{counts.max()}"
        caption += (
            f"\nEU: unweighted reporting-country median and middle 50% "
            f"(n={coverage} of 27; {counts.index.max()}: n={counts.iloc[-1]})."
        )
    caption = "\n".join(textwrap.fill(line, width=145) for line in caption.splitlines())
    footnote = fig.text(0.01, 0.01, caption, fontsize=8, color="#6B6B6B", ha="left", va="bottom")
    fig.canvas.draw()
    caption_top = footnote.get_window_extent(fig.canvas.get_renderer()).transformed(
        fig.transFigure.inverted()
    ).y1
    fig.tight_layout(rect=(0, max(0.09, caption_top + 0.025), 0.84, 1))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{metric_id}.png"
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_charts(source=None, out_dir: Path | str = CHART_DIR) -> list[Path]:
    """Render one chart per metric that has data. Returns the list of written paths."""
    df = _load(source)
    written: list[Path] = []
    for metric_id in metrics.METRICS:
        path = chart_metric(df, metric_id, out_dir)
        if path is not None:
            written.append(path)
    return written
