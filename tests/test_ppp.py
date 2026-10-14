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

import pytest

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
                _row(iso3, year, "gdp_per_capita_constant_usd", gdp_ppp * 0.8),
                _row(iso3, year, "gdp_per_capita_nominal_usd", gdp_ppp * pli),
            ]
    rows += worldbank.derive_price_level_index(rows)
    rows += worldbank.derive_price_level_index_direct(rows)
    return rows


# ── The metric registry and its guard rails ──────────────────────────────────
def test_current_price_ppp_is_never_a_trend() -> None:
    # Current international dollars carry price changes, so plotting them as a real trend
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


def test_constant_price_ppp_can_compare_benchmark_valued_volumes() -> None:
    assert metrics.METRICS["gdp_per_capita_ppp_constant"].over_time
    metrics.require_cross_section("gdp_per_capita_ppp_constant")
    rows = _consistent_rows()
    for row in rows:
        if row["iso3"] == "GBR" and row["year"] == 2024:
            if row["metric"] == "gdp_per_capita_ppp_constant":
                row["value"] *= 0.8
    volume = series.ratio(rows, "gdp_per_capita_ppp_constant", "GBR", "USA")
    repriced = series.ratio(rows, "gdp_per_capita_ppp_current", "GBR", "USA")
    assert volume[2024] / volume[2007] == pytest.approx(0.8)
    assert repriced[2024] / repriced[2007] == pytest.approx(1)


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
    pli = decompose.price_level_index_direct(0.664153, 0.782415)
    assert abs(pli - 0.8489) < 1e-3, pli
    # Below 1.00 means cheaper than the US.
    assert pli < 1.0


def test_price_level_index_rejects_a_zero_exchange_rate() -> None:
    try:
        decompose.price_level_index_direct(0.66, 0.0)
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
        series.ratio(rows, "price_level_index_direct", "GBR", "USA")
    except ValueError as exc:
        assert "not registered for cross-country level ratios" in str(exc)
    else:
        raise AssertionError("series.ratio must enforce the cross-section guard")
    assert series.ratio(rows, "gdp_per_capita_ppp_constant", "GBR", "USA")


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
    assert "price_level_identity" in failed


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


def test_charts_skip_rather_than_crash_on_empty_input() -> None:
    # A partial fetch must not crash the run or publish a blank figure: every chart returns
    # None so `make_charts` simply omits it.
    import tempfile

    from ppp_data import charts

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for chart in charts.CHARTS:
            assert chart([], out) is None, f"{chart.__name__} did not skip empty input"
        assert list(out.glob("*.png")) == [], "a blank figure was written for empty input"


def test_decomposition_chart_skips_an_uncovered_start_year() -> None:
    # `--start 2010` must not abort the run after the CSVs are already written.
    import tempfile

    from ppp_data import charts

    rows = _consistent_rows()  # covers 2007, 2021, 2024
    with tempfile.TemporaryDirectory() as tmp:
        assert charts.chart_decomposition(rows, Path(tmp), start_year=1995) is None
    assert charts.DECOMPOSITION_START_YEAR == 2007


def test_missing_price_level_index_fails_the_error_gate() -> None:
    # Previously this returned WARN, so `failures()` was empty, the run proceeded, and the
    # price-level chart then crashed. It must stop the pipeline instead.
    rows = [r for r in _consistent_rows() if r["metric"] != "price_level_index"]
    failed = {c.name for c in validate.failures(validate.run_all(rows))}
    assert "relative_price_levels" in failed


def test_uk_above_us_price_levels_is_caught() -> None:
    # An inversion that keeps Poland below the UK would slip past the Poland check alone.
    rows = _consistent_rows()
    for row in rows:
        if row["metric"] == "price_level_index" and row["iso3"] in ("GBR", "POL"):
            row["value"] *= 2.0
    check = validate.check_relative_price_levels(rows)
    assert not check.ok and check.level == validate.WARN
    assert "price ordering changed" in check.detail


