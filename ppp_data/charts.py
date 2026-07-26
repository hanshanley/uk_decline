"""The PPP figures — the parallel, purchasing-power view of the UK's relative position.

Six charts, all written to ``outputs/ppp/`` in the shared house style:

1. ``ppp_gdp_per_capita_over_time``   levels at PPP, constant 2021 international $
2. ``ppp_gdp_relative_to_peers``      peers as a share of the UK, at PPP
3. ``ppp_vs_market_fx_uk_us``         the UK vs the US on both bases at once
4. ``price_level_index``              the sterling/price-level effect on its own
5. ``ppp_gap_decomposition_uk_us``    how much of the fall vs the US is real vs currency
6. ``ppp_gdp_long_run_maddison``      the long run, on the Maddison 2011 benchmark

Every figure states its PPP vintage in the source note, and every figure that could be read
as "the real number" carries a one-line reminder that market exchange rates and PPP answer
different questions.

Which series each chart may use is not left to the author's memory: level charts go through
:func:`ppp_data.metrics.require_over_time` and ratio charts through
:func:`ppp_data.metrics.require_cross_section`, so picking an inflation-carrying series for
a trend, or a benchmark-extrapolated series for a cross-country ratio, raises rather than
quietly producing a plausible-looking but wrong picture.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.ticker as mtick

from vizstyle import ACCENT, BLUE, GRID, MUTED, TEXT, save_fig, source_note, white_stroke

from . import decompose, metrics, peers, series
from .figure import labelled_ends, note as _note, span as _span, subtitle as _subtitle, themed_plt as _plt, tidy as _tidy
from .paths import CHART_DIR

# World Bank PPP coverage begins in 1990; the market-FX comparator is trimmed to match so
# the two bases are always compared over identical years.
START_YEAR = 1990

# The baseline year for the real-vs-currency decomposition: the UK's high-water mark against
# the US, and the year the rest of the repository measures decline from.
DECOMPOSITION_START_YEAR = 2007

_WB = "Data: World Bank Group, World Development Indicators"
_FRAMING = (
    "Market exchange rates measure what UK output buys on world markets; PPP measures what "
    "it buys at home. Neither is the truer number \u2014 they answer different questions."
)


# ── 1. Levels at PPP ─────────────────────────────────────────────────────────
def chart_gdp_per_capita(rows: list[dict], out_dir: Path) -> Path | None:
    """UK vs peers, real GDP per capita at PPP, constant 2021 international $."""
    metric = "gdp_per_capita_ppp_constant"
    meta = metrics.require_over_time(metric)
    plotted = {p.iso3: series.xy(series.series(rows, metric, p.iso3), START_YEAR)
               for p in peers.PEERS}
    if not any(xs for xs, _ in plotted.values()):
        return None  # a partial fetch: skip rather than publish an empty figure
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))

    uk_latest = None
    spans: list[list[int]] = []
    for peer in peers.PEERS:
        xs, ys = plotted[peer.iso3]
        if not xs:
            continue
        spans.append(xs)
        ys = [y / 1000.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth, label=peer.label,
                marker="o" if peer.iso3 == peers.UK else None, markersize=4.5,
                markeredgecolor="white", markeredgewidth=1.0,
                zorder=5 if peer.iso3 == peers.UK else 3)
        if peer.iso3 == peers.UK:
            uk_latest = (xs[-1], ys[-1])

    ax.set_title(f"Real GDP per capita at purchasing power parity, {_span(*spans)}",
                 fontweight="bold", pad=30)
    if uk_latest:
        _subtitle(ax, f"The UK reached ${uk_latest[1]:,.0f}k per head in {uk_latest[0]}, "
                      "measured at domestic price levels")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    _tidy(ax, ylabel=f"GDP per capita (000s, {meta.unit})")
    ax.legend(loc="upper left", frameon=False, labelcolor="linecolor", fontsize=10)

    source_note(fig, _note(
        f"{_WB} \u2014 GDP per capita, PPP ({meta.wb_indicator}), {meta.unit} "
        f"[{meta.vintage} benchmark].", _FRAMING))
    return save_fig(fig, out_dir / "ppp_gdp_per_capita_over_time.png")


# ── 2. Peers relative to the UK, at PPP ──────────────────────────────────────
def chart_relative_to_peers(rows: list[dict], out_dir: Path) -> Path | None:
    """Each peer's GDP per capita as a percentage of the UK's, at PPP (UK = 100)."""
    metric = "gdp_per_capita_ppp_current"
    meta = metrics.require_cross_section(metric)
    plotted = {p.iso3: series.xy(series.ratio(rows, metric, p.iso3, peers.UK), START_YEAR)
               for p in peers.RELATIVE_PEERS}
    if not any(xs for xs, _ in plotted.values()):
        return None  # no peer has a UK ratio: skip rather than publish an empty figure
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    facts: list[str] = []
    spans: list[list[int]] = []
    labels: list[tuple[float, str, str]] = []
    last_x = None
    for peer in peers.RELATIVE_PEERS:
        xs, ys = plotted[peer.iso3]
        if not xs:
            continue
        spans.append(xs)
        ys = [y * 100.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth)
        labels.append((ys[-1], peer.label, peer.colour))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
        if peer.iso3 == "POL":
            facts.append(f"Poland climbed from {ys[0]:.0f}% of the UK to {ys[-1]:.0f}%")
        elif peer.iso3 == "USA":
            facts.append(f"the US stands at {ys[-1]:.0f}%")

    ax.axhline(100, color=ACCENT, linewidth=1.4)
    ax.text(ax.get_xlim()[0], 101.5, "United Kingdom = 100", fontsize=9.5, color=ACCENT,
            style="italic", fontweight="bold", va="bottom", path_effects=white_stroke())
    if last_x is not None:
        # France and the EU average both finish within a point or two of the UK baseline,
        # so their labels are spread apart rather than drawn on top of one another.
        labelled_ends(ax, labels, min_gap=4.0, x=last_x)

    ax.set_title(f"GDP per capita relative to the UK at PPP, {_span(*spans)}",
                 fontweight="bold", pad=30)
    if facts:
        _subtitle(ax, "At domestic price levels, " + ", while ".join(facts))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, ylabel="GDP per capita as % of the UK (UK = 100)")

    source_note(fig, _note(
        f"{_WB} \u2014 GDP per capita, PPP ({meta.wb_indicator}), {meta.unit} "
        f"[{meta.vintage} benchmark].",
        "Current-price international dollars are used because this is a same-year "
        "cross-country ratio."))
    return save_fig(fig, out_dir / "ppp_gdp_relative_to_peers.png")


# ── 3. The two bases side by side ────────────────────────────────────────────
def chart_ppp_vs_market_fx(rows: list[dict], out_dir: Path) -> Path | None:
    """The UK as a share of the US, at market exchange rates and at PPP."""
    fx_metric, ppp_metric = "gdp_per_capita_nominal_usd", "gdp_per_capita_ppp_current"
    metrics.require_cross_section(fx_metric)
    metrics.require_cross_section(ppp_metric)

    fx = series.ratio(rows, fx_metric, peers.UK, peers.US)
    ppp = series.ratio(rows, ppp_metric, peers.UK, peers.US)
    years = [y for y in sorted(fx.keys() & ppp.keys()) if y >= START_YEAR]
    if not years:
        return None  # both bases are needed to draw the comparison at all
    fx_pct = [fx[y] * 100 for y in years]
    ppp_pct = [ppp[y] * 100 for y in years]

    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.fill_between(years, fx_pct, ppp_pct, color=MUTED, alpha=0.14, zorder=1)
    ax.plot(years, fx_pct, color=ACCENT, linewidth=2.8, zorder=4)
    ax.plot(years, ppp_pct, color=BLUE, linewidth=2.8, zorder=4)
    labelled_ends(ax, [(fx_pct[-1], "at market\nexchange rates", ACCENT),
                       (ppp_pct[-1], "at PPP", BLUE)],
                  min_gap=3.0, x=years[-1], fontsize=9.5)

    peak_year = max(years, key=lambda y: fx[y])
    peak_pct = fx[peak_year] * 100
    ax.plot([peak_year], [peak_pct], "o", color=ACCENT, markersize=7,
            markeredgecolor="white", markeredgewidth=1.4, zorder=6)
    # Anchored below-left of the peak: above it would run into the title block.
    ax.annotate(
        f"{peak_year}: the sterling peak\n{peak_pct:.0f}% of the US at market rates,\n"
        f"but only {ppp[peak_year]*100:.0f}% at PPP",
        xy=(peak_year, peak_pct), xytext=(years[0] + 1, peak_pct - 12),
        fontsize=9.5, color=TEXT, va="top", ha="left", path_effects=white_stroke(),
        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.9,
                    "connectionstyle": "arc3,rad=0.15"})

    mid = (fx_pct[-1] + ppp_pct[-1]) / 2
    ax.annotate("the gap is the\nexchange rate", xy=(years[-1] - 2, mid), fontsize=9.5,
                color=MUTED, style="italic", ha="right", va="center",
                path_effects=white_stroke())

    ax.set_title("How much of the UK's fall against the US is real?",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"At market rates the UK fell from {peak_pct:.0f}% of the US in "
                  f"{peak_year} to {fx_pct[-1]:.0f}% in {years[-1]}; at PPP it went from "
                  f"{ppp[peak_year]*100:.0f}% to {ppp_pct[-1]:.0f}%")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, ylabel="UK GDP per capita as % of the US")

    source_note(fig, _note(
        f"{_WB} \u2014 GDP per capita in current US$ (NY.GDP.PCAP.CD) and in current "
        f"international $ (NY.GDP.PCAP.PP.CD) [{metrics.ICP_VINTAGE} benchmark]. Same-year "
        "ratios, so both are free of inflation.", _FRAMING))
    return save_fig(fig, out_dir / "ppp_vs_market_fx_uk_us.png")


# ── 4. The price level index ─────────────────────────────────────────────────
def chart_price_level_index(rows: list[dict], out_dir: Path) -> Path | None:
    """Each country's price level relative to the United States (US = 1.00)."""
    metric = "price_level_index"
    meta = metrics.require_over_time(metric)
    uk = series.series(rows, metric, peers.UK)
    uk_years = series.years_between(uk, START_YEAR)
    if not uk_years:
        return None  # the UK is the subject of this figure; without it there is nothing to say
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    labels: list[tuple[float, str, str]] = []
    last_x = None
    for peer in peers.PRICE_LEVEL_PEERS:
        xs, ys = series.xy(series.series(rows, metric, peer.iso3), START_YEAR)
        if not xs:
            continue
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth,
                zorder=5 if peer.iso3 == peers.UK else 3)
        labels.append((ys[-1], peer.label, peer.colour))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
    if last_x is not None:
        labelled_ends(ax, labels, min_gap=0.035, x=last_x, fontsize=9.5)

    ax.axhline(1.0, color=TEXT, linewidth=1.2, linestyle="--", alpha=0.7)
    ax.text(ax.get_xlim()[0], 1.012, "United States = 1.00", fontsize=9.5, color=TEXT,
            style="italic", va="bottom", path_effects=white_stroke())

    peak_year = max(uk_years, key=lambda y: uk[y])
    ax.plot([peak_year], [uk[peak_year]], "o", color=ACCENT, markersize=7,
            markeredgecolor="white", markeredgewidth=1.4, zorder=6)

    ax.set_title("How expensive is Britain? Price levels relative to the United States",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"UK prices peaked at {uk[peak_year]:.2f}\u00d7 US levels in {peak_year} "
                  f"and are {uk[uk_years[-1]]:.2f}\u00d7 today \u2014 the whole difference "
                  "between the market-FX and PPP views")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.2f}"))
    _tidy(ax, ylabel=meta.unit)

    source_note(fig, _note(
        f"{_WB} \u2014 derived as GDP per capita in current US$ (NY.GDP.PCAP.CD) over GDP "
        f"per capita in current international $ (NY.GDP.PCAP.PP.CD) [{meta.vintage} "
        "benchmark].",
        "Computing it this way cancels local-currency units, so it is unaffected by the "
        "euro changeover."))
    return save_fig(fig, out_dir / "price_level_index.png")


