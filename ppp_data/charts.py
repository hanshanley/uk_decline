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

from vizstyle import (
    ACCENT, BLUE, GRID, MUTED, TEXT, end_label, house_style, save_fig, source_note,
    white_stroke,
)

from . import decompose, metrics, peers, series
from .paths import CHART_DIR

# World Bank PPP coverage begins in 1990; the market-FX comparator is trimmed to match so
# the two bases are always compared over identical years.
START_YEAR = 1990

_WB = "Data: World Bank Group, World Development Indicators"
_FRAMING = (
    "Market exchange rates measure what UK output buys on world markets; PPP measures what "
    "it buys at home. Neither is the truer number \u2014 they answer different questions."
)


def _plt():
    """Return the themed pyplot, with the house rcParams applied once."""
    import matplotlib.pyplot as plt

    house_style()
    return plt


def _note(*parts: str) -> str:
    return "  ".join(p for p in parts if p)


def _subtitle(ax, text: str) -> None:
    """The centred, muted one-liner that carries each figure's key fact."""
    ax.text(0.5, 1.015, text, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=11.5, color=MUTED)


def _tidy(ax, *, xlabel: str = "Year", ylabel: str = "") -> None:
    ax.set_xlabel(xlabel, labelpad=2)
    ax.set_ylabel(ylabel, labelpad=2)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", pad=2)
    ax.margins(x=0.04)


