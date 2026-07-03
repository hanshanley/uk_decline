"""Generate trend charts from the combined NHS waiting-times table.

One chart per canonical metric, with a line per nation over time. Charts are
written to ``data/charts/``. Because metric definitions differ by nation
(see :data:`nhs_data.metrics.CAVEATS`), each chart is framed as a per-nation
*trend*, not a strict cross-nation comparison.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

from . import _util, metrics  # noqa: E402
from .paths import CHART_DIR, DEFAULT_CSV  # noqa: E402

# ── Substack-style theme (matches personal_projects/pre1870_reapportionment_package) ──
BG = "#F7F5F0"
TEXT = "#1A1A1A"
MUTED = "#6B6B6B"
GRID = "#D6D3CC"
ACCENT = "#C85A3D"
BLUE = "#3D6F8C"
GOLD = "#C2993E"
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
        "font.family": "serif", "font.size": 12,
        "axes.titlesize": 16,
        "axes.labelsize": 13,
        "figure.titlesize": 18,
        "legend.framealpha": 0.0,
        "legend.fontsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# Stable colour per nation, drawn from the theme's muted palette.
NATION_COLOURS = {
    "ENG": ACCENT,
    "SCO": BLUE,
    "WAL": GREEN,
    "NIR": GOLD,
}

SOURCE_NOTE = "Sources: NHS England, Public Health Scotland, StatsWales, DoH Northern Ireland."
POP_SOURCE_NOTE = " Population: ONS/NRS/NISRA mid-year estimates (via Nomis)."


def _load(source):
    return _util.load_frame(source, DEFAULT_CSV)


def chart_metric(df, metric_id: str, out_dir: Path | str = CHART_DIR, indexed: bool = False):
    """Render a single metric's per-nation trend chart. Returns the output path or None.

    When ``indexed`` is True, each nation's series is rebased to 100 at its first
    observation, so nations of very different absolute size (e.g. England ~7M vs
    Wales ~0.7M) can be compared on a single growth scale.
    """
    import pandas as pd

    meta = metrics.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    sub = sub.dropna(subset=["date"]).sort_values("date")

    fig, ax = plt.subplots(figsize=(11, 6))
    for code, g in sub.groupby("nation_code"):
        g = g.sort_values("date")
        yvals = g["value"]
        if indexed:
            base = yvals.iloc[0]
            if not base:
                continue
            yvals = yvals / base * 100.0
        label = g["nation"].iloc[0]
        if indexed:
            label = f"{label} (\u00d7{g['value'].iloc[-1] / g['value'].iloc[0]:.2f})"
        ax.plot(
            g["date"],
            yvals,
            marker="o",
            markersize=4,
            markeredgecolor="white",
            markeredgewidth=0.8,
            linewidth=2.4,
            label=label,
            color=NATION_COLOURS.get(code),
        )

    direction = "higher = better" if meta.higher_is_better else "lower = better"
    if indexed:
        ax.axhline(100, color=MUTED, linewidth=1.0, linestyle=":")
        ax.set_title(f"{meta.label}\ngrowth indexed to each nation's first period (= 100)",
                     fontweight="bold", pad=14)
        ax.set_ylabel(f"Index, first period = 100 ({direction})", labelpad=2)
    else:
        ax.set_title(meta.label, fontweight="bold", pad=14)
        ax.set_ylabel(f"{meta.unit} ({direction})", labelpad=2)
    ax.set_xlabel("Period", labelpad=2)
    if not indexed and meta.unit == "percent":
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    if not indexed and meta.unit == "patients":
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _p: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k")
        )
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.legend(title="Nation", loc="best", frameon=False, labelcolor=TEXT)
    fig.autofmt_xdate()
    note = SOURCE_NOTE + (POP_SOURCE_NOTE if metric_id == "rtt_waiting_list_per_1000" else "")
    fig.text(0.01, 0.01, note, ha="left", fontsize=8, color=MUTED, style="italic")
    fig.tight_layout(rect=[0, 0.03, 1, 1])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_indexed" if indexed else ""
    out_path = out_dir / f"{metric_id}{suffix}.png"
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
        # For absolute head-count metrics, also emit an indexed (growth) view so nations
        # of very different size are comparable.
        if metrics.METRICS[metric_id].unit == "patients":
            ipath = chart_metric(df, metric_id, out_dir, indexed=True)
            if ipath is not None:
                written.append(ipath)
    return written
