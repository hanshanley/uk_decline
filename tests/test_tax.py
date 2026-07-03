"""Offline tests for the tax package: SDMX parsing, aggregation, fallback, combine."""

from __future__ import annotations

import json
import os

import pytest

from tax import combine, config, fallback, revenue, stats, taxing_wages

# --- Fixtures: raw OECD SDMX csvfilewithlabels rows (as tax._http.sdmx_csv returns) ---

REV_RAW = [
    {"REF_AREA": "GBR", "TIME_PERIOD": "2022", "OBS_VALUE": "35.16"},
    {"REF_AREA": "USA", "TIME_PERIOD": "2022", "OBS_VALUE": "28.05"},
    {"REF_AREA": "FRA", "TIME_PERIOD": "2022", "OBS_VALUE": "45.86"},
    {"REF_AREA": "DEU", "TIME_PERIOD": "2022", "OBS_VALUE": "38.66"},
    {"REF_AREA": "XXX", "TIME_PERIOD": "2022", "OBS_VALUE": "99.9"},   # unknown -> dropped
    {"REF_AREA": "ITA", "TIME_PERIOD": "2022", "OBS_VALUE": ""},        # blank -> dropped
]

TW_RAW = [
    # single, 100% AW (spouse not applicable) -> kept
    {"REF_AREA": "GBR", "TIME_PERIOD": "2023", "OBS_VALUE": "31.15",
     "HOUSEHOLD_TYPE": "S_C0", "INCOME_PRINCIPAL": "AW100", "INCOME_SPOUSE": "_Z"},
    {"REF_AREA": "FRA", "TIME_PERIOD": "2023", "OBS_VALUE": "46.87",
     "HOUSEHOLD_TYPE": "S_C0", "INCOME_PRINCIPAL": "AW100", "INCOME_SPOUSE": "_Z"},
    # one-earner couple 2 kids, 67% AW, spouse not employed -> kept
    {"REF_AREA": "DEU", "TIME_PERIOD": "2023", "OBS_VALUE": "20.0",
     "HOUSEHOLD_TYPE": "C_C2", "INCOME_PRINCIPAL": "AW67", "INCOME_SPOUSE": "NOEARN_UNEMP"},
    # couple 2 kids but spouse EARNS (two-earner) -> dropped (wrong family type)
    {"REF_AREA": "DEU", "TIME_PERIOD": "2023", "OBS_VALUE": "28.0",
     "HOUSEHOLD_TYPE": "C_C2", "INCOME_PRINCIPAL": "AW67", "INCOME_SPOUSE": "AW67"},
    # unmodelled household -> dropped
    {"REF_AREA": "USA", "TIME_PERIOD": "2023", "OBS_VALUE": "12.3",
     "HOUSEHOLD_TYPE": "S_C2", "INCOME_PRINCIPAL": "AW100", "INCOME_SPOUSE": "_Z"},
    # unknown country -> dropped
    {"REF_AREA": "XXX", "TIME_PERIOD": "2023", "OBS_VALUE": "5.0",
     "HOUSEHOLD_TYPE": "S_C0", "INCOME_PRINCIPAL": "AW100", "INCOME_SPOUSE": "_Z"},
]


# --- make_row ---------------------------------------------------------------

def test_make_row_derives_country_region_and_unit():
    row = combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.16, "src")
    assert row["country"] == "United Kingdom"
    assert row["region"] == config.UK
    assert row["unit"] == "percent"
    assert row["household"] == "" and row["earnings"] == ""


def test_make_row_rejects_unknown_metric():
    with pytest.raises(KeyError):
        combine.make_row("GBR", 2022, "not_a_metric", 1.0, "src")


# --- source parsing (monkeypatched network) ---------------------------------

def test_revenue_parse(monkeypatch):
    monkeypatch.setattr(revenue, "sdmx_csv", lambda *a, **k: REV_RAW)
    rows = revenue.fetch(2022, 2022)
    assert {r["iso3"] for r in rows} == {"GBR", "USA", "FRA", "DEU"}
    assert all(r["metric"] == "tax_to_gdp_pct" for r in rows)
    gbr = next(r for r in rows if r["iso3"] == "GBR")
    assert gbr["value"] == pytest.approx(35.16)
    assert gbr["region"] == config.UK


