"""Offline tests for the age_data package: WB parsing, median derivation, stats, combine."""

from __future__ import annotations

import json
import os

import pytest

from age_data import combine, config, fallback, median_age, pyramids, stats, worldbank


# --- make_row ---------------------------------------------------------------

def test_make_row_derives_country_region_unit():
    row = combine.make_row("GBR", 2024, "pop_share_65plus_pct", 19.5, "s")
    assert row["country"] == "United Kingdom"
    assert row["region"] == config.UK
    assert row["unit"] == "percent"
    assert row["age_band"] == "" and row["sex"] == ""


def test_make_row_us_region():
    assert combine.make_row("USA", 2024, "pop_share_65plus_pct", 17.9, "s")["region"] == config.US


def test_make_row_rejects_unknown_metric():
    with pytest.raises(KeyError):
        combine.make_row("GBR", 2024, "not_a_metric", 1.0, "s")


# --- World Bank parsing (monkeypatched network) -----------------------------

def _wb_payload(rows):
    return [{"pages": 1}, rows]


def test_worldbank_parse(monkeypatch):
    def fake_get_json(url, params=None, timeout=60):
        # Return the same 2-country payload for every indicator call.
        return _wb_payload([
            {"countryiso3code": "GBR", "date": "2024", "value": 19.5},
            {"countryiso3code": "USA", "date": "2024", "value": 17.9},
            {"countryiso3code": "XXX", "date": "2024", "value": 99.0},  # unknown -> dropped
            {"countryiso3code": "FRA", "date": "2024", "value": None},   # null -> dropped
        ])

    monkeypatch.setattr(worldbank, "get_json", fake_get_json)
    rows = worldbank.fetch(2024, 2024, iso3s=["GBR", "USA"])
    assert {r["iso3"] for r in rows} == {"GBR", "USA"}
    # 5 broad indicators x 2 valid countries = 10 rows.
    assert len(rows) == 10
    assert set(worldbank.METRICS) == set(config.BROAD_INDICATORS)


# --- median-age derivation (hand-verified) ----------------------------------

def _band_rows(iso3, year, shares_by_band):
    """Build pop_band_share_pct rows (single sex) from {band_label: percent}."""
    return [
        combine.make_row(iso3, year, "pop_band_share_pct", pct, "s", age_band=band, sex="male")
        for band, pct in shares_by_band.items()
    ]


def test_median_age_first_band():
    # 60% in 0-4 (lower=0), 40% in 5-9. Median crosses in the first band:
    # 0 + ((50 - 0) / 60) * 5 = 4.1667.
    rows = _band_rows("GBR", 2024, {"0-4": 60.0, "5-9": 40.0})
    (m,) = median_age.derive(rows)
    assert m["value"] == pytest.approx(4.17, abs=0.01)
    assert m["metric"] == "median_age_years"
    assert m["source"] == config.SOURCE_WB_DERIVED  # clearly labelled as derived


def test_median_age_mid_distribution():
    # Five equal 20% bands. Cumulative hits 50 inside 10-14 (lower=10):
    # 10 + ((50 - 40) / 20) * 5 = 12.5.
    rows = _band_rows("GBR", 2024,
                      {"0-4": 20.0, "5-9": 20.0, "10-14": 20.0, "15-19": 20.0, "20-24": 20.0})
    (m,) = median_age.derive(rows)
    assert m["value"] == pytest.approx(12.5, abs=0.01)


def test_median_age_sums_over_sex():
    # Two sexes each contribute; derive sums them before computing.
    rows = (
        [combine.make_row("GBR", 2024, "pop_band_share_pct", 30.0, "s", "0-4", "male"),
         combine.make_row("GBR", 2024, "pop_band_share_pct", 30.0, "s", "0-4", "female"),
         combine.make_row("GBR", 2024, "pop_band_share_pct", 20.0, "s", "5-9", "male"),
         combine.make_row("GBR", 2024, "pop_band_share_pct", 20.0, "s", "5-9", "female")]
    )
    (m,) = median_age.derive(rows)
    # 60% in 0-4 -> same as the first-band case: 4.1667.
    assert m["value"] == pytest.approx(4.17, abs=0.01)


# --- pyramids share computation ---------------------------------------------

def test_pyramid_rows_from_counts_sum_to_100():
    counts = {
        ("GBR", 2024, band, sex): 100.0
        for _code, band, _mid in config.AGE_BANDS
        for sex in config.SEXES.values()
    }
    rows = pyramids.rows_from_counts(counts)
    assert sum(r["value"] for r in rows) == pytest.approx(100.0)
    assert all(r["metric"] == "pop_band_share_pct" for r in rows)


