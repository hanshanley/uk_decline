"""Offline unit tests for the uk_migration package (no network)."""

from __future__ import annotations

import pytest

from uk_migration import normalize, schema
from uk_migration._aggregate import aggregate_by_year
from uk_migration.sources import asylum, irregular, ons_ltim, visas


def test_schema_row_valid():
    r = schema.row(
        2020, "immigration", 500000,
        unit="people", legality=schema.LEGAL, flow_type=schema.INFLOW, source="test",
    )
    assert r["iso3"] == "GBR"
    assert r["country"] == "United Kingdom"
    assert r["period"] == 2020 and isinstance(r["period"], int)
    assert r["value"] == 500000.0 and isinstance(r["value"], float)
    assert r["category"] == "all"
    assert r["flow_type"] == schema.INFLOW
    assert tuple(r.keys()) == schema.FIELDS


def test_schema_row_rejects_bad_legality():
    with pytest.raises(ValueError):
        schema.row(2020, "x", 1, unit="people", legality="bogus", flow_type=schema.NET, source="test")


def test_schema_row_rejects_bad_flow_type():
    with pytest.raises(ValueError):
        schema.row(2020, "x", 1, unit="people", legality=schema.LEGAL, flow_type="bogus", source="test")


def test_aggregate_sums_by_year_and_drops_partial_year_per_category():
    header = ("Year", "Quarter", "Method", "Value")
    rows = [
        header,
        # 2020, category a: four quarters -> kept
        (2020, "2020 Q1", "a", 10),
        (2020, "2020 Q2", "a", 10),
        (2020, "2020 Q3", "a", 10),
        (2020, "2020 Q4", "a", 10),
        # 2020, category b: four quarters -> kept
        (2020, "2020 Q1", "b", 5),
        (2020, "2020 Q2", "b", 5),
        (2020, "2020 Q3", "b", 5),
        (2020, "2020 Q4", "b", 5),
        # 2020, category c: only two quarters -> dropped even though the YEAR is complete
        (2020, "2020 Q1", "c", 7),
        (2020, "2020 Q2", "c", 7),
        # 2021 partial (only Q1) -> dropped
        (2021, "2021 Q1", "a", 99),
    ]
    out = aggregate_by_year(
        rows,
        header_rows=1,
        year_idx=0,
        quarter_idx=1,
        value_idx=3,
        category_of=lambda r: r[2],
    )
    assert (2020, "a", 40.0) in out
    assert (2020, "b", 20.0) in out
    # per-(year,category) completeness: c is dropped despite 2020 having 4 quarters overall
    assert all(cat != "c" for _, cat, _ in out)
    assert all(year != 2021 for year, _, _ in out)


def test_aggregate_can_keep_partial_year():
    rows = [("Year", "Q", "V"), (2021, "2021 Q1", 99)]
    out = aggregate_by_year(
        rows,
        header_rows=1,
        year_idx=0,
        quarter_idx=1,
        value_idx=2,
        category_of=lambda r: "all",
        complete_years_only=False,
    )
    assert out == [(2021, "all", 99.0)]


def test_ons_ltim_parse_by_group_and_ye_dec():
    # Table 1 columns: Flow, Period, All, British, EU+, Non-EU+
    rows = [
        ("Flow", "Period", "All Nationalities", "British", "EU+", "Non-EU+"),
        ("Immigration", "YE Jun 22", 1167000, 70000, 500000, 597000),
        ("Immigration", "YE Dec 22", 1398000, 74000, 550000, 774000),
        ("Emigration", "YE Dec 22", 486000, 60000, 200000, 226000),
        ("Net migration", "YE Dec 24 R", 331000, 10000, 100000, 221000),
        ("Net migration", "YE Dec 25 P", 171000, 5000, 60000, 106000),
        # 4-digit-year label must not be truncated to 2020:
        ("Immigration", "YE Dec 2026", 800000, 40000, 300000, 460000),
        ("Immigration", "not a period", 999, 1, 1, 1),
    ]
    out = ons_ltim.parse(rows)
    by = {(r["metric"], r["category"], r["period"]): r for r in out}
    assert by[("immigration", "all", 2022)]["value"] == 1398000.0
    assert by[("immigration", "british", 2022)]["value"] == 74000.0
    assert by[("immigration", "eu", 2022)]["value"] == 550000.0
    assert by[("immigration", "non_eu", 2022)]["value"] == 774000.0
    assert by[("immigration", "all", 2022)]["legality"] == schema.TOTAL
    assert by[("emigration", "all", 2022)]["flow_type"] == schema.OUTFLOW
    assert by[("net_migration", "all", 2024)]["legality"] == schema.TOTAL
    assert by[("net_migration", "non_eu", 2025)]["value"] == 106000.0
    assert by[("immigration", "all", 2026)]["value"] == 800000.0  # 4-digit year handled
    # YE Jun and the junk period are excluded
    assert ("immigration", "all", 2021) not in by
    assert all(r["value"] != 999 for r in out)


def _pad(*values, width):
    row = list(values)
    row += [None] * (width - len(row))
    return tuple(row)