def test_worldbank_paging_is_bounded() -> None:
    # The page count comes from the remote payload, so it must not be able to drive an
    # unbounded loop.
    assert worldbank.MAX_PAGES > 0
    calls = {"n": 0}

    def _hostile(url, params=None, timeout=60):
        calls["n"] += 1
        return [{"pages": 10**9}, [{"countryiso3code": "GBR", "date": "2020", "value": 1.0}]]

    import ppp_data.worldbank as wb

    original = wb.get_json
    wb.get_json = _hostile
    try:
        rows = list(wb._fetch_indicator("PA.NUS.PPP", ["GBR"], 2020, 2020))
    finally:
        wb.get_json = original
    assert calls["n"] == worldbank.MAX_PAGES
    assert len(rows) == worldbank.MAX_PAGES


def test_worldbank_paging_stops_on_a_malformed_page_count() -> None:
    def _malformed(url, params=None, timeout=60):
        return [{"pages": "not-a-number"},
                [{"countryiso3code": "GBR", "date": "2020", "value": 1.0}]]

    import ppp_data.worldbank as wb

    original = wb.get_json
    wb.get_json = _malformed
    try:
        rows = list(wb._fetch_indicator("PA.NUS.PPP", ["GBR"], 2020, 2020))
    finally:
        wb.get_json = original
    assert len(rows) == 1  # the one good page, then a clean stop
    assert set(worldbank.CONVERSION_INDICATORS) == {"PA.NUS.PPP", "PA.NUS.FCRF"}
    assert "NY.GDP.PCAP.PP.KD" in worldbank.GDP_INDICATORS
    assert worldbank.PPP_FIRST_YEAR == 1990


# ── Figure helpers ───────────────────────────────────────────────────────────
def test_end_labels_are_pushed_apart_when_they_collide() -> None:
    placed: list[tuple[float, str]] = []
    connectors = []

    class _Ax:
        def text(self, x, y, s, **kw):
            placed.append((y, s.strip()))

        def annotate(self, text, *, xy, xytext, **kw):
            connectors.append((xy, xytext))

    figure.labelled_ends(_Ax(), [(100.0, "a", "#000"), (99.5, "b", "#000"),
                                 (50.0, "c", "#000")], min_gap=4.0, x=2024)
    ys = [y for y, _ in placed]
    assert ys[0] == 100.0            # the highest label keeps its true position
    assert abs(ys[1] - 96.0) < 1e-9  # the colliding one is pushed down by min_gap
    assert ys[2] == 50.0             # a well-separated label is untouched
    assert connectors == [((2024, 99.5), (2024.4, 96.0))]


def test_source_notes_are_wrapped() -> None:
    # An unwrapped note sets the width of a tight-cropped figure.
    text = figure.note("word " * 200)
    assert max(len(line) for line in text.splitlines()) <= figure.NOTE_WRAP
    assert figure.note("ICP 2021 benchmark") == (
        "International Comparison Program 2021 benchmark"
    )


def test_span_is_derived_from_the_data() -> None:
    assert figure.span([1990, 2000], [2024]) == "1990\u20132024"
    assert figure.span([]) == ""


# ── Regression guards on the headline (non-PPP) analyses ─────────────────────
def test_headline_gdp_chart_is_still_not_ppp() -> None:
    # The PPP work is strictly additive: the repository's headline measure must remain the
    # market-exchange-rate, CPI-deflated series.
    from europe_data import plot_uk_decline

    assert plot_uk_decline.GDP_METRIC == "gdp_per_capita_constant_usd"
    assert "PPP" not in plot_uk_decline.GDP_METRIC.upper()


def test_markets_still_declares_that_it_is_not_ppp() -> None:
    from markets_data import markets

    assert "NOT PPP" in markets.CAVEATS["market_cap_usd_real"]


def test_tuition_still_converts_at_market_rates() -> None:
    from tuition import rates

    assert "PPP conversion was intentionally dropped" in rates.__doc__


# ── Tuition ──────────────────────────────────────────────────────────────────
def test_tuition_market_fx_column_follows_the_base_year() -> None:
    # The column name must be derived from tuition.config.REAL_BASE_YEAR, not hard-coded,
    # so the PPP twin cannot silently sit on a different base from its market-FX pair.
    from ppp_data import tuition_ppp
    from tuition import config as tuition_config

    assert tuition_ppp.BASE_YEAR == tuition_config.REAL_BASE_YEAR
    assert tuition_ppp.MARKET_FX_COLUMN == f"real_{tuition_ppp.BASE_YEAR}_usd"


