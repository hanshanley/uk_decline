"""Unit tests for the tuition analysis pipeline.

Run from the repository root:
    .venv/bin/python -m pytest tests/ -v
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tuition import build_dataset
from tuition import plot_tuition
from tuition import config, dataset, rates
from tuition.stats import aggregate_by_region, average, median


# --- stats ------------------------------------------------------------------
def test_average_and_median_basic():
    assert average([0, 10, 20]) == 10
    assert median([0, 10, 20]) == 10
    assert median([0, 0, 0, 8]) == 0  # zeros are real data points


def test_average_median_empty():
    assert average([]) is None
    assert median([]) is None


def test_aggregate_by_region_counts_and_4yr():
    rows = [
        {"region": "EU", "v": 0.0},
        {"region": "EU", "v": 100.0},
        {"region": "EU", "v": None},   # skipped
        {"region": "UK", "v": 9250.0},
    ]
    agg = aggregate_by_region(rows, "v", degree_years=4)
    assert agg["EU"]["n"] == 2
    assert agg["EU"]["mean_annual"] == 50.0
    assert agg["EU"]["median_annual"] == 50.0
    assert agg["UK"]["n"] == 1
    assert agg["UK"]["mean_4yr"] == 9250.0 * 4


# --- config / region tagging ------------------------------------------------
def test_eu27_membership():
    assert len(config.EU27) == 27
    assert all(c.region == config.EU for c in config.EU27)
    assert config.UK_COUNTRY.region == config.UK
    assert config.US_COUNTRY.region == config.US


def test_currency_mapping_examples():
    by_iso3 = config.BY_ISO3
    assert by_iso3["DEU"].currency == "EUR"
    assert by_iso3["GBR"].currency == "GBP"
    assert by_iso3["BGR"].currency == "BGN"
    assert by_iso3["USA"].currency == "USD"


# --- currency conversion (build_dataset.convert) ----------------------------
def test_convert_usd_and_constant_2022():
    rows = [{
        "country": "United Kingdom", "iso3": "GBR", "region": "UK",
        "annual_tuition_local": "9250", "currency": "GBP", "year": "2024",
        "include_primary": "1", "source": "s", "notes": "n",
    }]
    rates = {"GBR": {"currency": "GBP", "fx_lcu_per_usd": 0.80, "fx_year": 2024}}
    deflator = {2024: 0.95}  # US CPI_2022 / CPI_2024
    out = build_dataset.convert(rows, rates, deflator)[0]
    nominal = round(9250 / 0.80, 2)
    assert out["annual_tuition_usd"] == nominal
    assert out["annual_tuition_usd_real2022"] == round(nominal * 0.95, 2)
    assert "annual_tuition_usd_ppp" not in out  # PPP removed


def test_convert_usd_base_currency_and_no_deflator():
    rows = [{
        "country": "United States", "iso3": "USA", "region": "US",
        "annual_tuition_local": "11610", "currency": "USD", "year": "2024",
        "include_primary": "1", "source": "s", "notes": "n",
    }]
    rates = {"USA": {"currency": "USD", "fx_lcu_per_usd": 1.0, "fx_year": 2024}}
    out = build_dataset.convert(rows, rates)[0]  # no deflator -> factor 1.0
    assert out["annual_tuition_usd"] == 11610.0
    assert out["annual_tuition_usd_real2022"] == 11610.0


def test_convert_prefers_source_year_rate_key():
    rows = [{
        "country": "United Kingdom", "iso3": "GBR", "region": "UK",
        "annual_tuition_local": "9000", "currency": "GBP", "year": "2023",
        "include_primary": "1", "source": "s", "notes": "",
    }]
    source_rate = {"currency": "GBP", "fx_lcu_per_usd": 0.75, "fx_year": 2023}
    latest_rate = {"currency": "GBP", "fx_lcu_per_usd": 0.90, "fx_year": 2025}
    out = build_dataset.convert(
        rows,
        {("GBR", 2023): source_rate, "GBR": latest_rate},
        {2023: 1.0},
    )[0]
    assert out["annual_tuition_usd"] == 12000.0
    assert out["fx_year"] == 2023


def test_fetch_rates_for_years_uses_nearest_real_observation(monkeypatch):
    monkeypatch.setattr(
        rates,
        "_fetch_series",
        lambda *a, **k: {"GBR": {2022: 0.81, 2024: 0.79}},
    )
    got = rates.fetch_rates_for_years({"GBR": {2023}, "USA": {2023}})
    # A tie selects the newer real observation and records its actual year.
    assert got[("GBR", 2023)]["fx_lcu_per_usd"] == 0.79
    assert got[("GBR", 2023)]["fx_year"] == 2024
    assert got[("USA", 2023)]["fx_lcu_per_usd"] == 1.0
    assert got[("USA", 2023)]["fx_year"] == 2023


# --- primary-row inclusion (shared by analyze + plots) ----------------------
def test_is_primary_predicate():
    assert config.is_primary({"include_primary": "1"}) is True
    assert config.is_primary({"include_primary": ""}) is True   # blank -> primary
    assert config.is_primary({}) is True                        # absent -> primary
    assert config.is_primary({"include_primary": "0"}) is False


def test_load_primary_excludes_reference_rows():
    csv_text = (
        "country,iso3,region,include_primary,annual_tuition_usd\n"
        "United Kingdom,GBR,UK,1,12179.48\n"
        "United Kingdom (Scotland),GBR,UK,0,0.0\n"
        "Blank Flag,XXX,EU,,100.0\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        fh.write(csv_text)
        path = fh.name
    try:
        rows = dataset.load_primary(["annual_tuition_usd"], path=path)
    finally:
        os.unlink(path)
    countries = {r["country"] for r in rows}
    assert countries == {"United Kingdom", "Blank Flag"}          # "0" excluded, blank kept
    assert rows[0]["annual_tuition_usd"] == 12179.48


# --- plot regression: missing region must not KeyError ----------------------
def test_plot_region_comparison_missing_region_no_crash():
    rows = [
        {"country": "United Kingdom", "region": config.UK, "annual_tuition_usd": 12179.48},
        {"country": "Germany", "region": config.EU, "annual_tuition_usd": 0.0},
    ]  # note: no US region present
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        out = fh.name
    try:
        plot_tuition.plot_region_comparison(rows, "annual_tuition_usd", "USD", out)
        assert os.path.getsize(out) > 0
    finally:
        os.unlink(out)


# --- historical deflation (real-terms, inflation-adjusted) -------------------
from tuition import build_history


def test_real_base_usd_deflation():
    # nominal 1000 GBP at FX 0.8 LCU/USD -> $1250 nominal; US CPI 80 at year vs 100 base
    # -> inflate to base: 1250 * (100/80) = $1562.50
    assert build_history.real_base_usd(1000, fx_year_lcu_per_usd=0.8,
                                       us_cpi_year=80, us_cpi_base=100) == 1562.5
    # base year itself (US CPI year == base, USD fx=1) is the identity
    assert build_history.real_base_usd(9750, fx_year_lcu_per_usd=1.0,
                                       us_cpi_year=100, us_cpi_base=100) == 9750


def test_nearest_year_lookup():
    s = {1998: 60.0, 2012: 90.0, 2022: 100.0}
    assert build_history._nearest(s, 2012) == (2012, 90.0)   # exact
    assert build_history._nearest(s, 2011) == (2012, 90.0)   # nearest
    assert build_history._nearest({}, 2000) is None
