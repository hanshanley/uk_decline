"""Offline unit tests for the uk_migration package (no network)."""

from __future__ import annotations

import pytest

from uk_migration import schema
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


def test_ons_ltim_parse_takes_ye_dec_all_nationalities():
    rows = [
        ("Flow", "Period", "All Nationalities", "British"),
        ("Immigration", "YE Jun 22", 1167000, 1),
        ("Immigration", "YE Dec 22", 1398000, 1),
        ("Emigration", "YE Dec 22", 486000, 1),
        ("Net migration", "YE Dec 24 R", 331000, 1),
        ("Net migration", "YE Dec 25 P", 171000, 1),
        # 4-digit-year label must not be truncated to 2020:
        ("Immigration", "YE Dec 2026", 800000, 1),
        ("Immigration", "not a period", 999, 1),
    ]
    out = ons_ltim.parse(rows)
    by = {(r["metric"], r["period"]): r for r in out}
    assert by[("immigration", 2022)]["value"] == 1398000.0
    assert by[("immigration", 2022)]["legality"] == schema.LEGAL
    assert by[("immigration", 2022)]["flow_type"] == schema.INFLOW
    assert by[("emigration", 2022)]["flow_type"] == schema.OUTFLOW
    assert by[("net_migration", 2024)]["legality"] == schema.TOTAL
    assert by[("net_migration", 2024)]["flow_type"] == schema.NET
    assert by[("net_migration", 2025)]["value"] == 171000.0
    assert by[("immigration", 2026)]["value"] == 800000.0  # 4-digit year handled
    # YE Jun and the junk period are excluded
    assert ("immigration", 2021) not in by
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