def test_tuition_history_missing_base_column_is_a_clear_error() -> None:
    import tempfile
    from ppp_data import tuition_ppp

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.csv"
        path.write_text("country,iso3,region,year,nominal_local,currency,real_1999_usd\n"
                        "United Kingdom,GBR,UK,2020,9250,GBP,1\n")
        try:
            tuition_ppp.load_history(path)
        except RuntimeError as exc:
            assert "REAL_BASE_YEAR" in str(exc)
        else:
            raise AssertionError("a mismatched base-year column must be rejected loudly")


def test_tuition_share_subtitle_uses_a_shared_year() -> None:
    # The UK fee series runs ahead of the US one, so quoting each at its own last point
    # would compare different years while saying "now".
    from ppp_data import tuition_ppp

    text = tuition_ppp._share_subtitle([2020, 2022, 2024], [10.0, 20.0, 30.0],
                                       [2020, 2022], [5.0, 6.0])
    assert "In 2022" in text and "20.0%" in text and "6.0%" in text
    assert "30.0%" not in text, "the UK's unmatched 2024 point must not be compared to 2022"


def test_tuition_share_plots_germany_as_reference_points_not_continuous_history(
    monkeypatch, tmp_path
):
    from ppp_data import tuition_ppp
    from vizstyle import ACCENT, BLUE
    import matplotlib.pyplot as plt

    points = [
        tuition_ppp.TuitionPoint(country, iso3, region, year, 0, "EUR", 0, 0, share)
        for country, iso3, region, year, share in [
            ("United Kingdom", "GBR", "UK", 2021, 25),
            ("United Kingdom", "GBR", "UK", 2022, 24),
            ("Germany", "DEU", "EU", 1990, 0),
            ("Germany", "DEU", "EU", 2022, 0),
        ]
    ]
    figures = []
    monkeypatch.setattr(tuition_ppp, "save_fig", lambda fig, *a, **k: figures.append(fig))
    tuition_ppp.chart_tuition_share(points, tmp_path)
    fig = figures[0]
    try:
        ax = fig.axes[0]
        german = [line for line in ax.lines if line.get_color() == BLUE]
        assert len(german) == 1
        assert german[0].get_linestyle() == "None"
        assert list(german[0].get_xdata()) == [1990, 2022]
        uk = next(line for line in ax.lines if line.get_color() == ACCENT)
        assert uk.get_drawstyle() == "default"
        assert any("selected zero-fee reference years" in t.get_text() for t in ax.texts)
        assert any("2006\u20132014" in t.get_text() for t in fig.texts)
    finally:
        plt.close(fig)


def test_tuition_fee_schedule_expands_only_the_nominal_cap() -> None:
    from ppp_data import tuition_ppp

    history = [
        {
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2012", "nominal_local": "9000", "currency": "GBP",
            tuition_ppp.MARKET_FX_COLUMN: "1",
        },
        {
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2017", "nominal_local": "9250", "currency": "GBP",
            tuition_ppp.MARKET_FX_COLUMN: "1",
        },
    ]
    expanded = tuition_ppp.expand_uk_fee_schedule(
        history, {2012, 2013, 2014, 2015, 2016, 2017, 2018}
    )
    by_year = {int(row["year"]): float(row["nominal_local"]) for row in expanded}
    assert by_year == {
        2012: 9000, 2013: 9000, 2014: 9000, 2015: 9000, 2016: 9000,
        2017: 9250, 2018: 9250,
    }


