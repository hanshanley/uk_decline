"""Offline unit tests for the europe_data pipeline (no network required).

Run directly:  python tests/test_pipeline.py
Or with pytest: pytest tests/ -q
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from europe_data import combine, countries, eurostat  # noqa: E402


def test_country_mappings() -> None:
    # Eurostat quirks: Greece is EL (not GR), UK is UK (not GB).
    assert countries.BY_ISO3["GRC"].eurostat == "EL"
    assert countries.BY_ISO3["GBR"].eurostat == "UK"
    assert countries.iso3_for_eurostat("EL") == "GRC"
    assert countries.iso3_for_eurostat("UK") == "GBR"
    assert countries.name_for_iso3("DEU") == "Germany"
    # Aggregates are reachable via the Eurostat lookup but not the country list.
    geos = countries.eurostat_geos(include_aggregates=True)
    assert "EU27_2020" in geos and "UK" in geos
    assert "EU27_2020" not in countries.eurostat_geos(include_aggregates=False)
    # No duplicate ISO3 codes.
    iso3s = countries.iso3_codes()
    assert len(iso3s) == len(set(iso3s))
    # United States is a GDP peer but NOT part of the European allow-list, so it must not
    # leak into the Eurostat geos or the PIP/European country set.
    assert countries.name_for_iso3("USA") == "United States"
    assert "USA" in countries.gdp_iso3_codes(include_aggregates=False)
    assert "USA" not in countries.iso3_codes()
    assert "US" not in countries.eurostat_geos(include_aggregates=True)


def test_maddison_metric_in_wide_order() -> None:
    # The real (inflation-adjusted) Maddison GDP series must flow into the wide table.
    from europe_data import combine, maddison
    assert maddison.METRIC == "gdp_per_capita_real_maddison"
    assert maddison.METRIC in combine.METRIC_ORDER
    # It is a REAL series (constant-price / inflation-adjusted).
    assert "2011" in maddison.UNIT and "real" in maddison.UNIT.lower()


def test_headline_gdp_is_constant_usd_not_ppp() -> None:
    # Headline GDP metric must be real constant-US$ (NON-PPP), per the chosen methodology.
    from europe_data import plot_uk_decline
    from europe_data import combine, worldbank
    assert plot_uk_decline.GDP_METRIC == "gdp_per_capita_constant_usd"
    assert "PPP" not in plot_uk_decline.GDP_METRIC.upper()
    # It comes from World Bank NY.GDP.PCAP.KD and flows into the wide table.
    assert worldbank.INDICATORS["NY.GDP.PCAP.KD"][0] == "gdp_per_capita_constant_usd"
    assert "2015 US$" in worldbank.INDICATORS["NY.GDP.PCAP.KD"][1]
    assert "gdp_per_capita_constant_usd" in combine.METRIC_ORDER


def test_eurostat_decoder() -> None:
    # Minimal JSON-stat: 1 statinfo x 2 geo x 2 time = 4 obs (row-major).
    payload = {
        "id": ["statinfo", "geo", "time"],
        "size": [1, 2, 2],
        "dimension": {
            "statinfo": {"category": {"index": {"MED_EI": 0}}},
            "geo": {"category": {"index": {"DE": 0, "UK": 1}}},
            "time": {"category": {"index": {"2017": 0, "2018": 1}}},
        },
        # linear index = geo*2 + time
        "value": {"0": 100.0, "1": 110.0, "2": 200.0, "3": 210.0},
    }
    decoded = {
        (c["geo"], c["time"]): v for c, v in eurostat._iter_values(payload)
    }
    assert decoded[("DE", "2017")] == 100.0
    assert decoded[("DE", "2018")] == 110.0
    assert decoded[("UK", "2017")] == 200.0
    assert decoded[("UK", "2018")] == 210.0


def test_combine_long_and_wide() -> None:
    rows = [
        {"iso3": "GBR", "country": "United Kingdom", "year": 2020,
         "metric": "gdp_per_capita_ppp_current", "value": 50000.0,
         "unit": "current international $", "source": "World Bank WDI"},
        {"iso3": "GBR", "country": "United Kingdom", "year": 2020,
         "metric": "median_income_pip", "value": 53.4,
         "unit": "2017 PPP $ per day", "source": "World Bank PIP"},
        {"iso3": "DEU", "country": "Germany", "year": 2020,
         "metric": "gdp_per_capita_ppp_current", "value": 56000.0,
         "unit": "current international $", "source": "World Bank WDI"},
    ]
    with tempfile.TemporaryDirectory() as d:
        long_path = Path(d) / "long.csv"
        wide_path = Path(d) / "wide.csv"
        combine.write_long(rows, str(long_path))
        combine.write_wide(rows, str(wide_path))

        long_rows = list(csv.DictReader(open(long_path)))
        assert len(long_rows) == 3
        assert set(long_rows[0]) == set(combine.LONG_FIELDS)

        wide_rows = {r["country"]: r for r in csv.DictReader(open(wide_path))}
        uk = wide_rows["United Kingdom"]
        assert uk["gdp_per_capita_ppp_current"] == "50000.0"
        assert uk["median_income_pip"] == "53.4"
        # Missing metric for the UK row is blank, not an error.
        assert uk["mean_disposable_income"] == ""
        assert wide_rows["Germany"]["median_income_pip"] == ""


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
