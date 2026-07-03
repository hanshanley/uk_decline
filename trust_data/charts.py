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
    countries.UK: {"color": "#C0392B", "lw": 2.8, "alpha": 1.0, "zorder": 5},
    countries.EU: {"color": "#1F5C99", "lw": 1.4, "alpha": 0.55, "zorder": 2},
    countries.US: {"color": "#2A9D8F", "lw": 1.8, "alpha": 0.9, "zorder": 4},
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
        "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
        "savefig.facecolor": "#FFFFFF", "text.color": "#111827",
        "axes.labelcolor": "#374151", "xtick.color": "#6B7280", "ytick.color": "#6B7280",
        "axes.edgecolor": "#D1D5DB", "axes.linewidth": 0.8,
        "grid.color": "#E5E7EB", "grid.alpha": 1.0, "grid.linewidth": 0.9,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
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
    uk_labelled = eu_labelled = us_labelled = False
    for iso3, g in sub.groupby("iso3"):
        group = countries.group_for_iso3(iso3)
        style = GROUP_STYLE.get(group, GROUP_STYLE[countries.EU])
        label = None
        if group == countries.UK and not uk_labelled:
            label, uk_labelled = "United Kingdom", True
        elif group == countries.US and not us_labelled:
            label, us_labelled = "United States", True
        elif group == countries.EU and not eu_labelled:
            label, eu_labelled = "EU-27 members", True
        ax.plot(
            g["year"],
            g["value"],
            marker="o" if group == countries.UK else None,
            markersize=3,
            linewidth=style["lw"],
            alpha=style["alpha"],
            color=style["color"],
            zorder=style["zorder"],
            label=label,
        )

    ax.set_title(meta.label)
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{meta.unit} (higher = more trust)")
    if meta.unit == "percent":
        ax.set_ylim(0, 100)
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
    fig.text(0.01, 0.01, caption, fontsize=7, color="#6B7280", ha="left", va="bottom")
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