def test_frozen_nominal_cap_still_changes_in_real_converted_terms() -> None:
    from ppp_data import tuition_ppp

    history = [{
        "country": "United Kingdom", "iso3": "GBR", "region": "UK",
        "year": "2017", "nominal_local": "9250", "currency": "GBP",
        tuition_ppp.MARKET_FX_COLUMN: "0",
    }]
    rows = []
    for year, ppp_factor, fx in ((2017, 0.50, 0.80), (2018, 0.55, 0.75)):
        # Keep the World Bank identity internally consistent:
        # local GDP = PPP factor * GDP(PPP); GDP(USD) = local GDP / FX.
        gdp_ppp = 100_000.0
        gdp_usd = ppp_factor * gdp_ppp / fx
        rows.extend([
            _row("GBR", year, "ppp_conversion_factor", ppp_factor),
            _row("GBR", year, "gdp_per_capita_ppp_current", gdp_ppp),
            _row("GBR", year, "gdp_per_capita_nominal_usd", gdp_usd),
            _row("GBR", year, "market_exchange_rate", fx),
        ])
    points = tuition_ppp.build(
        rows,
        history=history,
        cpi={2017: 90.0, 2018: 100.0, tuition_ppp.BASE_YEAR: 120.0},
    )
    assert [point.year for point in points] == [2017, 2018]
    assert points[0].nominal_local == points[1].nominal_local == 9250
    assert points[0].real_base_usd != points[1].real_base_usd
    assert points[0].real_base_intl != points[1].real_base_intl


def test_tuition_share_keeps_years_beyond_cpi_coverage() -> None:
    from ppp_data import tuition_ppp

    history = [{
        "country": "United Kingdom", "iso3": "GBR", "region": "UK",
        "year": "2017", "nominal_local": "9250", "currency": "GBP",
        tuition_ppp.MARKET_FX_COLUMN: "0",
    }]
    rows = []
    for year in (2017, 2018):
        ppp_factor, fx, gdp_ppp = 0.5, 0.8, 100_000.0
        rows.extend([
            _row("GBR", year, "ppp_conversion_factor", ppp_factor),
            _row("GBR", year, "gdp_per_capita_ppp_current", gdp_ppp),
            _row("GBR", year, "gdp_per_capita_nominal_usd", ppp_factor * gdp_ppp / fx),
            _row("GBR", year, "market_exchange_rate", fx),
        ])
    points = tuition_ppp.build(
        rows,
        history=history,
        cpi={2017: 90.0, tuition_ppp.BASE_YEAR: 120.0},
    )
    assert [point.year for point in points] == [2017, 2018]
    assert points[1].share_of_gdp_pc_pct > 0
    assert points[1].real_base_usd is None
    assert points[1].real_base_intl is None


def test_tuition_default_deflator_matches_saved_market_history_not_gdp_rows():
    import pytest
    from ppp_data import tuition_ppp
    from tuition import build_dataset
    from tuition.cpi import load_cpi

    history = [{
        "country": "United States", "iso3": "USA", "region": "US",
        "year": "2025", "nominal_local": "11950", "currency": "USD",
    }]
    rows = [
        _row("USA", 2025, "ppp_conversion_factor", 1),
        _row("USA", 2025, "market_exchange_rate", 1),
        _row("USA", 2025, "gdp_per_capita_ppp_current", 90000),
        _row("USA", 2025, "gdp_per_capita_nominal_usd", 90000),
    ]
    point, = tuition_ppp.build(rows, history=history)
    cpi = load_cpi(2022, 2025)
    expected = 11950 * cpi[2022] / cpi[2025]
    assert point.real_base_usd == point.real_base_intl
    assert point.real_base_usd == pytest.approx(expected)
    assert build_dataset._us_cpi_deflator({2025})[2025] == cpi[2022] / cpi[2025]
    assert point.share_of_gdp_pc_pct == 11950 / 90000 * 100


def test_tuition_cpi_is_recovered_from_the_rows_for_offline_recharting() -> None:
    # `--from-csv` is documented as offline, so the deflator must come from the CSV rather
    # than a live World Bank call. The CPI is the *US* CPI, so it must be read from the US
    # rows specifically -- see the regression test below.
    from ppp_data import tuition_ppp

    rows = []
    for year, cpi in ((2015, 80.0), (2022, 100.0)):
        nominal = 50_000.0
        rows.append(_row("USA", year, "gdp_per_capita_nominal_usd", nominal))
        rows.append(_row("USA", year, "gdp_per_capita_real_usd", nominal * (100.0 / cpi)))
    recovered = tuition_ppp.us_cpi_from_rows(rows)
    assert abs(recovered[2015] - 80.0) < 1e-9
    assert abs(recovered[2022] - 100.0) < 1e-9


