"""Sanity checks on the fetched PPP data, run before anything is charted.

PPP data is unusually easy to get quietly wrong: the numeraire can be misidentified, a
conversion factor can be paired with the wrong year's exchange rate, benchmark vintages can
be mixed, and a plausible-looking number can be off by a factor of two without anything
raising. These checks make those failures loud.

The strongest check is :func:`check_price_level_agreement`. The price level index can be
built two ways from four *independent* World Bank series:

    GDPpc(current US$) / GDPpc(current int'l $)      and      PPP factor / market FX

Both are algebraically the same quantity, so reproducing one from the other confirms, end to
end, that the right series were pulled, aligned on the right years, and divided the right
way round. It is a real cross-check, not a tautology — and it is what caught the euro
changeover problem recorded in :data:`CURRENCY_BASIS_BREAKS`.

Checks are classified ``error`` (the pipeline must stop) or ``warn`` (worth surfacing, but
expected to drift as the World Bank revises its estimates).
"""

from __future__ import annotations

from collections import Counter
from typing import Callable, Iterable, NamedTuple

from . import metrics, peers, series

ERROR = "error"
WARN = "warn"

# The two routes to the price level index agree to rounding in the published data; anything
# worse than this means the series are misaligned rather than merely rounded.
IDENTITY_TOLERANCE = 0.005  # 0.5%

# Known, documented breaks where the World Bank does NOT quote PA.NUS.PPP and PA.NUS.FCRF in
# the same currency, so the direct route to the price level index is invalid.
#
# When a country adopts the euro, the World Bank restates its PPP conversion factor in euro
# for the whole back-series, but leaves the exchange rate in the legacy national currency for
# the pre-changeover years. Dividing one by the other then understates the price level by the
# legacy conversion rate — for Italy, by a factor of nearly 2,000. The headline
# ``price_level_index`` is immune because it is built from the two GDP-per-capita series,
# whose local-currency GDP cancels; this table records where the *cross-check* is expected to
# disagree, so a disagreement anywhere else is treated as a genuine failure.
CURRENCY_BASIS_BREAKS: dict[str, tuple[int, str]] = {
    "DEU": (1999, "Deutsche Mark replaced by the euro on 1 January 1999"),
    "FRA": (1999, "French franc replaced by the euro on 1 January 1999"),
    "ITA": (1999, "Italian lira replaced by the euro on 1 January 1999"),
}

# In the ICP benchmark year the constant- and current-price PPP ratios are anchored to the
# same underlying parities, so they should very nearly agree.
BENCHMARK_YEAR = 2021
BENCHMARK_TOLERANCE = 0.02  # 2%

# Plausibility envelopes. Deliberately wide: they catch order-of-magnitude and
# wrong-series errors, not small revisions.
GDP_PPP_RANGE = (500.0, 250_000.0)      # international $ per capita
PRICE_LEVEL_RANGE = (0.2, 2.5)          # relative to the US

# Loose expectation bands for a few well-known published values, used to notice if an
# upstream revision or an indicator change has moved the data a long way. These are WARN
# level by design: the World Bank revises, and a revision is not a bug.
SPOT_CHECKS: dict[tuple[str, str, int], tuple[float, float]] = {
    ("gdp_per_capita_ppp_constant", "GBR", 2024): (45_000, 62_000),
    ("gdp_per_capita_ppp_constant", "USA", 2024): (65_000, 88_000),
    ("ppp_conversion_factor", "GBR", 2024): (0.55, 0.80),
    ("market_exchange_rate", "GBR", 2024): (0.70, 0.90),
    ("price_level_index", "GBR", 2024): (0.70, 1.00),
}


class Check(NamedTuple):
    name: str
    ok: bool
    level: str
    detail: str


