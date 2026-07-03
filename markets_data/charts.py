"""Generate stock-market-size trend charts from the combined table.

Produces one trend chart per metric (a line per region over time) plus two
**UK-as-a-share-of-US** ratio charts (market cap in US$, and market cap as % of
GDP), the headline framing for the UK-vs-US comparison. Charts land in
``data/charts/``.

Styling follows the "Substack" theme shared with
``pre1870_reapportionment_package`` (warm paper background, serif type, muted
grid, top/right spines removed).
"""

from __future__ import annotations

from pathlib import Path

from . import markets, regions
from .paths import CHART_DIR, DEFAULT_CSV

# --- Substack-style theme (matches pre1870_reapportionment_package) ---
BG = "#FFFFFF"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"

_THEME = {
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": GRID,
    "grid.color": GRID,
    "grid.alpha": 1.0,
    "grid.linewidth": 0.9,
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 12,
    "axes.titlesize": 16,
    "axes.labelsize": 13,
    "figure.titlesize": 18,
    "legend.framealpha": 0.0,
    "legend.fontsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

SOURCE_NOTE = "Source: World Bank WDI (CM.MKT.* indicators). No API key."


def _plt():
    """Return a themed pyplot (Agg backend), applying the shared rcParams once."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(_THEME)
    return plt


def _source_note(metric_id: str) -> str:
    """Build a figure footnote that cites the organization that collected the data.

    Uses the formal citation registry (``markets.citation_short``) so every figure
    names its collecting organization (e.g. the World Federation of Exchanges) and
    the World Bank indicator that redistributes it, dated to the run.
    """
    import datetime as _dt

    return markets.citation_short(metric_id, accessed=_dt.date.today().isoformat())


def _footnote(fig, note: str = SOURCE_NOTE) -> None:
    fig.text(0.01, 0.005, note, ha="left", fontsize=8, color=MUTED, style="italic")


def _save(fig, out_dir: Path | str, name: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / name
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return out_path


def _load(source):
    import pandas as pd

    if source is None:
        source = DEFAULT_CSV
    if hasattr(source, "columns"):  # already a DataFrame
        return source
    return pd.read_csv(source)


def chart_metric(df, metric_id: str, out_dir: Path | str = CHART_DIR):
    """Render a single metric's per-region trend chart. Returns the path or None."""
    plt = _plt()
    import matplotlib.ticker as mticker

    meta = markets.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    sub = sub.dropna(subset=["value"]).sort_values("year")

    fig, ax = plt.subplots(figsize=(11, 6))
    for code, g in sub.groupby("region_code"):
        region = regions.BY_CODE.get(code)
        is_core = bool(region and region.core)
        ax.plot(
            g["year"],
            g["value"],
            marker="o",
            markersize=3,
            linewidth=2.4 if is_core else 1.4,
            label=regions.name_for_code(code),
            color=regions.COLOURS.get(code),
            alpha=1.0 if is_core else 0.75,
        )

    ax.set_title(meta.label, fontweight="bold", pad=14)
    ax.set_xlabel("Year")
    ax.set_ylabel(meta.unit)
    if "US$" in meta.unit:
        ax.get_yaxis().set_major_formatter(
            mticker.FuncFormatter(lambda v, _p: markets.format_usd(v))
        )
    ax.grid(axis="y")
    ax.legend(title="Region", loc="upper left")
    _footnote(fig, _source_note(metric_id))
    fig.tight_layout(rect=[0, 0.02, 1, 1])

    out = _save(fig, out_dir, f"stock_{metric_id}.png")
    plt.close(fig)
    return out


def chart_uk_us_ratio(df, metric_id: str, out_dir: Path | str = CHART_DIR):
    """Render UK market size as a share of the US, over time. Returns path or None."""
    plt = _plt()
    import matplotlib.ticker as mticker

    meta = markets.METRICS[metric_id]
    sub = df[df["metric"] == metric_id].copy()
    if sub.empty:
        return None
    ratio = markets.uk_us_ratio(sub)
    if ratio is None:
        return None

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(ratio.index, ratio.values * 100, marker="o", markersize=3,
            linewidth=2.4, color=regions.COLOURS["GBR"])
    ax.axhline(100, color=MUTED, linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_title(f"UK {meta.label.lower()} as a share of the US",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Year")
    ax.set_ylabel("UK / US (%)")
    ax.get_yaxis().set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.grid(axis="y")
    ax.set_ylim(bottom=0)
    _footnote(fig, _source_note(metric_id))
    fig.tight_layout(rect=[0, 0.02, 1, 1])

    out = _save(fig, out_dir, f"stock_uk_us_ratio_{metric_id}.png")
    plt.close(fig)
    return out


def make_charts(source=None, out_dir: Path | str = CHART_DIR) -> list[Path]:
    """Render every metric chart plus the UK/US ratio charts. Returns written paths."""
    df = _load(source)
    written: list[Path] = []
    for metric_id in markets.METRICS:
        p = chart_metric(df, metric_id, out_dir)
        if p is not None:
            written.append(p)
    for metric_id in ("market_cap_usd", "market_cap_usd_real", "market_cap_pct_gdp"):
        p = chart_uk_us_ratio(df, metric_id, out_dir)
        if p is not None:
            written.append(p)
    return written