def test_tuition_cpi_does_not_depend_on_row_order() -> None:
    # Regression: the recovered CPI is `nominal / real`, which is only the deflator ratio when
    # both values come from the SAME country. Keying by year alone let whichever country
    # sorted last win each metric independently, so a change in sort order upstream silently
    # produced a CPI that was wrong by ~29%.
    import random

    from ppp_data import tuition_ppp

    rows = []
    for iso3, scale in (("USA", 1.0), ("GBR", 0.7), ("POL", 0.4)):
        for year, cpi in ((2015, 80.0), (2022, 100.0)):
            nominal = 50_000.0 * scale
            rows.append(_row(iso3, year, "gdp_per_capita_nominal_usd", nominal))
            rows.append(_row(iso3, year, "gdp_per_capita_real_usd", nominal * (100.0 / cpi)))

    expected = {2015: 80.0, 2022: 100.0}
    for seed in range(12):
        shuffled = random.Random(seed).sample(rows, len(rows))
        recovered = tuition_ppp.us_cpi_from_rows(shuffled)
        for year, want in expected.items():
            assert abs(recovered[year] - want) < 1e-9, f"seed {seed}, year {year}"


# ── Observed coverage is not survey certification ───────────────────────────
def test_headline_requires_overlapping_volume_and_nominal_observations(monkeypatch) -> None:
    rows = _consistent_rows()
    assert validate.check_headline_year_coverage(rows).ok
    rows = [r for r in rows if not (r["iso3"] == "USA" and r["year"] == 2007
                                   and r["metric"] == "gdp_per_capita_ppp_constant")]
    assert not validate.check_headline_year_coverage(rows).ok
    monkeypatch.setattr(validate, "DECOMPOSITION_BASELINE_YEAR", 1992)
    check = validate.check_headline_year_coverage(_consistent_rows())
    assert not check.ok and "not covered" in check.detail
    assert check.level == validate.ERROR


def test_extrapolated_years_are_reported_not_hidden() -> None:
    rows = _consistent_rows() + [
        _row("GBR", 1992, "gdp_per_capita_ppp_current", 30_000.0),
    ]
    check = validate.check_ppp_estimate_provenance(rows)
    assert check.ok and check.level == validate.WARN
    assert "1992" in check.detail and "extrapolated" in check.detail
    assert "cannot certify" in check.detail
    assert "survey-backed" not in check.detail


def test_decomposition_real_component_equals_real_divergence() -> None:
    """The bar labelled "real output" must equal the actual real-output divergence.

    The real component must come from the constant-price (volume) series. Building it from the
    current-price PPP ratio, whose movement mixes volume growth with shifts in the PPP price
    structure, understates the real divergence roughly four-fold.
    """
    import math

    from ppp_data import charts

    rows = _consistent_rows()
    # Give the UK a real-volume path that diverges from the US, and a price path that does
    # not, so a decomposition reading the wrong series would visibly under-report.
    for row in rows:
        if row["iso3"] == "GBR" and row["year"] == 2024:
            if row["metric"] == "gdp_per_capita_ppp_constant":
                row["value"] *= 0.80          # 20% real underperformance
            elif row["metric"] == "gdp_per_capita_nominal_usd":
                row["value"] *= 0.80

    uk = series.series(rows, "gdp_per_capita_ppp_constant", "GBR")
    us = series.series(rows, "gdp_per_capita_ppp_constant", "USA")
    expected = ((uk[2024] / uk[2007]) / (us[2024] / us[2007]) - 1) * 100

    d = charts.uk_us_decomposition(rows, 2007, 2024)
    implied = (math.exp(d.log_real / 100) - 1) * 100
    assert abs(implied - expected) < 0.05, (implied, expected)
    assert abs(expected + 20.0) < 0.05, "fixture should show a 20% real divergence"


def test_volume_growth_check_uses_independent_national_accounts() -> None:
    rows = _consistent_rows()
    for row in rows:
        if row["iso3"] == "GBR":
            if row["metric"] == "gdp_per_capita_ppp_constant":
                row["value"] = {2007: 40_000, 2021: 44_000, 2024: 48_000}[row["year"]]
            elif row["metric"] == "gdp_per_capita_constant_usd":
                row["value"] = {2007: 25_000, 2021: 27_500, 2024: 30_000}[row["year"]]
    assert validate.check_constant_ppp_growth(rows).ok
    for row in rows:
        if (row["iso3"], row["year"], row["metric"]) == (
                "GBR", 2024, "gdp_per_capita_constant_usd"):
            row["value"] *= 1.02
    check = validate.check_constant_ppp_growth(rows)
    assert not check.ok and "GBR" in check.detail
    assert check.level == validate.ERROR