def check_us_is_numeraire(rows: list[dict]) -> Check:
    """The US defines the international dollar, so its price level index must be 1.00."""
    pli = series.series(rows, "price_level_index", "USA")
    if not pli:
        return Check("us_is_numeraire", False, ERROR,
                     "no price level index rows for the United States")
    worst_year, worst = max(pli.items(), key=lambda kv: abs(kv[1] - 1.0))
    ok = abs(worst - 1.0) < 1e-6
    return Check(
        "us_is_numeraire", ok, ERROR,
        f"US price level index over {len(pli)} years; furthest from 1.00 is "
        f"{worst:.9f} in {worst_year}"
        + ("" if ok else " — the US is not being treated as the numeraire"),
    )


def check_price_level_agreement(rows: list[dict]) -> Check:
    """The two independent routes to the price level index must agree.

    Disagreement is tolerated only for country-years listed in
    :data:`CURRENCY_BASIS_BREAKS`, where the World Bank quotes the PPP conversion factor and
    the exchange rate in different currencies. A disagreement anywhere else means the wrong
    series were pulled or the years are misaligned.
    """
    values = series.index(rows)
    checked = 0
    unexplained: list[str] = []
    explained = 0
    worst = (0.0, "", 0)
    for (metric, iso3, year), headline in values.items():
        if metric != "price_level_index":
            continue
        direct = values.get(("price_level_index_direct", iso3, year))
        if direct is None or headline == 0:
            continue
        checked += 1
        error = abs(direct - headline) / abs(headline)
        if error <= IDENTITY_TOLERANCE:
            worst = max(worst, (error, iso3, year))
            continue
        break_year = CURRENCY_BASIS_BREAKS.get(iso3, (None, ""))[0]
        if break_year is not None and year < break_year:
            explained += 1
        else:
            unexplained.append(f"{iso3} {year} ({error:.1%})")

    if not checked:
        return Check("price_level_agreement", False, ERROR,
                     "no country-year had both routes to the price level index")
    detail = (
        f"checked {checked} country-years; worst agreeing error {worst[0]:.2%} "
        f"({worst[1]} {worst[2]}); {explained} disagreement(s) explained by a documented "
        "currency changeover"
    )
    if unexplained:
        detail += f"; {len(unexplained)} UNEXPLAINED: " + ", ".join(unexplained[:5])
    return Check("price_level_agreement", not unexplained, ERROR, detail)


def check_benchmark_year_agreement(rows: list[dict]) -> Check:
    """Constant- and current-price PPP ratios should agree in the ICP benchmark year."""
    current = series.ratio(rows, "gdp_per_capita_ppp_current", peers.UK, peers.US)
    constant = series.ratio(rows, "gdp_per_capita_ppp_constant", peers.UK, peers.US,
                            check=False)
    if BENCHMARK_YEAR not in current or BENCHMARK_YEAR not in constant:
        return Check("benchmark_year_agreement", False, WARN,
                     f"no UK/US PPP ratio available for the {BENCHMARK_YEAR} benchmark year")
    a, b = current[BENCHMARK_YEAR], constant[BENCHMARK_YEAR]
    gap = abs(a - b) / a
    return Check(
        "benchmark_year_agreement", gap <= BENCHMARK_TOLERANCE, ERROR,
        f"UK/US PPP ratio in {BENCHMARK_YEAR}: {a:.4f} (current prices) vs {b:.4f} "
        f"(constant {BENCHMARK_YEAR} prices), differing by {gap:.2%}",
    )


def check_plausible_ranges(rows: list[dict]) -> Check:
    """Catch order-of-magnitude errors: wrong indicator, wrong units, misplaced decimal."""
    bad: list[str] = []
    envelopes = {
        "gdp_per_capita_ppp_constant": GDP_PPP_RANGE,
        "gdp_per_capita_ppp_current": GDP_PPP_RANGE,
        "price_level_index": PRICE_LEVEL_RANGE,
    }
    for row in rows:
        envelope = envelopes.get(row["metric"])
        if envelope and not (envelope[0] <= row["value"] <= envelope[1]):
            bad.append(f"{row['metric']} {row['iso3']} {row['year']} = {row['value']:,.4g}")
    return Check(
        "plausible_ranges", not bad, ERROR,
        "all values inside their plausibility envelopes" if not bad
        else f"{len(bad)} value(s) outside range, e.g. " + "; ".join(bad[:5]),
    )


