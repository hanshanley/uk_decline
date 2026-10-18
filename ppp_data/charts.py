"""The PPP figures — the parallel, purchasing-power view of the UK's relative position.

Seven charts, all written to ``outputs/ppp/`` in the shared house style:

1. ``ppp_gdp_per_capita_over_time``   levels at PPP, constant 2021 international $
2. ``ppp_gdp_relative_to_peers``      peers as a share of the UK, at PPP
3. ``ppp_vs_market_fx_uk_us``         the UK vs the US on both bases at once
4. ``price_level_index``             GDP-wide relative prices, not consumer cost of living
5. ``ppp_gap_decomposition_uk_us``    relative volumes and a price/exchange-rate residual
6. ``ppp_gdp_long_run_maddison``      the long run, on the Maddison 2011 benchmark
7. ``ppp_gdp_per_capita_growth``     real growth since 2007, each country starts at 100

Every figure states its PPP vintage in the source note, and every figure that could be read
as "the real number" carries a one-line reminder that market exchange rates and PPP answer
different questions.

Which series each chart may use is not left to the author's memory: level charts go through
:func:`ppp_data.metrics.require_over_time` and ratio charts through
:func:`ppp_data.metrics.require_cross_section`, so picking an inflation-carrying series for
a real-growth trend raises rather than silently mistaking price changes for output.
Constant-PPP comparisons are labelled as benchmark-valued volumes, not annual PPP levels.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.ticker as mtick

from vizstyle import (
    ACCENT, BLUE, GREEN, GRID, MUTED, TEXT, save_fig, source_note, white_stroke,
)

from . import decompose, metrics, peers, series
from .figure import labelled_ends, note as _note, span as _span, subtitle as _subtitle, themed_plt as _plt, tidy as _tidy
from .paths import CHART_DIR

# World Bank PPP coverage begins in 1990; the market-FX comparator is trimmed to match so
# the two bases are always compared over identical years.
START_YEAR = 1990

# The baseline year for the real-vs-currency decomposition: the UK's high-water mark against
# the US, and the year the rest of the repository measures decline from. Single source of
# truth lives in `metrics` so `validate`'s guards can never check a different year.
DECOMPOSITION_START_YEAR = metrics.DECOMPOSITION_BASELINE_YEAR

_WB = "Data: World Bank Group, World Development Indicators"
# Kept deliberately short: it appears on the figures that show both bases, where a long
# paragraph would crowd the plot. The full argument is in ppp_data/README.md.
_FRAMING = ("Market-exchange-rate valuations and purchasing-power-adjusted output volumes "
            "answer different questions; "
            "neither is household income.")


# ── 1. Levels at PPP ─────────────────────────────────────────────────────────
def chart_gdp_per_capita(rows: list[dict], out_dir: Path) -> Path | None:
    """UK vs peers, real GDP per capita at PPP, constant 2021 international $."""
    metric = "gdp_per_capita_ppp_constant"
    meta = metrics.require_over_time(metric)
    plotted = {p.iso3: series.xy(series.series(rows, metric, p.iso3), START_YEAR)
               for p in peers.GDP_PEERS}
    if not any(xs for xs, _ in plotted.values()):
        return None  # a partial fetch: skip rather than publish an empty figure
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))

    uk_latest = None
    spans: list[list[int]] = []
    labels: list[tuple[float, str, str, float]] = []
    last_x = None
    for peer in peers.GDP_PEERS:
        xs, ys = plotted[peer.iso3]
        if not xs:
            continue
        spans.append(xs)
        ys = [y / 1000.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle, label=peer.label,
                linewidth=peer.linewidth,
                marker="o" if peer.iso3 == peers.UK else None, markersize=4.5,
                markeredgecolor="white", markeredgewidth=1.0,
                zorder=5 if peer.iso3 == peers.UK else 3)
        labels.append((ys[-1], f"{peer.label} ({xs[-1]})", peer.colour, xs[-1]))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
        if peer.iso3 == peers.UK:
            uk_latest = (xs[-1], ys[-1])

    ax.set_title(f"Real GDP per capita at purchasing power parity, {_span(*spans)}",
                 fontweight="bold", pad=30)
    if uk_latest:
        _subtitle(ax, f"The UK reached ${uk_latest[1]:,.0f}k per head in {uk_latest[0]}, "
                      f"valued at the 2021 purchasing power parity benchmark")
    labelled_ends(ax, labels, min_gap=max(item[0] for item in labels) * 0.045, x=last_x,
                  fontsize=10)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    _tidy(ax, ylabel=f"GDP per capita (000s, {meta.unit})")
    ax.margins(x=0.12)  # room on the right for the end labels

    source_note(fig, _note(
        f"{_WB} \u2014 GDP per capita at purchasing power parity ({meta.wb_indicator}), {meta.unit} "
        f"[{meta.vintage} benchmark].",
        "Fixed purchasing power parities measure volume growth on a fixed benchmark. Cross-country levels "
        "are benchmark-sensitive, not annually repriced comparisons. GDP per head "
        "is not median household income."))
    return save_fig(fig, out_dir / "ppp_gdp_per_capita_over_time.png", bottom=0.17)


def chart_volume_growth(rows: list[dict], out_dir: Path,
                        start_year: int = DECOMPOSITION_START_YEAR) -> Path | None:
    """Real output growth per head, indexed to the same observed baseline."""
    metric = "gdp_per_capita_ppp_constant"
    metrics.require_over_time(metric)
    plotted = {}
    growth_peers = peers.GDP_PEERS
    for peer in growth_peers:
        data = series.series(rows, metric, peer.iso3)
        if start_year in data and data[start_year] > 0:
            xs, ys = series.xy(data, start_year)
            plotted[peer.iso3] = (xs, [100 * y / data[start_year] for y in ys])
    if peers.UK not in plotted or peers.US not in plotted:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    labels = []
    for peer in growth_peers:
        if peer.iso3 not in plotted:
            continue
        xs, ys = plotted[peer.iso3]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle, label=peer.label,
                linewidth=peer.linewidth)
        labels.append((ys[-1], f"{peer.label} ({xs[-1]})", peer.colour, xs[-1]))
    ax.axhline(100, color=MUTED, linewidth=0.8, linestyle="--")
    labelled_ends(ax, labels, min_gap=3.0,
                  x=max(xs[-1] for xs, _ in plotted.values()), fontsize=10)
    ax.set_title(f"Real GDP per head growth since {start_year}",
                 fontweight="bold", pad=30)
    _subtitle(ax, "Each economy starts at 100; this compares growth, not starting GDP levels")
    _tidy(ax, ylabel=f"Real GDP per capita index ({start_year} = 100)")
    ax.margins(x=0.14)
    source_note(fig, _note(
        f"{_WB} \u2014 NY.GDP.PCAP.PP.KD, constant 2021 international dollars "
        f"[{metrics.ICP_VINTAGE}]. Each series divided by its own observed {start_year} "
        "value. Fixed purchasing power parity conversion factors cancel; neither annual "
        "market exchange rates nor changing international price weights drive these growth indices."))
    return save_fig(fig, out_dir / "ppp_gdp_per_capita_growth.png", bottom=0.17)


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
    labels: list[tuple[float, str, str, float]] = []
    last_x = None
    for peer in peers.RELATIVE_PEERS:
        xs, ys = plotted[peer.iso3]
        if not xs:
            continue
        spans.append(xs)
        ys = [y * 100.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle, label=peer.label,
                linewidth=peer.linewidth)
        labels.append((ys[-1], f"{peer.label} ({xs[-1]})", peer.colour, xs[-1]))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
        if peer.iso3 == "POL":
            # Retain the documented reporting window without claiming survey provenance.
            first = next((i for i, year in enumerate(xs)
                          if year >= metrics.PEER_COMPARISON_START_YEAR), 0)
            facts.append(f"Poland climbed from {ys[first]:.0f}% of the UK in {xs[first]} "
                         f"to {ys[-1]:.0f}% in {xs[-1]}")
        elif peer.iso3 == "USA":
            facts.append(f"the US stands at {ys[-1]:.0f}% in {xs[-1]}")

    ax.axhline(100, color=ACCENT, linewidth=1.4)
    ax.text(ax.get_xlim()[0], 101.5, "United Kingdom = 100", fontsize=9.5, color=ACCENT,
            style="italic", fontweight="bold", va="bottom", path_effects=white_stroke())
    if last_x is not None:
        # France and the EU average both finish within a point or two of the UK baseline,
        # so their labels are spread apart rather than drawn on top of one another.
        labelled_ends(ax, labels, min_gap=4.0, x=last_x)

    ax.set_title(f"GDP per person relative to the UK, {_span(*spans)}\n"
                 "Adjusted for purchasing power at each year's prices",
                 fontweight="bold", pad=30)
    if facts:
        _subtitle(ax, "At domestic price levels, " + ", while ".join(facts))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, ylabel="GDP per capita as % of the UK (UK = 100)")

    source_note(fig, _note(
        f"{_WB} \u2014 GDP per capita at purchasing power parity ({meta.wb_indicator}), {meta.unit} "
        f"[{meta.vintage} benchmark].",
        "Annual purchasing power parities compare output at each year's prices. Changes in these ratios "
        "also reflect changing price weights and parity estimates, not just real growth."))
    return save_fig(fig, out_dir / "ppp_gdp_relative_to_peers.png", bottom=0.17)


# ── 3. The two bases side by side ────────────────────────────────────────────
def chart_ppp_vs_market_fx(rows: list[dict], out_dir: Path) -> Path | None:
    """The UK as a share of the US on all three measures that matter.

    Three lines, because two would mislead. The market-FX and PPP-level lines alone invite
    the reading "the PPP line is the real story, so almost nothing was lost" — but the
    current-price PPP line is a *level* comparison at each year's prices, and its movement is
    not pure volume growth. The constant-price line is, and it falls considerably further.
    Showing all three keeps this figure consistent with the decomposition chart, which splits
    the market-FX fall using the volume series.
    """
    fx_metric, ppp_metric = "gdp_per_capita_nominal_usd", "gdp_per_capita_ppp_current"
    metrics.require_cross_section(fx_metric)
    metrics.require_cross_section(ppp_metric)

    fx = series.ratio(rows, fx_metric, peers.UK, peers.US)
    ppp = series.ratio(rows, ppp_metric, peers.UK, peers.US)
    real = series.ratio(rows, "gdp_per_capita_ppp_constant", peers.UK, peers.US)
    years = [y for y in sorted(fx.keys() & ppp.keys() & real.keys()) if y >= START_YEAR]
    if not years:
        return None
    fx_pct = [fx[y] * 100 for y in years]
    ppp_pct = [ppp[y] * 100 for y in years]
    real_pct = [real[y] * 100 for y in years]

    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.fill_between(years, fx_pct, ppp_pct, color=MUTED, alpha=0.13, zorder=1)
    ax.plot(years, fx_pct, color=ACCENT, linewidth=2.8, zorder=4, label="At market exchange rates")
    ax.plot(years, ppp_pct, color=ACCENT, linewidth=2.2, linestyle="--", zorder=4, label="Purchasing power (current prices)")
    ax.plot(years, real_pct, color=ACCENT, linewidth=1.8, linestyle=":", zorder=3, label="Purchasing power (constant prices)")

    labelled_ends(ax, [(fx_pct[-1], "at market\nexchange rates", ACCENT, years[-1]),
                       (ppp_pct[-1], "purchasing power\n(current prices)", ACCENT, years[-1]),
                       (real_pct[-1], "output volumes\n(2021 price benchmark)", ACCENT, years[-1])],
                  min_gap=4.5, x=years[-1], fontsize=9.5)

    peak_year = max(years, key=lambda y: fx[y])
    peak_pct = fx[peak_year] * 100
    ax.plot([peak_year], [peak_pct], "o", color=ACCENT, markersize=7,
            markeredgecolor="white", markeredgewidth=1.4, zorder=6, label="At market exchange rates")
    ax.annotate(
        f"{peak_year}: peak dollar GDP ratio\n{peak_pct:.0f}% of the US at market rates,\n"
        f"but {ppp[peak_year]*100:.0f}% after adjusting for local prices",
        xy=(peak_year, peak_pct), xytext=(years[0] + 1, peak_pct - 12),
        fontsize=9.5, color=TEXT, va="top", ha="left", path_effects=white_stroke(),
        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.9,
                    "connectionstyle": "arc3,rad=0.15"})

    # Every line on this axis is "UK as % of the US", so state all three the same way — as
    # levels on that axis, not as a mix of levels and percentage changes.
    real_then = real[peak_year] * 100
    ax.set_title("UK GDP per head relative to the US: three measures",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"Market-rate ratio: {peak_pct:.0f}% in {peak_year} to "
                  f"{fx_pct[-1]:.0f}% in {years[-1]}; volume ratio over those years: "
                  f"{real_then:.0f}% to {real_pct[-1]:.0f}%")

    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, ylabel="UK GDP per capita as % of the US")
    ax.margins(x=0.14)

    source_note(fig, _note(
        f"{_WB} \u2014 NY.GDP.PCAP.CD (market rates), NY.GDP.PCAP.PP.CD (purchasing power parity) and "
        f"NY.GDP.PCAP.PP.KD (real volumes), {metrics.ICP_VINTAGE} benchmark. The purchasing-power "
        "line compares GDP at each year's prices; the constant-price line tracks relative "
        "volume growth on the 2021 benchmark. The market-rate peak is not proof of a peak "
        "in sterling itself.", _FRAMING))
    return save_fig(fig, out_dir / "ppp_vs_market_fx_uk_us.png", bottom=0.17)


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

    labels: list[tuple[float, str, str, float]] = []
    last_x = None
    for peer in peers.PRICE_LEVEL_PEERS:
        xs, ys = series.xy(series.series(rows, metric, peer.iso3), START_YEAR)
        if not xs:
            continue
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle, label=peer.label,
                linewidth=peer.linewidth,
                zorder=5 if peer.iso3 == peers.UK else 3)
        labels.append((ys[-1], f"{peer.label} ({xs[-1]})", peer.colour, xs[-1]))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
    if last_x is not None:
        labelled_ends(ax, labels, min_gap=0.035, x=last_x, fontsize=9.5)

    ax.axhline(1.0, color=TEXT, linewidth=1.2, linestyle="--", alpha=0.7)
    # Right-aligned at the end of the parity line: every series has fallen below 1.00 by the
    # mid-2010s, so that is the one stretch of the line with clear air above it.
    ax.text(max(uk_years), 1.015, "United States = 1.00", fontsize=9.5, color=TEXT,
            style="italic", va="bottom", ha="right", path_effects=white_stroke())

    peak_year = max(uk_years, key=lambda y: uk[y])
    ax.plot([peak_year], [uk[peak_year]], "o", color=ACCENT, markersize=7,
            markeredgecolor="white", markeredgewidth=1.4, zorder=6)

    ax.set_title("How expensive is Britain? Price levels relative to the United States",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"UK prices peaked at {uk[peak_year]:.2f}\u00d7 US levels in {peak_year} "
                  f"and are {uk[uk_years[-1]]:.2f}\u00d7 in {uk_years[-1]} \u2014 the whole difference "
                  "between market-rate and purchasing-power GDP valuations")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.2f}"))
    _tidy(ax, ylabel=meta.unit)

    source_note(fig, _note(
        f"{_WB} \u2014 derived as GDP per capita in current US$ (NY.GDP.PCAP.CD) over GDP "
        f"per capita in current international $ (NY.GDP.PCAP.PP.CD) [{meta.vintage} "
        "benchmark].",
        "Computing it this way cancels local-currency units, so it is unaffected by the "
        "euro changeover. This is a GDP-wide price index, not a consumer cost-of-living "
        "index or a test of currency misvaluation."))
    return save_fig(fig, out_dir / "price_level_index.png", bottom=0.17)


# ── 5. The decomposition ─────────────────────────────────────────────────────
def uk_us_decomposition(rows: list[dict], start_year: int,
                        end_year: int | None = None) -> decompose.Decomposition:
    """Split the change in the UK/US market-FX ratio into a volume part and a price part.

    The real component uses the **constant-price** PPP series, because that is the only one
    whose movement is pure volume growth: it holds parities at the ICP benchmark and moves
    each country by its own real growth rate. The current-price series would be the wrong
    choice here even though it satisfies a tidier identity — its year-to-year movement mixes
    real growth with changes in the PPP price structure, so a bar built from it and labelled
    "real output" would not equal the real output divergence. (On UK/US 2007-2025 the two
    differ by a factor of four: -14.0% of pure volume against -3.4%.)

    The second component is then defined residually as ``R_fx / R_real``, so the split stays
    exact. Its movement reflects relative GDP prices and exchange rates. In one consistent
    vintage, the fixed PPP benchmark scale cancels from growth and from the symmetric split.
    It is not the current-PPP price level index or an identified causal currency effect.
    """
    real = series.ratio(rows, "gdp_per_capita_ppp_constant", peers.UK, peers.US)
    fx = series.ratio(rows, "gdp_per_capita_nominal_usd", peers.UK, peers.US)
    shared = sorted(real.keys() & fx.keys())
    if not shared:
        raise ValueError("no year has both a real and a market-FX UK/US ratio")
    end_year = end_year if end_year is not None else shared[-1]
    for year in (start_year, end_year):
        if year not in shared:
            raise ValueError(f"{year} is not covered by both series (have {shared[0]}-{shared[-1]})")
    return decompose.decompose_ratio_change(
        start_year=start_year, end_year=end_year,
        ppp_ratio_start=real[start_year], ppp_ratio_end=real[end_year],
        # Residual: whatever the market-FX ratio does that real volumes do not explain.
        pli_ratio_start=fx[start_year] / real[start_year],
        pli_ratio_end=fx[end_year] / real[end_year],
    )


def chart_decomposition(rows: list[dict], out_dir: Path,
                        start_year: int = DECOMPOSITION_START_YEAR) -> Path | None:
    """Why the UK fell against the US: the two contributions, in percentage points.

    Deliberately **not** a waterfall. A waterfall would put the endpoint levels (105% and
    64% of the US) and the two changes (-12.6 and -28.8 points) on one axis, so bars drawn
    from zero and bars floating in mid-air would look like the same kind of quantity when
    they are not. This chart plots one quantity only — the contribution to the change, in
    percentage points — and leaves the levels to the subtitle and the endpoint annotation.

    ``start_year`` defaults to 2007, the UK's high-water mark and the baseline the rest of
    the repository measures from. If the fetched range does not reach that far back — the
    ``--start`` flag can move it — the figure is skipped rather than aborting a run whose
    CSVs and manifest have already been written.
    """
    real = series.ratio(rows, "gdp_per_capita_ppp_constant", peers.UK, peers.US)
    nominal = series.ratio(rows, "gdp_per_capita_nominal_usd", peers.UK, peers.US)
    shared = real.keys() & nominal.keys()
    if start_year not in shared or max(shared) <= start_year:
        return None
    d = uk_us_decomposition(rows, start_year)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 5.6))

    # Top to bottom: the big driver, the small one, then the total they sum to.
    bars = [
        ("Relative GDP prices\nand exchange rate", d.price_effect, ACCENT),
        ("Real output\nper head", d.real_effect, BLUE),
        (f"Total change\n{d.start_year}\u2013{d.end_year}", d.total_change, TEXT),
    ]
    ys = [2.0, 1.0, -0.15]  # the total is set slightly apart, below a divider

    for y, (label, value, colour) in zip(ys, bars):
        ax.barh(y, value, height=0.55, color=colour, zorder=3, label=label)
        ax.text(value + (0.7 if value >= 0 else -0.7), y, f"{value:+.1f} points",
                va="center", ha="left" if value >= 0 else "right",
                fontsize=12.5, fontweight="bold", color=colour,
                path_effects=white_stroke())

    ax.axhline(0.45, color=GRID, linewidth=1.0, zorder=2)
    ax.axvline(0, color=TEXT, linewidth=1.2, zorder=4)

    if not math.isclose(d.total_change, 0.0, abs_tol=1e-9):
        share = d.price_effect / d.total_change * 100
        ax.text(d.price_effect + 0.7, ys[0] - 0.42,
                f"{share:.0f}% of the net change", fontsize=10, color=MUTED, style="italic",
                va="top", ha="left", path_effects=white_stroke())

    ax.set_yticks(ys)
    ax.set_yticklabels([label for label, _, _ in bars], fontsize=11, color=TEXT)
    ax.set_ylim(-0.75, 2.6)
    # Leave room to the left of the longest bar for its outside value label, which would
    # otherwise run into the y tick labels.
    values = [0.0, *[value for _, value, _ in bars]]
    padding = max(max(values) - min(values), 5.0) * 0.28
    ax.set_xlim(min(values) - padding, max(values) + padding)

    ax.set_title(f"UK/US GDP-per-head change since {d.start_year}: "
                 "volume growth and non-volume factors", fontweight="bold", pad=30)
    _subtitle(ax, f"UK GDP per head went from {d.start_ratio:.0f}% of the US in "
                  f"{d.start_year} to {d.end_ratio:.0f}% in {d.end_year}. Splitting that "
                  f"{d.total_change:+.0f}-point change into two accounting contributions:")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.set_xlabel("Contribution to the change in UK GDP per capita vs the US "
                  "(percentage points)", labelpad=6)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(y=0)

    source_note(fig, _note(
        f"{_WB} \u2014 NY.GDP.PCAP.CD and NY.GDP.PCAP.PP.KD [{metrics.ICP_VINTAGE} "
        "benchmark]. Symmetric (Shapley) decomposition of UK/US = (real volume ratio) "
        "\u00d7 (residual); the two contributions sum exactly to the total. The real "
        "component uses the constant-price series to measure the divergence in "
        "real output per head.",
        "The residual reflects relative GDP-price changes and exchange rates, not an "
        "identified causal currency contribution. Fixed benchmark scale factors cancel "
        "from this within-vintage accounting split."))
    return save_fig(fig, out_dir / "ppp_gap_decomposition_uk_us.png", bottom=0.20)


# ── 6. The long run, on the Maddison benchmark ───────────────────────────────
def chart_long_run(rows: list[dict], out_dir: Path) -> Path | None:
    """Maddison's long-run PPP series, which reaches back before the World Bank's 1990."""
    metric = "gdp_per_capita_real_maddison"
    meta = metrics.require_over_time(metric)
    plotted = {p.iso3: series.xy(series.series(rows, metric, p.iso3)) for p in peers.PEERS}
    if not any(xs for xs, _ in plotted.values()):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    labels: list[tuple[float, str, str, float]] = []
    last_x = None
    span_years: list[int] = []
    for peer in peers.PEERS:
        xs, ys = plotted[peer.iso3]
        if not xs:
            continue
        span_years += xs
        ys = [y / 1000.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle, label=peer.label,
                linewidth=peer.linewidth, zorder=5 if peer.iso3 == peers.UK else 3)
        labels.append((ys[-1], f"{peer.label} ({xs[-1]})", peer.colour, xs[-1]))
        last_x = xs[-1] if last_x is None else max(last_x, xs[-1])
    labelled_ends(ax, labels, min_gap=max(item[0] for item in labels) * 0.05, x=last_x,
                  fontsize=10)

    # Compare growth on common observed endpoints without assuming a direction or steady trend.
    uk = dict(zip(*plotted[peers.UK])) if plotted[peers.UK][0] else {}
    us = dict(zip(*plotted[peers.US])) if plotted[peers.US][0] else {}
    subtitle_text = ("Benchmarked on Maddison's 2011 prices \u2014 a different vintage from "
                     "the World Bank series, so the two are never spliced")
    shared = sorted(uk.keys() & us.keys())
    # A growth rate needs at least two distinct years; a truncated fetch (or a one-year
    # --start/--end window) falls back to the generic subtitle rather than dividing by zero.
    if len(shared) > 1:
        first, last = shared[0], shared[-1]
        span = last - first
        uk_cagr = ((uk[last] / uk[first]) ** (1 / span) - 1) * 100
        us_cagr = ((us[last] / us[first]) ** (1 / span) - 1) * 100
        subtitle_text = (f"Annualised real growth per head, {first}\u2013{last}: "
                         f"US {us_cagr:.2f}%; UK {uk_cagr:.2f}%")

    ax.set_title(f"Long-run real GDP per person, {_span(span_years)}\n"
                 "Adjusted for purchasing power",
                 fontweight="bold", pad=30)
    _subtitle(ax, subtitle_text)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    _tidy(ax, ylabel=f"GDP per person (000s, {meta.unit})")
    ax.margins(x=0.12)

    source_note(fig, _note(
        "Data: Maddison Project Database 2023 (Bolt & van Zanden), via Our World in Data "
        f"\u2014 {meta.unit}. On the International Comparison Program's 2011 benchmark, "
        "so its levels are not comparable with the World Bank's 2021 benchmark shown "
        "elsewhere in this analysis, and the "
        "spacing between countries should be read as indicative rather than exact. "
        "No comparable EU aggregate is included in this source series; none is synthesised."))
    return save_fig(fig, out_dir / "ppp_gdp_long_run_maddison.png", bottom=0.17)


CHARTS = (
    chart_gdp_per_capita,
    chart_volume_growth,
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