def test_volume_growth_check_rejects_missing_reference_series() -> None:
    rows = [r for r in _consistent_rows() if r["metric"] != "gdp_per_capita_constant_usd"]
    check = validate.check_constant_ppp_growth(rows)
    assert not check.ok and "re-fetch" in check.detail


def test_growth_chart_plots_country_growth_not_levels_or_current_prices(monkeypatch, tmp_path):
    from ppp_data import charts

    rows = [
        _row("GBR", 2007, "gdp_per_capita_ppp_constant", 40_000),
        _row("GBR", 2025, "gdp_per_capita_ppp_constant", 44_000),
        _row("USA", 2007, "gdp_per_capita_ppp_constant", 80_000),
        _row("USA", 2025, "gdp_per_capita_ppp_constant", 100_000),
        _row("GBR", 2025, "gdp_per_capita_ppp_current", 70_000),
        _row("POL", 2025, "gdp_per_capita_ppp_constant", 50_000),
    ]
    captured = []
    def save(fig, path, **kwargs):
        captured.append(fig)
        charts._plt().close(fig)
        return path
    monkeypatch.setattr(charts, "save_fig", save)
    assert charts.chart_volume_growth(rows, tmp_path).name == "ppp_gdp_per_capita_growth.png"
    ax = captured[0].axes[0]
    assert list(ax.lines[0].get_ydata()) == pytest.approx([100, 110])
    assert list(ax.lines[1].get_ydata()) == pytest.approx([100, 125])
    # Poland has no baseline, so it cannot silently get a different one.
    assert not any("Poland" in t.get_text() for t in ax.texts)
    rows.append(_row("POL", 2007, "gdp_per_capita_ppp_constant", 25_000))
    charts.chart_volume_growth(rows, tmp_path)
    ax = captured[-1].axes[0]
    assert list(ax.lines[2].get_ydata()) == pytest.approx([100, 200])
    assert any("Poland (2025)" in t.get_text() for t in ax.texts)


@pytest.mark.parametrize("chart_name", [
    "chart_gdp_per_capita", "chart_price_level_index", "chart_ppp_vs_market_fx",
    "chart_volume_growth", "chart_relative_to_peers", "chart_long_run",
])
def test_gdp_source_footers_do_not_overlap_year_label(monkeypatch, tmp_path, chart_name):
    from ppp_data import charts
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    captured = []
    original_save = charts.save_fig

    def save(fig, path, **kwargs):
        captured.append(fig)
        return original_save(fig, path, **kwargs)

    monkeypatch.setattr(charts, "save_fig", save)
    rows = _consistent_rows() + [
        _row(iso3, year, "gdp_per_capita_real_maddison", value)
        for iso3, value in (("GBR", 40_000), ("USA", 60_000))
        for year in (2007, 2024)
    ]
    getattr(charts, chart_name)(rows, tmp_path)
    fig = captured[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    footer_top = max(text.get_window_extent(renderer).y1 for text in fig.texts)
    xlabel_bottom = fig.axes[0].xaxis.label.get_window_extent(renderer).y0
    assert footer_top < xlabel_bottom


def test_decomposition_is_invariant_to_fixed_benchmark_rescaling() -> None:
    from ppp_data import charts

    rows = _consistent_rows()
    for row in rows:
        if row["iso3"] == "GBR" and row["year"] == 2024:
            if row["metric"] == "gdp_per_capita_ppp_constant":
                row["value"] *= 0.8
            elif row["metric"] == "gdp_per_capita_nominal_usd":
                row["value"] *= 0.6
    before = charts.uk_us_decomposition(rows, 2007)
    for row in rows:
        if row["iso3"] == "GBR" and row["metric"] == "gdp_per_capita_ppp_constant":
            row["value"] *= 1.7
    after = charts.uk_us_decomposition(rows, 2007)
    for field in ("real_effect", "price_effect", "total_change", "log_real", "log_price"):
        assert getattr(after, field) == pytest.approx(getattr(before, field))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.0])