def test_visas_parse_counts_only_issued_by_group():
    # Data_Vis_D02 layout, header on row index 3 (4 header rows).
    W = 10
    rows = [
        _pad("title", width=W),
        _pad("notes", width=W),
        _pad("contents", width=W),
        _pad("Year", "Quarter", "Nat", "Reg", "Visa type group", "vt", "vs", "Applicant", "Case outcome", "Decisions", width=W),
    ]
    for q in ("Q1", "Q2", "Q3", "Q4"):
        rows.append(_pad(2020, f"2020 {q}", "N", "R", "Work", "vt", "vs", "All", "Issued", 100, width=W))
        rows.append(_pad(2020, f"2020 {q}", "N", "R", "Work", "vt", "vs", "All", "Refused", 50, width=W))
        rows.append(_pad(2020, f"2020 {q}", "N", "R", "Study", "vt", "vs", "All", "Issued", 10, width=W))
    out = visas.parse(rows)
    by = {(r["category"], r["period"]): r for r in out}
    assert by[("work", 2020)]["value"] == 400.0  # 4 quarters * 100 issued
    assert by[("study", 2020)]["value"] == 40.0
    assert all(r["metric"] == "visas_granted" for r in out)
    assert all(r["legality"] == schema.LEGAL for r in out)
    assert all(r["flow_type"] == schema.COUNT for r in out)


def test_asylum_parse_counts_main_applicants():
    W = 10
    rows = [
        _pad("title", width=W),
        _pad("Year", "Quarter", "Nat", "Reg", "Age", "Sex", "Applicant type", "UASC", "Loc", "Claims", width=W),
    ]
    for q in ("Q1", "Q2", "Q3", "Q4"):
        rows.append(_pad(2020, f"2020 {q}", "N", "R", "A", "S", "Main Applicant", "U", "L", 25, width=W))
        rows.append(_pad(2020, f"2020 {q}", "N", "R", "A", "S", "Dependant", "U", "L", 5, width=W))
    out = asylum.parse(rows)
    assert len(out) == 1
    assert out[0]["category"] == "main_applicant"
    assert out[0]["value"] == 100.0  # dependants excluded
    assert out[0]["legality"] == schema.LEGAL


def test_irregular_parse_splits_methods_and_totals():
    W = 8
    rows = [
        _pad("title", width=W),
        _pad("Year", "Quarter", "Method of entry", "Nat", "Reg", "Sex", "Age", "Number of detections", width=W),
    ]
    for q in ("Q1", "Q2", "Q3", "Q4"):
        rows.append(_pad(2020, f"2020 {q}", "Small boat arrivals", "N", "R", "S", "A", 100, width=W))
        rows.append(_pad(2020, f"2020 {q}", "Recorded detections at UK ports", "N", "R", "S", "A", 20, width=W))
    out = irregular.parse(rows)
    by = {(r["category"], r["period"]): r for r in out}
    assert by[("small_boat", 2020)]["value"] == 400.0
    assert by[("port", 2020)]["value"] == 80.0
    assert by[("all", 2020)]["value"] == 480.0
    assert all(r["legality"] == schema.IRREGULAR for r in out)
    assert all(r["flow_type"] == schema.COUNT for r in out)


def test_normalize_per_capita_is_exact_ratio_of_real_series():
    rows = [
        schema.row(1974, "uk_population", 56_229_974, unit="people",
                   legality=schema.TOTAL, flow_type=schema.STOCK, source="World Bank WDI"),
        schema.row(1974, "net_migration_wb", -65_710, unit="people",
                   legality=schema.TOTAL, flow_type=schema.NET, source="World Bank WDI"),
        # a metric NOT in the whitelist must not be normalised:
        schema.row(1974, "migrant_stock", 3_000_000, unit="people",
                   legality=schema.TOTAL, flow_type=schema.STOCK, source="World Bank WDI"),
        # a year with no population must be skipped:
        schema.row(1975, "net_migration_wb", -40_241, unit="people",
                   legality=schema.TOTAL, flow_type=schema.NET, source="World Bank WDI"),
    ]
    out = normalize.per_capita(rows)
    assert len(out) == 1
    d = out[0]
    assert d["metric"] == "net_migration_wb_per_1000_pop"
    assert d["value"] == -65_710 / 56_229_974 * 1000.0  # exact ratio, nothing invented
    assert d["unit"] == "per 1,000 population"
    assert d["flow_type"] == schema.NET
    assert d["source"].startswith("Derived:")
    # stock (not whitelisted) and the population-less year are excluded
    assert all("migrant_stock" not in r["metric"] for r in out)
    assert all(r["period"] != 1975 for r in out)


def test_ons_ips_history_parse_by_origin_in_thousands():
    from uk_migration.sources import ons_ips_history
    # Minimal replica of the IPS "Data" sheet: header rows then year rows.
    # Columns: 0=Year, 1..3 All(Imm,Emi,Net), 4..6 British, 7..9 Non-British, 10..12 EU
    W = 25

    def rrow(*vals):
        r = list(vals) + [""] * (W - len(vals))
        return tuple(r)

    rows = [
        rrow("Table 1"),
        rrow(""),
        rrow("", "All Citizenships", "", "", "British Citizenship"),
        rrow("Year", "Immigration", "Emigration", "Net Migration",
             "Immigration", "Emigration", "Net Migration"),
        # 1964: All imm=211k, emi=271k, net=-60k ; British imm=71k ; EU '-' (missing)
        rrow(1964.0, 211.0, 271.0, -60.0, 71.0, 202.0, -131.0, " - ", " - ", " - ",
             " - ", " - ", " - "),
        rrow("footer text"),
    ]
    out = ons_ips_history.parse(rows)
    by = {(r["metric"], r["category"]): r for r in out}
    # thousands are scaled to people
    assert by[("immigration_by_origin", "all")]["value"] == 211_000.0
    assert by[("immigration_by_origin", "all")]["period"] == 1964
    assert by[("net_migration_by_origin", "all")]["value"] == -60_000.0
    assert by[("net_migration_by_origin", "all")]["flow_type"] == schema.NET
    assert by[("immigration_by_origin", "british")]["value"] == 71_000.0
    assert by[("immigration_by_origin", "british")]["legality"] == schema.LEGAL
    # '-' cells are skipped, not turned into 0
    assert ("immigration_by_origin", "eu") not in by