def check_relative_price_levels(rows: list[dict]) -> Check:
    """Poland must be cheaper than the UK, and the UK cheaper than the United States today.

    Two directional checks that would fail immediately if the price level index were
    accidentally inverted (market FX divided by the PPP factor rather than the reverse).
    A missing index is an ERROR, not a warning: the charts need it, and a WARN here would
    let the run proceed to crash in :func:`ppp_data.charts.chart_price_level_index`.
    """
    latest: dict[str, tuple[int, float]] = {}
    for iso3 in ("GBR", "POL"):
        pli = series.series(rows, "price_level_index", iso3)
        if pli:
            year = max(pli)
            latest[iso3] = (year, pli[year])
    missing = {"GBR", "POL"} - set(latest)
    if missing:
        return Check("relative_price_levels", False, ERROR,
                     f"no price level index for {sorted(missing)}")
    (uk_year, uk), (pl_year, pl) = latest["GBR"], latest["POL"]
    cheaper_than_uk = pl < uk
    uk_below_us = uk < 1.0  # the US is the numeraire at 1.00; the UK is below it today
    ok = cheaper_than_uk and uk_below_us
    detail = (f"price level index: Poland {pl:.2f} ({pl_year}) vs the UK {uk:.2f} "
              f"({uk_year}), against the US at 1.00")
    if not cheaper_than_uk:
        detail += " — Poland should be the cheaper country; the index may be inverted"
    if not uk_below_us:
        detail += " — the UK is above US price levels, which last held before 2015"
    return Check("relative_price_levels", ok, ERROR, detail)


def check_ppp_beats_market_fx_for_poland(rows: list[dict]) -> Check:
    """Poland must look richer relative to the UK at PPP than at market rates.

    This is the substantive reason the PPP view exists, so if it does not hold the two
    conversion bases have almost certainly been swapped somewhere.
    """
    ppp = series.ratio(rows, "gdp_per_capita_ppp_current", "POL", "GBR")
    fx = series.ratio(rows, "gdp_per_capita_nominal_usd", "POL", "GBR")
    shared = sorted(ppp.keys() & fx.keys())
    if not shared:
        return Check("ppp_beats_market_fx_for_poland", False, WARN,
                     "no overlapping years for the Poland/UK comparison")
    year = shared[-1]
    ok = ppp[year] > fx[year]
    return Check(
        "ppp_beats_market_fx_for_poland", ok, ERROR,
        f"Poland as a share of the UK in {year}: {ppp[year]:.1%} at PPP vs "
        f"{fx[year]:.1%} at market rates"
        + ("" if ok else " — PPP should raise a lower-price country, not lower it"),
    )


def check_no_duplicates(rows: list[dict]) -> Check:
    """One observation per metric, country, and year — no double-counting on re-fetch."""
    counts = Counter((r["metric"], r["iso3"], r["year"]) for r in rows)
    dupes = [key for key, n in counts.items() if n > 1]
    return Check(
        "no_duplicates", not dupes, ERROR,
        f"{len(rows)} rows, all unique" if not dupes
        else f"{len(dupes)} duplicated key(s), e.g. {dupes[:3]}",
    )