def test_decomposition_rejects_invalid_volume_inputs(bad):
    with pytest.raises(ValueError, match="positive and finite"):
        decompose.decompose_ratio_change(
            start_year=2007, end_year=2025, ppp_ratio_start=bad, ppp_ratio_end=0.7,
            pli_ratio_start=1.4, pli_ratio_end=0.8)


@pytest.mark.parametrize("end_year", [2007, 2000])
def test_decomposition_rejects_nonchronological_endpoints(end_year):
    with pytest.raises(ValueError, match="later"):
        decompose.decompose_ratio_change(
            start_year=2007, end_year=end_year, ppp_ratio_start=0.8, ppp_ratio_end=0.7,
            pli_ratio_start=1.4, pli_ratio_end=0.8)


@pytest.mark.parametrize("nominal_growth,volume_growth", [(1.2, 1.1), (1.0, 1.2), (0.8, 1.2)])
def test_decomposition_chart_handles_positive_mixed_and_zero_changes(
        monkeypatch, tmp_path, nominal_growth, volume_growth):
    from ppp_data import charts

    rows = _consistent_rows()
    for row in rows:
        if row["iso3"] == "GBR" and row["year"] == 2024:
            if row["metric"] == "gdp_per_capita_nominal_usd":
                row["value"] *= nominal_growth
            elif row["metric"] == "gdp_per_capita_ppp_constant":
                row["value"] *= volume_growth
    captured = []
    def save(fig, path, **kwargs):
        captured.append(fig)
        charts._plt().close(fig)
        return path
    monkeypatch.setattr(charts, "save_fig", save)
    charts.chart_decomposition(rows, tmp_path)
    ax = captured[0].axes[0]
    lo, hi = ax.get_xlim()
    assert all(lo < bar.get_width() < hi for bar in ax.patches)
    text = " ".join(t.get_text() for t in ax.texts)
    assert "change" in text and "fall" not in text
    if nominal_growth == 1:
        assert "% of the net change" not in text


def test_historical_price_ordering_is_not_a_publication_invariant():
    rows = _consistent_rows()
    for row in rows:
        if row["iso3"] == "GBR" and row["metric"] == "price_level_index":
            row["value"] = 1.2
    check = validate.check_relative_price_levels(rows)
    assert not check.ok and check.level == validate.WARN
    assert not validate.failures([check])


def test_price_ordering_compares_the_latest_shared_year():
    rows = _consistent_rows() + [_row("POL", 2025, "price_level_index", 1.8)]
    check = validate.check_relative_price_levels(rows)
    assert check.ok and "2024" in check.detail and "2025" not in check.detail
def test_validation_catches_a_non_volume_real_component() -> None:
    # The guard must fire if the decomposition is ever pointed back at a non-volume series.
    # The fixture needs a genuine real divergence, otherwise understating it is undetectable.
    rows = _consistent_rows()
    for row in rows:
        if (row["iso3"] == "GBR" and row["year"] == 2024
                and row["metric"] in ("gdp_per_capita_ppp_constant",
                                      "gdp_per_capita_nominal_usd")):
            row["value"] *= 0.80  # a 20% real underperformance against the US

    from ppp_data import charts

    original = charts.uk_us_decomposition
    baseline = validate.DECOMPOSITION_BASELINE_YEAR
    validate.DECOMPOSITION_BASELINE_YEAR = 2007
    try:
        assert validate.check_decomposition_real_component_is_volume(rows).ok

        def _wrong(rows_, start_year, end_year=None):
            d = original(rows_, start_year, end_year)
            return d._replace(log_real=d.log_real / 4.0)  # the old, understated split

        charts.uk_us_decomposition = _wrong
        check = validate.check_decomposition_real_component_is_volume(rows)
    finally:
        charts.uk_us_decomposition = original
        validate.DECOMPOSITION_BASELINE_YEAR = baseline
    assert not check.ok and check.level == validate.ERROR
    assert "not measuring real volume" in check.detail


