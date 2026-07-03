"""Generate trend charts from the combined NHS waiting-times table.

One chart per canonical metric, with a line per nation over time. Charts are
written to ``data/charts/``. Because metric definitions differ by nation
(see :data:`nhs_data.metrics.CAVEATS`), each chart is framed as a per-nation
*trend*, not a strict cross-nation comparison.
"""

from __future__ import annotations

from pathlib import Path

from . import metrics
from .paths import CHART_DIR, DEFAULT_CSV

# Stable colour per nation so charts are consistent.
NATION_COLOURS = {
    "ENG": "#e6194B",
    "SCO": "#4363d8",
    "WAL": "#3cb44b",
    "NIR": "#f58231",
}


def _load(source):
    import pandas as pd

    if source is None:
        source = DEFAULT_CSV
    if hasattr(source, "columns"):  # already a DataFrame
        return source
    return pd.read_csv(source)


def chart_metric(df, metric_id: str, out_dir: Path | str = CHART_DIR):
    """Render a single metric's per-nation trend chart. Returns the output path or None."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import pandas as pd

    meta = metrics.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    sub = sub.dropna(subset=["date"]).sort_values("date")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for code, g in sub.groupby("nation_code"):
        ax.plot(
            g["date"],
            g["value"],
            marker="o",
            markersize=3,
            linewidth=1.6,
            label=g["nation"].iloc[0],
            color=NATION_COLOURS.get(code),
        )

    ax.set_title(meta.label)
    ax.set_xlabel("Period")
    ylabel = meta.unit + (" (higher = better)" if meta.higher_is_better else "")
    ax.set_ylabel(ylabel)
    if meta.unit == "percent":
        ax.set_ylim(0, 100)
    if meta.unit == "patients":
        ax.get_yaxis().set_major_formatter(
            mticker.FuncFormatter(lambda v, _p: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k")
        )
    ax.grid(True, alpha=0.3)
    ax.legend(title="Nation", fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{metric_id}.png"
    fig.savefig(out_path, dpi=130)
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