# ── 5. The decomposition ─────────────────────────────────────────────────────
def uk_us_decomposition(rows: list[dict], start_year: int,
                        end_year: int | None = None) -> decompose.Decomposition:
    """Split the change in the UK/US market-FX ratio into real and price-level parts."""
    ppp = series.ratio(rows, "gdp_per_capita_ppp_current", peers.UK, peers.US)
    pli = series.series(rows, "price_level_index", peers.UK)
    us_pli = series.series(rows, "price_level_index", peers.US)
    shared = sorted(ppp.keys() & pli.keys() & us_pli.keys())
    if not shared:
        raise ValueError("no year has both a UK/US PPP ratio and a UK price level index")
    end_year = end_year if end_year is not None else shared[-1]
    for year in (start_year, end_year):
        if year not in shared:
            raise ValueError(f"{year} is not covered by both series (have {shared[0]}-{shared[-1]})")
    return decompose.decompose_ratio_change(
        start_year=start_year, end_year=end_year,
        ppp_ratio_start=ppp[start_year], ppp_ratio_end=ppp[end_year],
        # The US price level is the numeraire (1.00), so the UK index is already the ratio.
        pli_ratio_start=pli[start_year] / us_pli[start_year],
        pli_ratio_end=pli[end_year] / us_pli[end_year],
    )