def test_charts_do_not_reference_the_removed_shading_helper() -> None:
    # The pre-survey caveat lives in the README and the validation output rather than as
    # shading on the plots; this asserts the helper stays gone.
    from ppp_data import charts

    assert not hasattr(charts, "_mark_extrapolated_era")


# ── Robustness of the validation gate itself ─────────────────────────────────
def test_validation_reports_rather_than_crashes_on_a_partial_fetch() -> None:
    # Regression: the WDI routinely publishes the constant-price volume series a year ahead of
    # the market-FX series. `uk_us_decomposition` raises ValueError in that case, and the
    # exception used to escape `run_all`, turning the stage whose job is to REPORT failures
    # into an unhandled traceback that `--skip-validation` could not bypass.
    from ppp_data import validate

    rows = _consistent_rows()
    baseline = validate.DECOMPOSITION_BASELINE_YEAR
    validate.DECOMPOSITION_BASELINE_YEAR = 2007
    try:
        trimmed = [r for r in rows
                   if not (r["metric"] == "gdp_per_capita_nominal_usd" and r["year"] == 2024)]
        check = validate.check_decomposition_real_component_is_volume(trimmed)
    finally:
        validate.DECOMPOSITION_BASELINE_YEAR = baseline
    assert not check.ok
    assert "cannot decompose" in check.detail


def test_price_level_identity_catches_a_year_misalignment() -> None:
    # The identity GDPpc(US$) = GDPpc(int'l $) x PLI is true by construction at derivation
    # time, so this guards the emitted dataset: shifting one series by a single year was
    # previously undetected by every other check.
    from ppp_data import validate

    rows = [
        _row("GBR", 2020, "gdp_per_capita_nominal_usd", 40_000.0),
        _row("GBR", 2020, "gdp_per_capita_ppp_current", 50_000.0),
        _row("GBR", 2020, "price_level_index", 0.8),
    ]
    assert validate.check_price_level_identity(rows).ok

    broken = [dict(r) for r in rows]
    broken[0]["value"] = 45_000.0  # as if the market-FX row came from the wrong year
    check = validate.check_price_level_identity(broken)
    assert not check.ok and check.level == validate.ERROR
    assert "misaligned" in check.detail


def test_price_level_agreement_requires_real_coverage() -> None:
    # Regression: the check previously failed only when ZERO country-years carried both
    # routes, so a truncated conversion-factor fetch could cross-check a single country-year,
    # report PASS, and silently drop countries from the figures.
    from ppp_data import validate

    rows = []
    for year in range(2000, 2020):
        rows.append(_row("GBR", year, "price_level_index", 0.9))
    rows.append(_row("GBR", 2000, "price_level_index_direct", 0.9))
    check = validate.check_price_level_agreement(rows)
    assert not check.ok and check.level == validate.ERROR
    assert "incomplete" in check.detail


def test_long_run_chart_survives_a_degenerate_year_window() -> None:
    # Regression: the CAGR subtitle divided by (last - first) without guarding a single-year
    # or empty overlap, raising ZeroDivisionError/ValueError AFTER the CSVs had been written.
    import tempfile

    from ppp_data import charts, metrics

    unit = metrics.METRICS["gdp_per_capita_real_maddison"].unit

    def _m(iso3, year, value):
        return {"metric": "gdp_per_capita_real_maddison", "iso3": iso3, "country": iso3,
                "year": year, "value": value, "unit": unit, "source": "Maddison"}

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        single = [_m("GBR", 2020, 40_000.0), _m("USA", 2020, 55_000.0)]
        assert charts.chart_long_run(single, out) is not None

        disjoint = [_m("GBR", 2019, 40_000.0), _m("USA", 2021, 55_000.0)]
        assert charts.chart_long_run(disjoint, out) is not None


def test_decomposition_baseline_year_has_one_source_of_truth() -> None:
    # The figure is drawn from charts.DECOMPOSITION_START_YEAR while the validation gate
    # checks validate.DECOMPOSITION_BASELINE_YEAR; a drift would check the wrong coverage.
    from ppp_data import charts, metrics, validate

    assert (charts.DECOMPOSITION_START_YEAR
            == validate.DECOMPOSITION_BASELINE_YEAR
            == metrics.DECOMPOSITION_BASELINE_YEAR)


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