def check_coverage(rows: list[dict]) -> Check:
    """Every plotted country must actually have the constant-price PPP series."""
    have = {
        r["iso3"] for r in rows if r["metric"] == "gdp_per_capita_ppp_constant"
    }
    missing = [iso3 for iso3 in peers.ALL_ISO3 if iso3 not in have]
    years = [r["year"] for r in rows if r["metric"] == "gdp_per_capita_ppp_constant"]
    span = f"{min(years)}-{max(years)}" if years else "none"
    return Check(
        "coverage", not missing, ERROR,
        f"PPP GDP per capita covers {len(have)} entities over {span}" if not missing
        else f"no PPP GDP per capita for {missing}",
    )


def check_spot_values(rows: list[dict]) -> Check:
    """Compare a few well-known values against loose published expectation bands."""
    values = series.index(rows)
    out_of_band: list[str] = []
    missing: list[str] = []
    for (metric, iso3, year), (low, high) in SPOT_CHECKS.items():
        value = values.get((metric, iso3, year))
        if value is None:
            missing.append(f"{metric} {iso3} {year}")
        elif not (low <= value <= high):
            out_of_band.append(f"{metric} {iso3} {year} = {value:,.4g} (expected {low:,g}-{high:,g})")
    detail_parts = []
    if out_of_band:
        detail_parts.append("outside expected band: " + "; ".join(out_of_band))
    if missing:
        detail_parts.append("not available: " + "; ".join(missing))
    return Check(
        "spot_values", not out_of_band, WARN,
        "; ".join(detail_parts) if detail_parts
        else f"all {len(SPOT_CHECKS)} spot values within their expected bands",
    )


def check_metric_units(rows: list[dict]) -> Check:
    """Every row's unit label must match its metric's registered unit.

    Cheap, but it is the check that would catch a constant-price series being written out
    under a current-price label — the kind of mix-up that is invisible on a finished chart.
    """
    wrong = [
        f"{r['metric']} {r['iso3']} {r['year']}: {r['unit']!r}"
        for r in rows
        if r["metric"] in metrics.METRICS
        and r["unit"] != metrics.METRICS[r["metric"]].unit
    ]
    unknown = sorted({r["metric"] for r in rows if r["metric"] not in metrics.METRICS})
    detail = "every row's unit matches its metric registry entry"
    if wrong:
        detail = f"{len(wrong)} row(s) with a mismatched unit, e.g. " + "; ".join(wrong[:3])
    if unknown:
        detail += f"; unregistered metric(s): {unknown}"
    return Check("metric_units", not wrong and not unknown, ERROR, detail)


def check_sources_present(rows: list[dict]) -> Check:
    """Every row must name where it came from — the repository fabricates nothing."""
    unsourced = [r for r in rows if not str(r.get("source", "")).strip()]
    sources = sorted({r["source"] for r in rows if r.get("source")})
    return Check(
        "sources_present", not unsourced, ERROR,
        f"{len(sources)} distinct source(s): {'; '.join(sources)}" if not unsourced
        else f"{len(unsourced)} row(s) with no source attribution",
    )


CHECKS: tuple[Callable[[list[dict]], Check], ...] = (
    check_no_duplicates,
    check_coverage,
    check_sources_present,
    check_us_is_numeraire,
    check_price_level_agreement,
    check_benchmark_year_agreement,
    check_plausible_ranges,
    check_relative_price_levels,
    check_ppp_beats_market_fx_for_poland,
    check_metric_units,
    check_spot_values,
)


def run_all(rows: Iterable[dict]) -> list[Check]:
    """Run every check against the fetched rows."""
    rows = list(rows)
    return [check(rows) for check in CHECKS]


def report(checks: Iterable[Check]) -> str:
    """Render the checks as a readable block, one line each."""
    lines = []
    for check in checks:
        mark = "PASS" if check.ok else ("WARN" if check.level == WARN else "FAIL")
        lines.append(f"  [{mark}] {check.name}: {check.detail}")
    return "\n".join(lines)


def failures(checks: Iterable[Check]) -> list[Check]:
    """Checks that failed at ``error`` level — these must stop the pipeline."""
    return [c for c in checks if not c.ok and c.level == ERROR]
