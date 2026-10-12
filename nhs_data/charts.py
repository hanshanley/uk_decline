"""Generate trend charts from the combined NHS waiting-times table.

One chart per canonical metric, with a line per nation over time. Charts are
written to ``outputs/nhs/``. Because metric definitions differ by nation
(see :data:`nhs_data.metrics.CAVEATS`), each chart is framed as a per-nation
*trend*, not a strict cross-nation comparison.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

from . import _util, metrics  # noqa: E402
from .paths import CHART_DIR, DEFAULT_CSV  # noqa: E402

# ── Substack-style theme (matches personal_projects/pre1870_reapportionment_package) ──
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, BLUE, GOLD, GREEN, house_style

house_style()

# Stable colour per nation, drawn from the theme's muted palette.
NATION_COLOURS = {
    "ENG": ACCENT,
    "SCO": BLUE,
    "WAL": GREEN,
    "NIR": GOLD,
}

NATION_SOURCES = {
    "ENG": "NHS England",
    "SCO": "Public Health Scotland",
    "WAL": "StatsWales",
    "NIR": "DoH Northern Ireland",
}
POP_SOURCE_NOTE = " Population: ONS/NRS/NISRA mid-year estimates (via Nomis)."


def _load(source):
    return _util.load_frame(source, DEFAULT_CSV)


def _shared_baseline_date(sub, metric_id=None):
    """Earliest shared date after the latest definition change in the observed data."""
    import pandas as pd

    date_sets = [set(g["date"]) for _, g in sub.groupby("nation_code")]
    if not date_sets:
        return None
    common = set.intersection(*date_sets)
    if metric_id is not None:
        for code, g in sub.groupby("nation_code"):
            for date, _ in metrics.series_breaks(metric_id, code):
                boundary = pd.Timestamp(date)
                if boundary <= g["date"].max():
                    common = {d for d in common if d >= boundary}
    return min(common) if common else None


def chart_metric(df, metric_id: str, out_dir: Path | str = CHART_DIR, indexed: bool = False):
    """Render a single metric's per-nation trend chart. Returns the output path or None.

    When ``indexed`` is True, each nation's series is rebased to 100 at its first
    shared observation date, so growth uses a common baseline.
    """
    import pandas as pd

    meta = metrics.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    sub = sub.dropna(subset=["date"]).sort_values("date")

    # Rebase every nation to the earliest exact date that all nations publish. This avoids
    # silently comparing monthly and quarterly series against different baseline dates.
    base_date = None
    if indexed:
        base_date = _shared_baseline_date(sub, metric_id)
        if base_date is None:
            _util.warn("charts", metric_id, ValueError(
                "no shared observation date within comparable definition periods"
            ))
            return None

    fig, ax = plt.subplots(figsize=(11, 6))
    plotted_codes = set()
    for code, g in sub.groupby("nation_code"):
        g = g.sort_values("date")
        if indexed:
            g = g[g["date"] >= base_date]
        yvals = g["value"]
        if indexed:
            at_base = g[g["date"] == base_date]
            if at_base.empty or not at_base["value"].iloc[0]:
                continue
            base = at_base["value"].iloc[0]
            yvals = yvals / base * 100.0
        label = g["nation"].iloc[0]
        if indexed:
            label = f"{label} (\u00d7{g['value'].iloc[-1] / base:.2f})"
        boundaries = [pd.Timestamp(date) for date, _ in metrics.series_breaks(metric_id, code)]
        segments = g["date"].map(lambda d: sum(d >= boundary for boundary in boundaries))
        labelled = False
        for _, segment in g.groupby(segments):
            ax.plot(
                segment["date"],
                yvals.loc[segment.index],
                marker="o",
                markersize=4,
                markeredgecolor="white",
                markeredgewidth=0.8,
                linewidth=2.4,
                label=label if not labelled else "_nolegend_",
                color=NATION_COLOURS.get(code),
            )
            labelled = True
        plotted_codes.add(code)

    direction = "higher = better" if meta.higher_is_better else "lower = better"
    if indexed:
        ax.axhline(100, color=MUTED, linewidth=1.0, linestyle=":")
        base_period = f"{base_date:%b %Y}"
        ax.set_title(f"{meta.label}\ngrowth indexed to {base_period} (= 100)",
                     fontweight="bold", pad=14)
        ax.set_ylabel(f"Index, {base_period} = 100 ({direction})", labelpad=2)
    else:
        ax.set_title(meta.label, fontweight="bold", pad=14)
        ax.set_ylabel(f"{meta.unit} ({direction})", labelpad=2)
    ax.set_xlabel("Period", labelpad=2)
    if not indexed and meta.unit == "percent":
        # Fit to the plotted data (with a margin) instead of a fixed 0-100 that strands
        # the lines in the top third; keep the axis within the valid 0-100% range.
        lo, hi = float(sub["value"].min()), float(sub["value"].max())
        pad = max((hi - lo) * 0.10, 2.0)
        ax.set_ylim(max(0.0, lo - pad), min(100.0, hi + pad))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    if not indexed and meta.unit == "pathways / waits":
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _p: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k")
        )
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.legend(title="Nation", loc="best", frameon=False, labelcolor=TEXT)
    fig.autofmt_xdate()
    note = "Sources: " + ", ".join(
        source for code, source in NATION_SOURCES.items() if code in plotted_codes
    ) + "."
    if metric_id == "rtt_waiting_list_per_1000":
        note += POP_SOURCE_NOTE
    if metric_id in metrics.CAVEATS:
        note += "\n" + textwrap.fill("Caveat: " + metrics.CAVEATS[metric_id], width=145)
    affected = [
        f"{code}: {', '.join(date[:7] for date, _ in metrics.series_breaks(metric_id, code))}"
        for code in sorted(plotted_codes) if metrics.series_breaks(metric_id, code)
    ]
    if affected:
        note += "\n" + textwrap.fill(
            "Definition/recording changes (" + "; ".join(affected)
            + "); lines do not bridge them.", width=145
        )
    caption = fig.text(0.01, 0.01, note, ha="left", va="bottom",
                       fontsize=8, color=MUTED, style="italic")
    fig.canvas.draw()
    caption_top = caption.get_window_extent(fig.canvas.get_renderer()).transformed(
        fig.transFigure.inverted()
    ).y1
    fig.tight_layout(rect=[0, max(0.11, caption_top + 0.025), 1, 1])

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
        if metrics.METRICS[metric_id].unit == "pathways / waits":
            ipath = chart_metric(df, metric_id, out_dir, indexed=True)
            if ipath is not None:
                written.append(ipath)
    return written