def test_taxing_wages_parse_filters_variants(monkeypatch):
    # Same fixture returned for each indicator call.
    monkeypatch.setattr(taxing_wages, "sdmx_csv", lambda *a, **k: TW_RAW)
    rows = taxing_wages.fetch(2023, 2023)
    # Dropped: S_C2 (unmodelled), XXX (unknown), and the two-earner couple (wrong
    # spouse). Kept: 3 valid raw rows x 2 indicators = 6.
    assert len(rows) == 6
    variants = {(r["metric"], r["household"], r["earnings"]) for r in rows}
    assert ("tax_wedge_pct", "single_nokids", "100aw") in variants
    assert ("net_personal_avg_tax_rate_pct", "couple2kids_1earner", "67aw") in variants
    assert all(r["household"] in ("single_nokids", "couple2kids_1earner") for r in rows)


def test_taxing_wages_drops_two_earner_couple_rows(monkeypatch):
    # Regression: only the one-earner (spouse NOEARN_UNEMP) couple survives, so no two
    # rows ever share a variant key (previously distinct spouse configs were collapsed).
    monkeypatch.setattr(taxing_wages, "sdmx_csv", lambda *a, **k: TW_RAW)
    rows = taxing_wages.fetch(2023, 2023)
    keys = [(r["iso3"], r["year"], r["metric"], r["household"], r["earnings"]) for r in rows]
    assert len(keys) == len(set(keys))  # every variant is unique -> no silent collapse


# --- stats ------------------------------------------------------------------

def test_summarize_uk_us_europe_median_mean():
    rows = [
        combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "s"),
        combine.make_row("USA", 2022, "tax_to_gdp_pct", 28.0, "s"),
        combine.make_row("FRA", 2022, "tax_to_gdp_pct", 46.0, "s"),
        combine.make_row("DEU", 2022, "tax_to_gdp_pct", 40.0, "s"),
        combine.make_row("ITA", 2022, "tax_to_gdp_pct", 42.0, "s"),
    ]
    (s,) = stats.summarize(rows)
    assert s["uk"] == 35.0 and s["us"] == 28.0
    assert s["europe_n"] == 3
    assert s["europe_median"] == 42.0            # median of 46/40/42
    assert s["europe_mean"] == pytest.approx(42.6667, rel=1e-3)


def test_summarize_picks_latest_year_per_variant():
    rows = [
        combine.make_row("GBR", 2019, "tax_to_gdp_pct", 33.0, "s"),
        combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "s"),
        combine.make_row("FRA", 2022, "tax_to_gdp_pct", 46.0, "s"),
    ]
    (s,) = stats.summarize(rows)
    assert s["year"] == 2022 and s["uk"] == 35.0


def test_summarize_pins_year_with_uk_data_not_global_max():
    # A European country reports a later (2024) vintage than the UK (2022). The summary
    # must pin 2022 so the UK is present, not the ragged 2024 that would blank it.
    rows = [
        combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "s"),
        combine.make_row("USA", 2022, "tax_to_gdp_pct", 28.0, "s"),
        combine.make_row("FRA", 2022, "tax_to_gdp_pct", 46.0, "s"),
        combine.make_row("DEU", 2024, "tax_to_gdp_pct", 39.0, "s"),  # later, UK/US absent
    ]
    (s,) = stats.summarize(rows)
    assert s["year"] == 2022
    assert s["uk"] == 35.0 and s["us"] == 28.0
    assert s["europe_n"] == 1  # only FRA reports 2022 among EUR here


def test_summarize_metrics_label_and_unit_populated():
    rows = [combine.make_row("GBR", 2022, "tax_wedge_pct", 31.0, "s", "single_nokids", "100aw")]
    (s,) = stats.summarize(rows)
    assert s["label"] == config.METRICS["tax_wedge_pct"].label
    assert s["unit"] == "percent"


# --- wide table + combine ---------------------------------------------------

def test_variant_columns_put_macro_first():
    rows = [
        combine.make_row("GBR", 2023, "tax_wedge_pct", 31.0, "s", "single_nokids", "100aw"),
        combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "s"),
    ]
    cols = combine._variant_columns(rows)
    assert cols[0] == "tax_to_gdp_pct"
    assert "tax_wedge_pct__single_nokids__100aw" in cols


