"""Generate trend charts from the combined trust table.

One chart per metric, with a line per country over time and the **UK highlighted** (bold,
dark line) against the EU-27 and US comparators (thin, faded). Charts are written to
``data/trust/charts/``. Survey trust and WGI governance indicators are on different scales
(see :data:`trust_data.metrics.CAVEATS`), so each chart is a single-metric trend.
"""

from __future__ import annotations

from pathlib import Path

from . import countries, metrics
from .paths import CHART_DIR, DEFAULT_LONG_CSV

# Group styling: the UK stands out; comparators are muted.
GROUP_STYLE = {
    countries.UK: {"color": "#C85A3D", "lw": 2.8, "alpha": 1.0, "zorder": 5},
    countries.EU: {"color": "#3D6F8C", "lw": 1.4, "alpha": 0.55, "zorder": 2},
    countries.US: {"color": "#4A7C59", "lw": 1.8, "alpha": 0.9, "zorder": 4},
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
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": "#F7F5F0", "axes.facecolor": "#F7F5F0",
        "savefig.facecolor": "#F7F5F0", "text.color": "#1A1A1A",
        "axes.labelcolor": "#1A1A1A", "xtick.color": "#6B6B6B", "ytick.color": "#6B6B6B",
        "axes.edgecolor": "#D6D3CC", "axes.linewidth": 0.8,
        "grid.color": "#D6D3CC", "grid.alpha": 0.6, "grid.linewidth": 0.5,
        "font.family": "serif",
        "font.size": 12, "axes.titlesize": 16, "axes.titleweight": "bold",
        "legend.framealpha": 0.0, "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.size": 0, "ytick.major.size": 0,
    })
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
    eu = sub[sub["group"] == countries.EU]
    if not eu.empty:
        g = eu.groupby("year")["value"]
        med, q1, q3 = g.median(), g.quantile(0.25), g.quantile(0.75)
        eu_color = GROUP_STYLE[countries.EU]["color"]
        ax.fill_between(med.index, q1.values, q3.values, color=eu_color, alpha=0.15,
                        zorder=2, label="EU-27 (middle 50%)")
        ax.plot(med.index, med.values, color=eu_color, linewidth=2.0, linestyle="--",
                zorder=3, label="EU-27 median")

    for grp, lab in ((countries.US, "United States"), (countries.UK, "United Kingdom")):
        gg = sub[sub["group"] == grp].sort_values("year")
        if gg.empty:
            continue
        st = GROUP_STYLE[grp]
        ax.plot(gg["year"], gg["value"], marker="o" if grp == countries.UK else None,
                markersize=3, linewidth=st["lw"], color=st["color"],
                zorder=st["zorder"], label=lab)

    ax.set_title(meta.label)
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{meta.unit} (higher = more trust)")
    if meta.unit == "percent":
        # Fit the axis to the data (incl. the EU band) with a small margin, rather than
        # a fixed 0-100 that strands every line in the middle of empty space.
        lo, hi = float(sub["value"].min()), float(sub["value"].max())
        pad = max((hi - lo) * 0.12, 1.0)
        ax.set_ylim(max(0.0, lo - pad), min(100.0, hi + pad))
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax.grid(True, axis="y", alpha=1.0)
    ax.legend(fontsize=9, frameon=False)

    # Stamp the data source(s) straight from the data's own `source` column, mapped to a
    # formal short citation, so the caption is always traceable to the plotted rows.
    from . import citations

    sources = sorted(str(s) for s in sub["source"].dropna().unique())
    cites = "; ".join(citations.short_citation(s) for s in sources)
    year_lo, year_hi = int(sub["year"].min()), int(sub["year"].max())
    caption = f"Source: {cites}. Data: {year_lo}\u2013{year_hi}."
    fig.text(0.01, 0.01, caption, fontsize=7, color="#6B6B6B", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.035, 1, 1))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{metric_id}.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
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