# ── 1. Levels at PPP ─────────────────────────────────────────────────────────
def chart_gdp_per_capita(rows: list[dict], out_dir: Path) -> Path:
    """UK vs peers, real GDP per capita at PPP, constant 2021 international $."""
    metric = "gdp_per_capita_ppp_constant"
    meta = metrics.require_over_time(metric)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))

    uk_latest = None
    for peer in peers.PEERS:
        xs, ys = series.xy(series.series(rows, metric, peer.iso3), START_YEAR)
        if not xs:
            continue
        ys = [y / 1000.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth, label=peer.label,
                marker="o" if peer.iso3 == peers.UK else None, markersize=4.5,
                markeredgecolor="white", markeredgewidth=1.0,
                zorder=5 if peer.iso3 == peers.UK else 3)
        if peer.iso3 == peers.UK:
            uk_latest = (xs[-1], ys[-1])

    ax.set_title("Real GDP per capita at purchasing power parity, 1990\u20132024",
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
def chart_relative_to_peers(rows: list[dict], out_dir: Path) -> Path:
    """Each peer's GDP per capita as a percentage of the UK's, at PPP (UK = 100)."""
    metric = "gdp_per_capita_ppp_current"
    meta = metrics.require_cross_section(metric)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    facts: list[str] = []
    for peer in peers.RELATIVE_PEERS:
        ratios = series.ratio(rows, metric, peer.iso3, peers.UK)
        xs, ys = series.xy(ratios, START_YEAR)
        if not xs:
            continue
        ys = [y * 100.0 for y in ys]
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth)
        end_label(ax, xs[-1], ys[-1], peer.label, peer.colour)
        if peer.iso3 == "POL":
            facts.append(f"Poland climbed from {ys[0]:.0f}% of the UK to {ys[-1]:.0f}%")
        elif peer.iso3 == "USA":
            facts.append(f"the US stands at {ys[-1]:.0f}%")

    ax.axhline(100, color=ACCENT, linewidth=1.4)
    ax.text(ax.get_xlim()[0], 101.5, "United Kingdom = 100", fontsize=9.5, color=ACCENT,
            style="italic", fontweight="bold", va="bottom")

    ax.set_title("GDP per capita relative to the UK at PPP, 1990\u20132024",
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
def chart_ppp_vs_market_fx(rows: list[dict], out_dir: Path) -> Path:
    """The UK as a share of the US, at market exchange rates and at PPP."""
    fx_metric, ppp_metric = "gdp_per_capita_nominal_usd", "gdp_per_capita_ppp_current"
    metrics.require_cross_section(fx_metric)
    metrics.require_cross_section(ppp_metric)
    plt = _plt()

    fx = series.ratio(rows, fx_metric, peers.UK, peers.US)
    ppp = series.ratio(rows, ppp_metric, peers.UK, peers.US)
    years = [y for y in sorted(fx.keys() & ppp.keys()) if y >= START_YEAR]
    fx_pct = [fx[y] * 100 for y in years]
    ppp_pct = [ppp[y] * 100 for y in years]

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.fill_between(years, fx_pct, ppp_pct, color=MUTED, alpha=0.14, zorder=1)
    ax.plot(years, fx_pct, color=ACCENT, linewidth=2.8, zorder=4)
    ax.plot(years, ppp_pct, color=BLUE, linewidth=2.8, zorder=4)
    end_label(ax, years[-1], fx_pct[-1], "at market\nexchange rates", ACCENT, fontsize=9.5)
    end_label(ax, years[-1], ppp_pct[-1], "at PPP", BLUE, fontsize=9.5)

    peak_year = max(years, key=lambda y: fx[y])
    ax.plot([peak_year], [fx[peak_year] * 100], "o", color=ACCENT, markersize=7,
            markeredgecolor="white", markeredgewidth=1.4, zorder=6)
    ax.annotate(
        f"{peak_year}: sterling peak\n{fx[peak_year]*100:.0f}% of the US at market rates,\n"
        f"but only {ppp[peak_year]*100:.0f}% at PPP",
        xy=(peak_year, fx[peak_year] * 100), xytext=(peak_year - 13, fx[peak_year] * 100 + 4),
        fontsize=9.5, color=TEXT, path_effects=white_stroke(),
        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.9})

    mid = (fx_pct[-1] + ppp_pct[-1]) / 2
    ax.annotate("the gap is the\nexchange rate", xy=(years[-1] - 2, mid), fontsize=9.5,
                color=MUTED, style="italic", ha="right", va="center",
                path_effects=white_stroke())

    ax.set_title("How much of the UK's fall against the US is real?",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"At market rates the UK fell from {fx[peak_year]*100:.0f}% of the US in "
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
def chart_price_level_index(rows: list[dict], out_dir: Path) -> Path:
    """Each country's price level relative to the United States (US = 1.00)."""
    metric = "price_level_index"
    meta = metrics.require_over_time(metric)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 6.5))

    uk = series.series(rows, metric, peers.UK)
    for peer in peers.PRICE_LEVEL_PEERS:
        xs, ys = series.xy(series.series(rows, metric, peer.iso3), START_YEAR)
        if not xs:
            continue
        ax.plot(xs, ys, color=peer.colour, linestyle=peer.linestyle,
                linewidth=peer.linewidth,
                zorder=5 if peer.iso3 == peers.UK else 3)
        end_label(ax, xs[-1], ys[-1], peer.label, peer.colour, fontsize=9.5)

    ax.axhline(1.0, color=TEXT, linewidth=1.2, linestyle="--", alpha=0.7)
    ax.text(ax.get_xlim()[0], 1.012, "United States = 1.00", fontsize=9.5, color=TEXT,
            style="italic", va="bottom")

    uk_years = series.years_between(uk, START_YEAR)
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
                        start_year: int = 2007) -> Path:
    """A waterfall splitting the UK's fall against the US into real and currency parts."""
    d = uk_us_decomposition(rows, start_year)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 6))

    def colour(value: float) -> str:
        return ACCENT if value < 0 else BLUE

    labels = [f"{d.start_year}", "Real output\nper head", "Price level /\nexchange rate",
              f"{d.end_year}"]
    # Endpoint bars sit on the axis; the two effect bars float between them, each starting
    # where the previous step left off.
    steps = [d.start_ratio, d.start_ratio + d.real_effect, d.end_ratio]
    bars = [(0.0, d.start_ratio, TEXT)]
    for effect, level in zip((d.real_effect, d.price_effect), steps):
        bars.append((level + min(effect, 0.0), abs(effect), colour(effect)))
    bars.append((0.0, d.end_ratio, TEXT))

    for i, (bottom, height, col) in enumerate(bars):
        ax.bar(i, height, bottom=bottom, color=col, width=0.6, zorder=3)

    for i, value in enumerate((d.start_ratio, d.real_effect, d.price_effect, d.end_ratio)):
        bottom, height, _ = bars[i]
        text = f"{value:+.1f} pp" if i in (1, 2) else f"{value:.1f}%"
        ax.text(i, bottom + height + 1.2, text, ha="center", va="bottom",
                fontsize=11.5, fontweight="bold", color=TEXT, path_effects=white_stroke())

    # Dashed connectors carrying each step's closing level across to the next bar.
    for i, level in enumerate(steps):
        ax.plot([i + 0.3, i + 1.3], [level, level], color=GRID, linewidth=1.0,
                linestyle="--", zorder=2)

    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=10.5, color=TEXT)
    ax.set_title(f"Almost none of the UK's fall against the US since {d.start_year} "
                 "is lost output", fontweight="bold", pad=30)
    _subtitle(ax, f"Of the {abs(d.total_change):.0f}-point fall from {d.start_ratio:.0f}% to "
                  f"{d.end_ratio:.0f}% of US GDP per head, {abs(d.price_effect):.0f} points "
                  f"come from the exchange rate and price levels, and {abs(d.real_effect):.0f} "
                  "from real output")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, xlabel="", ylabel="UK GDP per capita as % of the US")
    ax.set_ylim(0, max(d.start_ratio, d.end_ratio) * 1.22)

    source_note(fig, _note(
        f"{_WB} \u2014 NY.GDP.PCAP.CD, NY.GDP.PCAP.PP.CD [{metrics.ICP_VINTAGE} benchmark]. "
        "Symmetric (Shapley) decomposition of UK/US = (real ratio) \u00d7 (relative price "
        "level); the two contributions sum exactly to the total.",
        "A weaker pound does make imports dearer, so this is not a clean bill of health "
        "\u2014 it relocates the story from lost output to lost purchasing power abroad."))
    return save_fig(fig, out_dir / "ppp_gap_decomposition_uk_us.png")


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