def chart_decomposition(rows: list[dict], out_dir: Path,
                        start_year: int = DECOMPOSITION_START_YEAR) -> Path | None:
    """Why the UK fell against the US: the two contributions, in percentage points.

    Deliberately **not** a waterfall. A waterfall would put the endpoint levels (105% and
    64% of the US) and the two changes (-2.9 and -38.5 points) on one axis, so bars drawn
    from zero and bars floating in mid-air would look like the same kind of quantity when
    they are not. This chart plots one quantity only — the contribution to the change, in
    percentage points — and leaves the levels to the subtitle and the endpoint annotation.

    ``start_year`` defaults to 2007, the UK's high-water mark and the baseline the rest of
    the repository measures from. If the fetched range does not reach that far back — the
    ``--start`` flag can move it — the figure is skipped rather than aborting a run whose
    CSVs and manifest have already been written.
    """
    try:
        d = uk_us_decomposition(rows, start_year)
    except ValueError:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 5.6))

    # Top to bottom: the big driver, the small one, then the total they sum to.
    bars = [
        ("Price level and\nexchange rate", d.price_effect, ACCENT),
        ("Real output\nper head", d.real_effect, BLUE),
        (f"Total change\n{d.start_year}\u2013{d.end_year}", d.total_change, TEXT),
    ]
    ys = [2.0, 1.0, -0.15]  # the total is set slightly apart, below a divider

    for y, (_, value, colour) in zip(ys, bars):
        ax.barh(y, value, height=0.55, color=colour, zorder=3)
        ax.text(value - 0.7, y, f"{value:+.1f} pp", va="center", ha="right",
                fontsize=12.5, fontweight="bold", color=colour,
                path_effects=white_stroke())

    ax.axhline(0.45, color=GRID, linewidth=1.0, zorder=2)
    ax.axvline(0, color=TEXT, linewidth=1.2, zorder=4)

    share = abs(d.price_effect) / abs(d.total_change) * 100 if d.total_change else 0.0
    ax.text(d.price_effect + 0.7, ys[0] - 0.42,
            f"{share:.0f}% of the total fall", fontsize=10, color=MUTED, style="italic",
            va="top", ha="left", path_effects=white_stroke())

    ax.set_yticks(ys)
    ax.set_yticklabels([label for label, _, _ in bars], fontsize=11, color=TEXT)
    ax.set_ylim(-0.75, 2.6)
    # Leave room to the left of the longest bar for its outside value label, which would
    # otherwise run into the y tick labels.
    widest = min(value for _, value, _ in bars)
    ax.set_xlim(widest * 1.28, abs(widest) * 0.03)

    ax.set_title(f"Almost none of the UK's fall against the US since {d.start_year} "
                 "is lost output", fontweight="bold", pad=30)
    _subtitle(ax, f"UK GDP per head went from {d.start_ratio:.0f}% of the US in "
                  f"{d.start_year} to {d.end_ratio:.0f}% in {d.end_year}. Splitting that "
                  f"{abs(d.total_change):.0f}-point fall into its two causes:")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.set_xlabel("Contribution to the change in UK GDP per capita vs the US "
                  "(percentage points)", labelpad=6)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(y=0)

    source_note(fig, _note(
        f"{_WB} \u2014 NY.GDP.PCAP.CD, NY.GDP.PCAP.PP.CD [{metrics.ICP_VINTAGE} benchmark]. "
        "Symmetric (Shapley) decomposition of UK/US = (real ratio) \u00d7 (relative price "
        "level); the two contributions sum exactly to the total.",
        "A weaker pound does make imports dearer, so this is not a clean bill of health "
        "\u2014 it relocates the story from lost output to lost purchasing power abroad."))
    return save_fig(fig, out_dir / "ppp_gap_decomposition_uk_us.png", bottom=0.20)


