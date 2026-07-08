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
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, RC_PARAMS as _THEME, house_style

# World Bank "World" is a super-aggregate (the sum of every market), so it always
# towers over the country lines and crushes the UK-vs-peers comparison. Exclude it
# from the per-region level charts; the UK/US ratio charts tell the size story.
_EXCLUDE_FROM_TRENDS = {"WLD"}

_STROKE = None  # lazy patheffects (needs matplotlib import)


def _end_label(ax, xs, ys, text, color):
    """Label a line at its final point (right side), with a white halo."""
    import matplotlib.patheffects as pe

    xs, ys = list(xs), list(ys)
    if not xs:
        return
    ax.text(xs[-1] + (xs[-1] - xs[0]) * 0.01, ys[-1], text, fontsize=10.5,
            fontweight="bold", color=color, va="center", ha="left",
            path_effects=[pe.withStroke(linewidth=3.0, foreground="white")])

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
    sub = sub[~sub["region_code"].isin(_EXCLUDE_FROM_TRENDS)]
    if sub.empty:
        return None
    sub = sub.dropna(subset=["value"]).sort_values("year")

    fig, ax = plt.subplots(figsize=(11, 6))
    for code, g in sub.groupby("region_code"):
        region = regions.BY_CODE.get(code)
        is_uk = code == "GBR"
        ax.plot(
            g["year"],
            g["value"],
            marker="o" if is_uk else None,
            markersize=4,
            markeredgecolor="white",
            markeredgewidth=1.0,
            linewidth=2.8 if is_uk else 1.8,
            label=regions.name_for_code(code),
            color=regions.COLOURS.get(code),
            zorder=5 if is_uk else 3,
        )

    ax.set_title(meta.label, fontweight="bold", pad=14)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel(meta.unit, labelpad=2)
    if "US$" in meta.unit:
        ax.get_yaxis().set_major_formatter(
            mticker.FuncFormatter(lambda v, _p: markets.format_usd(v))
        )
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.02)
    ax.legend(loc="upper left", frameon=False, labelcolor="linecolor", fontsize=10)
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
    pct = ratio * 100
    peak_year = int(pct.idxmax())
    peak_val = float(pct.max())
    last_year = int(pct.index[-1])
    last_val = float(pct.iloc[-1])

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(pct.index, pct.values, marker="o", markersize=3.5,
            linewidth=2.8, color=ACCENT, markeredgecolor="white", markeredgewidth=0.8)
    _end_label(ax, pct.index, pct.values, f"{last_val:.0f}%", ACCENT)

    top = max(peak_val, last_val)
    # Only draw the US-parity line when the data actually comes near it, otherwise
    # it just strands the whole series at the bottom of an empty axis.
    if top >= 60:
        ax.axhline(100, color=MUTED, linewidth=0.9, linestyle="--", alpha=0.7)
        ax.text(pct.index[0], 101, "UK = US (parity)", fontsize=9, color=MUTED,
                style="italic", va="bottom")
        ax.set_ylim(0, max(top * 1.12, 105))
    else:
        ax.set_ylim(0, top * 1.18)

    ax.set_title(f"UK {meta.label.lower()} as a share of the US",
                 fontweight="bold", pad=30)
    ax.text(0.5, 1.015,
            f"From {peak_val:.0f}% at its {peak_year} peak to {last_val:.0f}% by {last_year}",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=12, color=MUTED)
    ax.set_xlabel("Year", labelpad=2)
    ax.set_ylabel("UK as % of US", labelpad=2)
    ax.get_yaxis().set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.03)
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
