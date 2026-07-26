"""Offline unit tests for the ppp_data pipeline (no network required).

Run directly:  python tests/test_ppp.py
Or with pytest: pytest tests/test_ppp.py -q

These tests cover the arithmetic and the guard rails, not the download. In particular they
pin down the two mistakes that are easiest to make with PPP data and hardest to notice on a
finished chart: plotting an inflation-carrying series as a trend, and mixing currency bases
when deriving the price level index.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ppp_data import (  # noqa: E402
    combine, decompose, figure, metrics, peers, series, validate, worldbank,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────
def _row(iso3: str, year: int, metric: str, value: float, source: str = "test") -> dict:
    return metrics.make_row(iso3, peers.name_for(iso3), year, metric, value, source=source)


def _consistent_rows() -> list[dict]:
    """A tiny, internally consistent dataset spanning the UK, US and Poland.

    Built so that GDPpc(US$) == GDPpc(int'l $) x (PPP factor / FX) exactly, which is what
    the validation checks look for. The US is the numeraire: its PPP factor and exchange
    rate are both 1.0, so its price level index is 1.00.
    """
    spec = {
        # iso3: (ppp factor, fx, gdp at ppp in current int'l $)
        "USA": (1.0, 1.0, 60_000.0),
        "GBR": (0.66, 0.78, 44_000.0),
        "POL": (1.95, 3.98, 44_000.0),
    }
    rows: list[dict] = []
    for iso3, (ppp_factor, fx, gdp_ppp) in spec.items():
        for year in (2007, 2021, 2024):
            pli = ppp_factor / fx
            rows += [
                _row(iso3, year, "ppp_conversion_factor", ppp_factor),
                _row(iso3, year, "market_exchange_rate", fx),
                _row(iso3, year, "gdp_per_capita_ppp_current", gdp_ppp),
                _row(iso3, year, "gdp_per_capita_ppp_constant", gdp_ppp),
                _row(iso3, year, "gdp_per_capita_nominal_usd", gdp_ppp * pli),
            ]
    rows += worldbank.derive_price_level_index(rows)
    rows += worldbank.derive_price_level_index_direct(rows)
    return rows


# ── The metric registry and its guard rails ──────────────────────────────────
def test_current_price_ppp_is_never_a_trend() -> None:
    # Current international dollars carry worldwide inflation, so plotting them as a level
    # over time would show rising prices as rising prosperity.
    assert not metrics.METRICS["gdp_per_capita_ppp_current"].over_time
    assert "gdp_per_capita_ppp_current" not in metrics.TIME_SERIES_SAFE
    assert "gdp_per_capita_ppp_current" in metrics.CROSS_SECTION_SAFE
    try:
        metrics.require_over_time("gdp_per_capita_ppp_current")
    except ValueError as exc:
        assert "cannot be plotted as a level" in str(exc)
    else:
        raise AssertionError("require_over_time must reject a current-price series")


def test_constant_price_ppp_is_never_a_cross_section() -> None:
    # Constant-price PPP is extrapolated from the benchmark with each country's own
    # deflator, so same-year cross-country ratios drift away from the benchmark year.
    assert metrics.METRICS["gdp_per_capita_ppp_constant"].over_time
    assert not metrics.METRICS["gdp_per_capita_ppp_constant"].cross_section
    try:
        metrics.require_cross_section("gdp_per_capita_ppp_constant")
    except ValueError as exc:
        assert "cross-country ratios are unreliable" in str(exc)
    else:
        raise AssertionError("require_cross_section must reject a constant-price series")


def test_every_metric_has_a_unit_vintage_and_caveat() -> None:
    for metric_id, metric in metrics.METRICS.items():
        assert metric.id == metric_id
        assert metric.unit and metric.vintage
        assert metrics.CAVEATS.get(metric_id), f"{metric_id} has no caveat"
        usable = metric.over_time or metric.cross_section or metric.validation_only
        assert usable, f"{metric_id} is usable for nothing"
    # Indicator <-> metric round-trip for the fetched (non-derived) series.
    for indicator, metric_id in metrics.BY_INDICATOR.items():
        assert metrics.METRICS[metric_id].wb_indicator == indicator
    assert metrics.BY_INDICATOR["NY.GDP.PCAP.PP.KD"] == "gdp_per_capita_ppp_constant"
    assert metrics.BY_INDICATOR["PA.NUS.PPP"] == "ppp_conversion_factor"


def test_the_direct_price_level_index_is_validation_only() -> None:
    # It disagrees with the headline index across the euro changeover, so it must be barred
    # from both plotting modes rather than merely left unused.
    assert metrics.VALIDATION_ONLY == {"price_level_index_direct"}
    direct = metrics.METRICS["price_level_index_direct"]
    assert direct.validation_only
    assert not direct.over_time and not direct.cross_section
    assert "price_level_index_direct" not in metrics.TIME_SERIES_SAFE
    assert "price_level_index_direct" not in metrics.CROSS_SECTION_SAFE
    # ...while the headline index is safe for both.
    assert "price_level_index" in metrics.TIME_SERIES_SAFE
    assert "price_level_index" in metrics.CROSS_SECTION_SAFE


def test_icp_vintage_is_named_on_ppp_metrics() -> None:
    # Levels shift retroactively when the World Bank re-benchmarks, so every PPP metric
    # must carry the vintage that the figures then print in their source notes.
    assert metrics.ICP_VINTAGE == "ICP 2021"
    for metric_id in ("gdp_per_capita_ppp_constant", "gdp_per_capita_ppp_current",
                      "ppp_conversion_factor", "price_level_index"):
        assert metrics.METRICS[metric_id].vintage == metrics.ICP_VINTAGE
    # Maddison sits on a different benchmark and must say so.
    assert "2011" in metrics.METRICS["gdp_per_capita_real_maddison"].vintage


def test_make_row_uses_the_registered_unit() -> None:
    row = _row("GBR", 2024, "gdp_per_capita_ppp_constant", 54_000.0)
    assert row["unit"] == "constant 2021 international $"
    assert set(row) == set(combine.LONG_FIELDS)


# ── Deriving the price level index ───────────────────────────────────────────
def test_price_level_index_matches_the_published_uk_figure() -> None:
    # World Bank 2024 for the UK: PA.NUS.PPP = 0.664153, PA.NUS.FCRF = 0.782415.
    pli = decompose.price_level_index(0.664153, 0.782415)
    assert abs(pli - 0.8489) < 1e-3, pli
    # Below 1.00 means cheaper than the US.
    assert pli < 1.0


def test_price_level_index_rejects_a_zero_exchange_rate() -> None:
    try:
        decompose.price_level_index(0.66, 0.0)
    except ValueError as exc:
        assert "zero" in str(exc)
    else:
        raise AssertionError("a zero exchange rate must not silently produce infinity")


def test_both_routes_to_the_price_level_index_agree() -> None:
    rows = _consistent_rows()
    values = series.index(rows)
    for iso3 in ("USA", "GBR", "POL"):
        headline = values[("price_level_index", iso3, 2024)]
        direct = values[("price_level_index_direct", iso3, 2024)]
        assert abs(headline - direct) < 1e-9, (iso3, headline, direct)
    # The US is the numeraire, so its index is exactly 1.00.
    assert values[("price_level_index", "USA", 2024)] == 1.0


def test_derivation_skips_country_years_with_a_missing_input() -> None:
    # One country-year has an exchange rate but no PPP factor; it must be dropped, not
    # filled in from a neighbouring year.
    rows = [
        _row("GBR", 2024, "ppp_conversion_factor", 0.664),
        _row("GBR", 2024, "market_exchange_rate", 0.782),
        _row("GBR", 2023, "market_exchange_rate", 0.805),
    ]
    derived = worldbank.derive_price_level_index_direct(rows)
    assert [r["year"] for r in derived] == [2024]


def test_derivation_skips_a_zero_denominator() -> None:
    rows = [
        _row("GBR", 2024, "ppp_conversion_factor", 0.664),
        _row("GBR", 2024, "market_exchange_rate", 0.0),
    ]
    assert worldbank.derive_price_level_index_direct(rows) == []


# ── The decomposition ────────────────────────────────────────────────────────
def test_decomposition_contributions_sum_to_the_total() -> None:
    d = decompose.decompose_ratio_change(
        start_year=2007, end_year=2024,
        ppp_ratio_start=0.743, ppp_ratio_end=0.729,
        pli_ratio_start=1.419, pli_ratio_end=0.849,
    )
    assert abs((d.real_effect + d.price_effect) - d.total_change) < 1e-9
    assert abs(d.start_ratio - 0.743 * 1.419 * 100) < 1e-9
    assert abs(d.end_ratio - 0.729 * 0.849 * 100) < 1e-9
    # The UK's fall against the US is overwhelmingly a price-level story.
    assert d.price_effect < d.real_effect < 0
    assert abs(d.price_effect) > 10 * abs(d.real_effect)


def test_decomposition_is_symmetric_in_its_two_factors() -> None:
    # Swapping which factor is called "real" and which "price" must swap the two effects
    # exactly — that is what makes the Shapley split free of an ordering choice.
    a = decompose.decompose_ratio_change(
        start_year=2000, end_year=2020,
        ppp_ratio_start=0.8, ppp_ratio_end=0.9, pli_ratio_start=1.2, pli_ratio_end=0.9)
    b = decompose.decompose_ratio_change(
        start_year=2000, end_year=2020,
        ppp_ratio_start=1.2, ppp_ratio_end=0.9, pli_ratio_start=0.8, pli_ratio_end=0.9)
    assert abs(a.real_effect - b.price_effect) < 1e-12
    assert abs(a.price_effect - b.real_effect) < 1e-12


def test_decomposition_log_split_is_additive() -> None:
    d = decompose.decompose_ratio_change(
        start_year=2007, end_year=2024,
        ppp_ratio_start=0.743, ppp_ratio_end=0.729,
        pli_ratio_start=1.419, pli_ratio_end=0.849,
    )
    total_log = math.log((0.729 * 0.849) / (0.743 * 1.419)) * 100.0
    assert abs((d.log_real + d.log_price) - total_log) < 1e-9


def test_decomposition_rejects_non_positive_ratios() -> None:
    try:
        decompose.decompose_ratio_change(
            start_year=2007, end_year=2024, ppp_ratio_start=0.0, ppp_ratio_end=0.7,
            pli_ratio_start=1.4, pli_ratio_end=0.8)
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("a zero ratio must be rejected, not turned into a division error")


# ── Series helpers ───────────────────────────────────────────────────────────
def test_ratio_refuses_an_invalid_cross_section_metric() -> None:
    rows = _consistent_rows()
    try:
        series.ratio(rows, "gdp_per_capita_ppp_constant", "GBR", "USA")
    except ValueError as exc:
        assert "cross-country ratios are unreliable" in str(exc)
    else:
        raise AssertionError("series.ratio must enforce the cross-section guard")
    # ...but allows it when the caller explicitly opts out (validation does this).
    assert series.ratio(rows, "gdp_per_capita_ppp_constant", "GBR", "USA", check=False)


def test_ratio_only_covers_overlapping_years() -> None:
    rows = [
        _row("GBR", 2020, "gdp_per_capita_ppp_current", 44_000.0),
        _row("GBR", 2021, "gdp_per_capita_ppp_current", 46_000.0),
        _row("USA", 2021, "gdp_per_capita_ppp_current", 60_000.0),
    ]
    ratio = series.ratio(rows, "gdp_per_capita_ppp_current", "GBR", "USA")
    assert list(ratio) == [2021]
    assert abs(ratio[2021] - 46_000.0 / 60_000.0) < 1e-12


def test_xy_respects_the_year_window() -> None:
    data = {2000: 1.0, 2010: 2.0, 2020: 3.0}
    assert series.xy(data, 2005, 2015) == ([2010], [2.0])
    assert series.xy(data) == ([2000, 2010, 2020], [1.0, 2.0, 3.0])


# ── Validation ───────────────────────────────────────────────────────────────
def test_all_checks_pass_on_consistent_data() -> None:
    checks = validate.run_all(_consistent_rows())
    names = {c.name for c in checks}
    assert "price_level_agreement" in names and "us_is_numeraire" in names
    for check in checks:
        if check.name in ("coverage", "spot_values", "benchmark_year_agreement"):
            continue  # the fixture is deliberately small; these need the real fetch
        assert check.ok, f"{check.name}: {check.detail}"


def test_inverted_price_level_index_is_caught() -> None:
    # Compute the index upside down (FX / PPP) and confirm the checks notice.
    rows = [r for r in _consistent_rows() if r["metric"] != "price_level_index"]
    values = series.index(rows)
    for iso3 in ("USA", "GBR", "POL"):
        for year in (2007, 2021, 2024):
            inverted = (values[("market_exchange_rate", iso3, year)]
                        / values[("ppp_conversion_factor", iso3, year)])
            rows.append(_row(iso3, year, "price_level_index", inverted))
    failed = {c.name for c in validate.failures(validate.run_all(rows))}
    assert "price_level_agreement" in failed
    assert "relative_price_levels" in failed


def test_misaligned_years_are_caught() -> None:
    # Pair the UK's price level index with the wrong year's value. The direct route still
    # agrees with itself, so only the cross-check between the two routes can catch this.
    rows = _consistent_rows()
    for row in rows:
        if row["metric"] == "price_level_index" and row["iso3"] == "GBR":
            row["value"] *= 1.25
    failed = {c.name for c in validate.failures(validate.run_all(rows))}
    assert "price_level_agreement" in failed


def test_duplicate_rows_are_caught() -> None:
    rows = _consistent_rows()
    rows.append(dict(rows[0]))
    assert not validate.check_no_duplicates(rows).ok


def test_mismatched_units_are_caught() -> None:
    rows = _consistent_rows()
    rows[0] = {**rows[0], "unit": "bananas"}
    check = validate.check_metric_units(rows)
    assert not check.ok and "mismatched unit" in check.detail


def test_unsourced_rows_are_caught() -> None:
    rows = _consistent_rows()
    rows[0] = {**rows[0], "source": ""}
    assert not validate.check_sources_present(rows).ok


def test_implausible_values_are_caught() -> None:
    rows = _consistent_rows()
    # A misplaced decimal point: GDP per capita of $440, not $44,000.
    rows.append(_row("GBR", 1999, "gdp_per_capita_ppp_current", 440.0))
    assert not validate.check_plausible_ranges(rows).ok


def test_currency_basis_breaks_are_documented_not_silent() -> None:
    # The euro changeover is the one place the two routes legitimately disagree. It must be
    # recorded with a reason, and only for years before the changeover.
    assert set(validate.CURRENCY_BASIS_BREAKS) == {"DEU", "FRA", "ITA"}
    for iso3, (year, reason) in validate.CURRENCY_BASIS_BREAKS.items():
        assert year == 1999 and "euro" in reason.lower()
    # A disagreement in a year at or after the changeover is NOT excused.
    rows = _consistent_rows()
    rows += [
        _row("DEU", 2010, "price_level_index", 0.76),
        _row("DEU", 2010, "price_level_index_direct", 0.38),
    ]
    assert not validate.check_price_level_agreement(rows).ok


def test_documented_break_years_are_excused() -> None:
    rows = _consistent_rows()
    rows += [
        _row("ITA", 1995, "price_level_index", 0.92),
        _row("ITA", 1995, "price_level_index_direct", 0.0005),  # lire vs euro
    ]
    check = validate.check_price_level_agreement(rows)
    assert check.ok and "currency changeover" in check.detail


# ── Combine ──────────────────────────────────────────────────────────────────
def test_long_and_wide_round_trip(tmp_path: Path | None = None) -> None:
    import tempfile

    rows = _consistent_rows()
    with tempfile.TemporaryDirectory() as tmp:
        long_path = Path(tmp) / "ppp_long.csv"
        wide_path = Path(tmp) / "ppp_wide.csv"
        combine.write_long(rows, long_path)
        combine.write_wide(rows, wide_path)
        back = combine.load_long(long_path)
        assert len(back) == len(rows)
        assert {(r["metric"], r["iso3"], r["year"]) for r in back} == {
            (r["metric"], r["iso3"], r["year"]) for r in rows
        }
        header = wide_path.read_text().splitlines()[0].split(",")
        assert header[:3] == ["iso3", "country", "year"]
        assert header[3:] == metrics.METRIC_ORDER


def test_wide_column_order_matches_the_registry() -> None:
    assert metrics.METRIC_ORDER == list(metrics.METRICS)
    assert combine.LONG_FIELDS == ["iso3", "country", "year", "metric", "value", "unit",
                                   "source"]


# ── Peers ────────────────────────────────────────────────────────────────────
def test_aggregates_are_excluded_from_conversion_factor_lookups() -> None:
    # The EU has no single currency across the whole period and no single exchange rate, so
    # asking for its price level would be meaningless.
    assert "EUU" in peers.ALL_ISO3
    assert "EUU" not in peers.COUNTRY_ISO3
    assert "EUU" in peers.AGGREGATE_ISO3
    assert set(peers.COUNTRY_ISO3) <= set(peers.ALL_ISO3)
    assert len(peers.ALL_ISO3) == len(set(peers.ALL_ISO3)), "duplicate ISO3 in the peer list"


def test_peer_names_come_from_the_curated_table() -> None:
    assert peers.name_for("GBR") == "United Kingdom"
    assert peers.name_for("USA") == "United States"
    assert peers.UK == "GBR" and peers.US == "USA"


def test_worldbank_fetches_conversion_factors_for_countries_only() -> None:
    assert set(worldbank.CONVERSION_INDICATORS) == {"PA.NUS.PPP", "PA.NUS.FCRF"}
    assert "NY.GDP.PCAP.PP.KD" in worldbank.GDP_INDICATORS
    assert worldbank.PPP_FIRST_YEAR == 1990


# ── Figure helpers ───────────────────────────────────────────────────────────
def test_end_labels_are_pushed_apart_when_they_collide() -> None:
    placed: list[tuple[float, str]] = []

    class _Ax:
        def text(self, x, y, s, **kw):
            placed.append((y, s.strip()))

    figure.labelled_ends(_Ax(), [(100.0, "a", "#000"), (99.5, "b", "#000"),
                                 (50.0, "c", "#000")], min_gap=4.0, x=2024)
    ys = [y for y, _ in placed]
    assert ys[0] == 100.0            # the highest label keeps its true position
    assert abs(ys[1] - 96.0) < 1e-9  # the colliding one is pushed down by min_gap
    assert ys[2] == 50.0             # a well-separated label is untouched


def test_source_notes_are_wrapped() -> None:
    # An unwrapped note sets the width of a tight-cropped figure.
    text = figure.note("word " * 200)
    assert max(len(line) for line in text.splitlines()) <= figure.NOTE_WRAP


def test_span_is_derived_from_the_data() -> None:
    assert figure.span([1990, 2000], [2024]) == "1990\u20132024"
    assert figure.span([]) == ""


# ── Regression guards on the headline (non-PPP) analyses ─────────────────────
def test_headline_gdp_chart_is_still_not_ppp() -> None:
    # The PPP work is strictly additive: the repository's headline measure must remain the
    # market-exchange-rate, CPI-deflated series.
    from europe_data import plot_uk_decline

    assert plot_uk_decline.GDP_METRIC == "gdp_per_capita_real_usd"
    assert "PPP" not in plot_uk_decline.GDP_METRIC.upper()


def test_markets_still_declares_that_it_is_not_ppp() -> None:
    from markets_data import markets

    assert "NOT PPP" in markets.CAVEATS["market_cap_usd_real"]


def test_tuition_still_converts_at_market_rates() -> None:
    from tuition import rates

    assert "PPP conversion was intentionally dropped" in rates.__doc__


def _run() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            t()
            print(f"ok   {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