def test_combine_writes_long_wide_and_manifest(tmp_path):
    rows = [
        combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "s"),
        combine.make_row("USA", 2022, "tax_to_gdp_pct", 28.0, "s"),
    ]
    written = combine.combine([("tax_revenue_to_gdp", rows)], str(tmp_path))
    for key in ("tax_revenue_to_gdp", "combined_long", "combined_wide", "manifest"):
        assert os.path.exists(written[key])
    manifest = json.loads(open(written["manifest"]).read())
    assert manifest["n_rows"] == 2
    assert "tax_to_gdp_pct" in manifest["metrics"]
    assert manifest["caveats"]["tax_to_gdp_pct"]


# --- fallback ---------------------------------------------------------------

def test_fallback_load_from_repo_csv():
    rows = fallback.load()
    assert rows, "expected curated manual_tax.csv rows"
    assert any(r["iso3"] == "GBR" and r["metric"] == "tax_to_gdp_pct" for r in rows)
    assert all(r["metric"] in config.METRICS for r in rows)


def test_fallback_missing_file_returns_empty(tmp_path):
    assert fallback.load(str(tmp_path / "nope.csv")) == []


# --- source metric ownership + scoped fallback (regression for the HIGH bug) ---

def test_source_modules_declare_owned_metrics():
    assert revenue.METRICS == ("tax_to_gdp_pct",)
    assert set(taxing_wages.METRICS) == {"tax_wedge_pct", "net_personal_avg_tax_rate_pct"}
    # Ownership must partition the metric space with no overlap.
    assert not set(revenue.METRICS) & set(taxing_wages.METRICS)


def test_fetch_tax_scopes_fallback_per_source(tmp_path, monkeypatch):
    """Offline run must not leak one source's metrics into another's per-source CSV."""
    import csv as _csv

    import fetch_tax

    # Force both live fetchers to yield nothing so both fall back.
    monkeypatch.setattr(fetch_tax.revenue, "fetch", lambda *a, **k: [])
    monkeypatch.setattr(fetch_tax.taxing_wages, "fetch", lambda *a, **k: [])
    rc = fetch_tax.main(["--out", str(tmp_path), "--no-charts", "--start", "2022", "--end", "2023"])
    assert rc == 0

    def metrics_in(path):
        with open(path) as fh:
            return {r["metric"] for r in _csv.DictReader(fh)}

    assert metrics_in(tmp_path / "tax_revenue_to_gdp.csv") == {"tax_to_gdp_pct"}
    assert metrics_in(tmp_path / "tax_taxing_wages.csv") == {
        "tax_wedge_pct",
        "net_personal_avg_tax_rate_pct",
    }
    # Combined long must not double-count: one row per country-year-variant.
    with open(tmp_path / "tax_combined_long.csv") as fh:
        keys = [
            (r["iso3"], r["year"], r["metric"], r["household"], r["earnings"])
            for r in _csv.DictReader(fh)
        ]
    assert len(keys) == len(set(keys))


def test_combine_dedupes_overlapping_rows(tmp_path):
    import csv as _csv

    dup = combine.make_row("GBR", 2022, "tax_to_gdp_pct", 35.0, "live")
    same = combine.make_row("GBR", 2022, "tax_to_gdp_pct", 99.0, "fallback")  # same key
    written = combine.combine([("a", [dup]), ("b", [same])], str(tmp_path))
    with open(written["combined_long"]) as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["value"] == "35.0"  # first (live) row wins


# --- charts -----------------------------------------------------------------

def test_charts_render_all_writes_pngs(tmp_path):
    from tax import charts

    rows = []
    for iso3, val in [("GBR", 34.0), ("USA", 26.0), ("FRA", 46.0), ("DEU", 39.0)]:
        rows.append(combine.make_row(iso3, 2022, "tax_to_gdp_pct", val, "s"))
        rows.append(combine.make_row(iso3, 2023, "tax_to_gdp_pct", val + 0.5, "s"))
        for aw in ("67aw", "100aw", "167aw"):
            rows.append(combine.make_row(iso3, 2023, "tax_wedge_pct", val, "s", "single_nokids", aw))
            rows.append(
                combine.make_row(iso3, 2023, "net_personal_avg_tax_rate_pct", val - 5, "s", "single_nokids", aw)
            )
    written = charts.render_all(rows, str(tmp_path))
    assert len(written) == 3
    assert all(os.path.exists(p) and os.path.getsize(p) > 0 for p in written)