def test_pyramid_rows_drop_incomplete_profiles():
    counts = {
        ("GBR", 2024, "0-4", "male"): 100.0,
        ("GBR", 2024, "0-4", "female"): 100.0,
    }
    assert pyramids.rows_from_counts(counts) == []


# --- stats ------------------------------------------------------------------

def test_summarize_uk_us_europe():
    rows = [
        combine.make_row("GBR", 2024, "pop_share_65plus_pct", 19.5, "s"),
        combine.make_row("USA", 2024, "pop_share_65plus_pct", 17.9, "s"),
        combine.make_row("FRA", 2024, "pop_share_65plus_pct", 22.0, "s"),
        combine.make_row("DEU", 2024, "pop_share_65plus_pct", 23.0, "s"),
        combine.make_row("ITA", 2024, "pop_share_65plus_pct", 24.0, "s"),
    ]
    (s,) = stats.summarize(rows)
    assert s["uk"] == 19.5 and s["us"] == 17.9
    assert s["europe_median"] == 23.0 and s["europe_n"] == 3


def test_summarize_pins_year_with_uk_data():
    rows = [
        combine.make_row("GBR", 2020, "median_age_years", 40.0, "s"),
        combine.make_row("FRA", 2024, "median_age_years", 43.0, "s"),  # later, UK absent
    ]
    (s,) = stats.summarize(rows)
    assert s["year"] == 2020 and s["uk"] == 40.0


# --- combine + manifest citations -------------------------------------------

def test_combine_writes_files_and_citations(tmp_path):
    rows = [
        combine.make_row("GBR", 2024, "pop_share_65plus_pct", 19.5, "s"),
        combine.make_row("USA", 2024, "pop_share_65plus_pct", 17.9, "s"),
    ]
    written = combine.combine([("age_structure", rows)], str(tmp_path))
    for key in ("age_structure", "combined_long", "combined_wide", "manifest"):
        assert os.path.exists(written[key])
    manifest = json.loads(open(written["manifest"]).read())
    assert manifest["n_rows"] == 2
    # Proper bibliographic citations must be present.
    assert "un_wpp" in manifest["citations"]
    assert "World Population Prospects" in manifest["citations"]["un_wpp"]
    assert "World Bank" in manifest["citations"]["world_bank_wdi"]


def test_combine_dedupes(tmp_path):
    import csv as _csv
    a = combine.make_row("GBR", 2024, "pop_share_65plus_pct", 19.5, "live")
    b = combine.make_row("GBR", 2024, "pop_share_65plus_pct", 99.0, "fallback")
    written = combine.combine([("x", [a]), ("y", [b])], str(tmp_path))
    with open(written["combined_long"]) as fh:
        got = list(_csv.DictReader(fh))
    assert len(got) == 1 and got[0]["value"] == "19.5"


# --- fallback ---------------------------------------------------------------

def test_fallback_loads_snapshot():
    rows = fallback.load()
    assert rows, "expected the curated manual_age.csv snapshot"
    assert all(r["metric"] in config.METRICS for r in rows)
    assert any(r["iso3"] == "GBR" and r["metric"] == "pop_share_65plus_pct" for r in rows)


def test_fallback_missing_file(tmp_path):
    assert fallback.load(str(tmp_path / "nope.csv")) == []


# --- charts -----------------------------------------------------------------

def test_charts_render(tmp_path):
    from age_data import charts

    rows = []
    for iso3 in ("GBR", "USA", "FRA", "DEU"):
        for y in (1960, 2024):
            rows.append(combine.make_row(iso3, y, "pop_share_0_14_pct", 20.0, "s"))
            rows.append(combine.make_row(iso3, y, "pop_share_15_64_pct", 63.0, "s"))
            rows.append(combine.make_row(iso3, y, "pop_share_65plus_pct", 17.0, "s"))
            rows.append(combine.make_row(iso3, y, "median_age_years", 38.0 + (y - 1960) * 0.1, "d"))
    # UK pyramid bands for two years.
    for y in (1960, 2024):
        for band in config.BAND_ORDER:
            for sex in ("male", "female"):
                rows.append(combine.make_row("GBR", y, "pop_band_share_pct", 100.0 / (2 * len(config.BAND_ORDER)), "s", band, sex))
    written = charts.render_all(rows, str(tmp_path))
    assert len(written) == 4
    assert all(os.path.exists(p) and os.path.getsize(p) > 0 for p in written)