# ── 6. The long run, on the Maddison benchmark ───────────────────────────────
def chart_long_run(rows: list[dict], out_dir: Path) -> Path | None:
    """Maddison's long-run PPP series, which reaches back before the World Bank's 1990."""
    metric = "gdp_per_capita_real_maddison"
    meta = metrics.require_over_time(metric)
    if not any(r["metric"] == metric for r in rows):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))

    uk_latest = None
    for peer in peers.PEERS:
        xs, ys = series.xy(series.series(rows, metric, peer.iso3))
        if not xs:
            continue
        ys = [y / 1000.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth, label=peer.label,
                zorder=5 if peer.iso3 == peers.UK else 3)
        if peer.iso3 == peers.UK:
            uk_latest = (xs[0], xs[-1])

    span = f"{uk_latest[0]}\u2013{uk_latest[1]}" if uk_latest else "the long run"
    ax.set_title(f"Real GDP per capita at PPP over the long run, {span}",
                 fontweight="bold", pad=30)
    _subtitle(ax, "Maddison's 2011 benchmark \u2014 a different vintage from the World Bank "
                  "series above, so the two are never spliced")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    _tidy(ax, ylabel=f"GDP per capita (000s, {meta.unit})")
    ax.legend(loc="upper left", frameon=False, labelcolor="linecolor", fontsize=10)

    source_note(fig, _note(
        f"Data: Maddison Project Database 2023 (Bolt & van Zanden), via Our World in Data "
        f"\u2014 {meta.unit}.",
        "Benchmarked on ICP 2011, so its levels are not comparable with the World Bank's "
        "ICP 2021 series."))
    return save_fig(fig, out_dir / "ppp_gdp_long_run_maddison.png")


CHARTS = (
    chart_gdp_per_capita,
    chart_relative_to_peers,
    chart_ppp_vs_market_fx,
    chart_price_level_index,
    chart_decomposition,
    chart_long_run,
)


def make_charts(rows: list[dict], out_dir: Path | str = CHART_DIR) -> list[Path]:
    """Render every PPP figure. Returns the paths written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for chart in CHARTS:
        path = chart(rows, out_dir)
        if path is not None:
            written.append(path)
    return written
