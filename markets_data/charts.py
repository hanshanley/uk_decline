"""Generate stock-market-size trend charts from the combined table.

Produces one trend chart per metric (a line per region over time) plus two
**UK-as-a-share-of-US** ratio charts (market cap in US$, and market cap as % of
GDP), the headline framing for the UK-vs-US comparison. Charts land in
``outputs/stock_markets/``.

Styling follows the "Substack" theme shared with
``pre1870_reapportionment_package`` (warm paper background, serif type, muted
grid, top/right spines removed).
"""

from __future__ import annotations

from pathlib import Path

from . import markets, regions
from .paths import CHART_DIR, DEFAULT_CSV

# --- Substack-style theme (matches pre1870_reapportionment_package) ---
from vizstyle import (
    BG, TEXT, MUTED, GRID, ACCENT, RC_PARAMS as _THEME, house_style, save_chart,
    with_year_gaps as _with_year_gaps, mark_year_breaks,
)

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

SOURCE_NOTE = "Source: World Bank, World Development Indicators (CM.MKT.* indicators)."


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
    the World Bank indicator that redistributes it. Cached inputs do not establish
    a new source-access date.
    """
    note = markets.citation_short(metric_id)
    if metric_id == "market_cap_usd_real":
        note += (
            " Current-dollar market values deflated by US CPI, not national-accounts "
            "real output or PPP. Non-US markets retain exchange-rate movements. "
            "A common CPI deflator cancels from same-year UK/US ratios."
        )
    if metric_id == "listed_domestic_companies":
        note += (
            " China is shown separately: its 2019 total reconciles to exchange-listed "
            "plus NEEQ companies, unlike 2018 (CSRC Annual Report 2019, pp. 25, 29-30). "
            "The coverage jump is not like-for-like growth; dotted links mark this change."
        )
    return note


def _footnote(fig, note: str = SOURCE_NOTE) -> float:
    import textwrap

    note = "\n".join(textwrap.fill(line, width=145) for line in note.splitlines())
    caption = fig.text(0.01, 0.005, note, ha="left", fontsize=8, color=MUTED, style="italic")
    fig.canvas.draw()
    top = caption.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted()).y1
    return max(.02, top + .025)


def _save(fig, out_dir: Path | str, name: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / name
    save_chart(fig, out_path, dpi=200, bbox_inches="tight")
    return out_path


def _load(source):
    import pandas as pd

    if source is None:
        source = DEFAULT_CSV
    if hasattr(source, "columns"):  # already a DataFrame
        return source
    return pd.read_csv(source, float_precision="round_trip")


def _annotate_year_gaps(ax, series, label: str = "UK data unavailable", *, at_top=False) -> None:
    """Shade and label contiguous missing-year runs in an annual series."""
    missing = [int(year) for year, value in series.items() if value != value]
    if not missing:
        return
    spans: list[tuple[int, int]] = []
    start = previous = missing[0]
    for year in missing[1:]:
        if year == previous + 1:
            previous = year
            continue
        spans.append((start, previous))
        start = previous = year
    spans.append((start, previous))
    for start, end in spans:
        ax.axvspan(start - 0.5, end + 0.5, color=MUTED, alpha=0.07, linewidth=0)
        ax.text(
            (start + end) / 2,
            .98 if at_top else .035,
            f"{label}\n{start}\u2013{str(end)[-2:]}",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top" if at_top else "bottom",
            fontsize=8.2,
            color=MUTED,
            style="italic",
        )


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

    split = metric_id == "listed_domestic_companies" and "CHN" in set(sub["region_code"]) and sub["region_code"].nunique() > 1
    fig, grid = plt.subplots(1, 2 if split else 1, figsize=(13.5 if split else 11, 6),
                             squeeze=False, width_ratios=[1.5, 1] if split else [1])
    axes = grid[0]
    legend_labels = [[] for _ in axes]
    for code, g in sub.groupby("region_code"):
        panel = 1 if split and code == "CHN" else 0
        ax = axes[panel]
        is_uk = code == "GBR"
        observed = g.set_index("year")["value"]
        breaks = markets.LISTING_COVERAGE_BREAKS.get(code, ()) if metric_id == "listed_domestic_companies" else ()
        annual = _with_year_gaps(observed, breaks=breaks)
        ax.plot(
            annual.index,
            annual.values,
            marker="o" if is_uk else None,
            markersize=4,
            markeredgecolor="white",
            markeredgewidth=1.0,
            linewidth=2.8 if is_uk else 1.8,
            label=regions.name_for_code(code),
            color=regions.COLOURS.get(code),
            zorder=5 if is_uk else 3,
        )
        if is_uk:
            _annotate_year_gaps(ax, annual, at_top=split)
        if breaks:
            mark_year_breaks(ax, observed, breaks=breaks, color=regions.COLOURS.get(code), linewidth=1.8)
        legend_labels[panel].append(
            f"{regions.name_for_code(code)} ({int(g['year'].min())}\u2013{int(g['year'].max())})"
        )

    plotted_unit = str(sub["unit"].dropna().iloc[0]) if sub["unit"].notna().any() else meta.unit
    legend_handles = []
    combined_labels = []
    for panel, ax in enumerate(axes):
        ax.set_title(
            ("UK and international peers" if panel == 0 else "China: separate scale and coverage")
            if split else meta.label, fontweight="bold", pad=14,
            fontsize=14 if split else plt.rcParams["axes.titlesize"],
        )
        ax.set_xlabel("Year", labelpad=2)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(
            nbins=6 if split else 9, steps=[1, 2, 5, 10], integer=True,
        ))
        ax.set_ylabel(plotted_unit, labelpad=2)
        if "US$" in meta.unit:
            ax.get_yaxis().set_major_formatter(
                mticker.FuncFormatter(lambda v, _p: markets.format_usd(v))
            )
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.margins(x=0.02)
        handles, _ = ax.get_legend_handles_labels()
        if split:
            legend_handles.extend(handles)
            combined_labels.extend(legend_labels[panel])
        else:
            ax.legend(handles, legend_labels[panel], loc="upper left", frameon=False,
                      labelcolor="linecolor", fontsize=10)
    if split:
        fig.suptitle(meta.label, fontsize=20, fontweight="bold", y=.99)
        fig.legend(legend_handles, combined_labels, loc="upper center", bbox_to_anchor=(.5, .94),
                   ncol=3, frameon=False, labelcolor="linecolor", fontsize=9)
        axes[1].text(.03, .78, "2019: wider reporting coverage\nNot like-for-like company growth",
                     transform=axes[1].transAxes, va="top", fontsize=9, color=MUTED)
    bottom = _footnote(fig, _source_note(metric_id))
    if split:
        fig.subplots_adjust(left=.065, right=.99, bottom=max(.20, bottom + .08),
                            top=.79, wspace=.18)
    else:
        fig.tight_layout(rect=[0, bottom, 1, 1])

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
    pct = _with_year_gaps(ratio * 100)
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
        ax.text(pct.index[-1], 101, "UK = US (parity)", fontsize=9, color=MUTED,
                style="italic", va="bottom", ha="right")
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
    _annotate_year_gaps(ax, pct)
    bottom = _footnote(fig, _source_note(metric_id))
    fig.tight_layout(rect=[0, bottom, 1, 1])

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


def chart_lse_companies(source, out_dir: Path | str = CHART_DIR) -> Path:
    """Chart LSE UK-classified companies without splicing in WDI counts."""
    import pandas as pd
    import matplotlib.ticker as mticker

    df = _load(source)
    sub = df[
        (df["region"] == "United Kingdom") & (df["metric"] == "lse_companies_uk")
    ].copy()
    if sub.empty:
        raise ValueError("No LSE UK company counts to chart")
    sub["date"] = pd.to_datetime(sub["date"], errors="raise")
    sub = sub.sort_values("date").drop_duplicates("year", keep="last")
    annual = _with_year_gaps(sub.set_index("year")["value"])
    latest = sub.iloc[-1]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(
        annual.index, annual.values, color=ACCENT, linewidth=2.8, marker="o",
        markersize=4, markeredgecolor="white", markeredgewidth=1,
    )
    _end_label(ax, sub["year"], sub["value"], f'{latest["value"]:,.0f}', ACCENT)
    ax.set_title("UK companies on the London Stock Exchange", fontweight="bold", pad=30)
    ax.text(
        0.5, 1.015,
        f'Main Market + Alternative Investment Market; '
        f'latest snapshot {latest["date"].strftime("%d %B %Y")}',
        transform=ax.transAxes, ha="center", va="bottom", fontsize=12, color=MUTED,
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("UK-classified companies")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.margins(x=0.07)
    bottom = _footnote(
        fig,
        "Source: London Stock Exchange Main Market and Alternative Investment Market factsheets. December snapshots, "
        "except latest partial year.\n"
        "Includes investment companies; not the World Bank / World Federation of Exchanges definition. "
        "Starts after the May 2018 Main Market coverage change.",
    )
    fig.tight_layout(rect=[0, max(.05, bottom), 1, 1])
    out = _save(fig, out_dir, "stock_lse_uk_companies.png")
    plt.close(fig)
    return out
