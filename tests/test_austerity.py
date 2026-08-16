"""Offline tests for the HM Treasury austerity analysis."""

from __future__ import annotations

import pandas as pd
import pytest

from austerity_data import charts, treasury


def _aggregate_sheet() -> pd.DataFrame:
    data = [[None] * 15 for _ in range(9)]
    data[5][1] = "2009-10"
    data[5][3], data[5][9], data[5][10], data[5][13], data[5][14] = (
        900,
        70,
        3.0,
        1020,
        46,
    )
    data[6][1] = "2010-11"
    data[6][3], data[6][9], data[6][10], data[6][13], data[6][14] = (
        920,
        58,
        2.4,
        1040,
        45,
    )
    data[7][1] = "2013-14"
    data[7][3], data[7][9], data[7][10], data[7][13], data[7][14] = (
        915,
        36,
        1.5,
        1015,
        42,
    )
    return pd.DataFrame(data)


def _functions_sheet() -> pd.DataFrame:
    data = [[None] * 5 for _ in range(12)]
    data[4] = [None, "2010-11", "2011-12", "2012-13", "2019-20"]
    data[5] = ["3. Public order and safety", 50, 47, 43, 45]
    data[6] = ["6. Housing and community amenities", 20, 15, 14, 18]
    data[7] = ["7. Health", 170, 171, 173, 200]
    data[8] = ["8. Recreation, culture and religion", 20, 18, 16, 17]
    data[9] = ["2. Defence(2)", 60, 57, 54, 56]
    data[10] = ["of which: public and common services", 10, 9, 8, 9]
    return pd.DataFrame(data)


def _historical_functions_sheet() -> pd.DataFrame:
    data = [[None] * 7 for _ in range(12)]
    data[4] = [None, None, "2000-01", "2001-02", "2002-03", "2003-04", "2010-11"]
    data[6] = [None, "3. Public order and safety", 40, 43, 45, 47, 50]
    data[7] = [None, "6. Housing and community amenities", 10, 12, 14, 15, 20]
    data[8] = [None, "7. Health", 100, 110, 120, 130, 170]
    data[9] = [None, "8. Recreation, culture and religion", 12, 14, 15, 17, 20]
    data[10] = [None, "2. Defence(2)", 48, 50, 52, 54, 60]
    return pd.DataFrame(data)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        treasury.build_rows(
            {
                "4_1": _aggregate_sheet(),
                "4_3": _functions_sheet(),
                "historical_4_3": _historical_functions_sheet(),
            }
        )
    )


def test_parse_aggregates_values_and_units() -> None:
    rows = treasury.parse_aggregates(_aggregate_sheet())
    by = {(r["financial_year"], r["metric"]): r for r in rows}
    assert by[("2010-11", "public_sector_net_investment_pct_gdp")]["value"] == 2.4
    assert by[("2013-14", "total_managed_expenditure_real")]["value"] == 1015
    assert by[("2009-10", "public_sector_current_expenditure_real")]["year"] == 2009
    assert all(set(row) == set(treasury.ROW_FIELDS) for row in rows)


def test_parse_functions_ignores_subfunctions() -> None:
    rows = treasury.parse_functions(_functions_sheet())
    categories = {row["category"] for row in rows}
    assert "public_order_safety" in categories
    assert "housing_community" in categories
    assert "public_common_services" not in categories
    assert len(rows) == 5 * 4


def test_parse_historical_functions_and_source() -> None:
    rows = treasury.parse_historical_functions(_historical_functions_sheet())
    assert len(rows) == 5 * 5
    first = next(
        row for row in rows
        if row["category"] == "housing_community"
        and row["financial_year"] == "2000-01"
    )
    assert first["value"] == 10
    assert "2012" in first["source"]
    assert "2011-12 prices" in first["unit"]


def test_index_and_trough_math() -> None:
    frame = _frame()
    housing = charts.indexed_function_series(frame, "housing_community")
    assert housing.iloc[0]["financial_year"] == "2000-01"
    assert housing.iloc[0]["index"] == pytest.approx(50)
    assert housing[housing["financial_year"] == "2012-13"].iloc[0]["index"] == 70
    change, year = charts.trough_change(frame, "housing_community")
    assert change == pytest.approx(-30)
    assert year == "2012-13"


def test_release_and_workbook_link_parsing() -> None:
    html = """
    <a href="/government/statistics/public-spending-statistics-release-july-2025">x</a>
    <a href="/government/statistics/public-spending-statistics-release-july-2026">y</a>
    """
    links = treasury._release_links(html)
    assert max(links)[0] == 2026
    release = """
    <a href="https://assets.publishing.service.gov.uk/media/x/Chapter_1.xlsx">one</a>
    <a href="https://assets.publishing.service.gov.uk/media/x/July_PSS_2026_Chapter_4.xlsx">four</a>
    """
    assert treasury._chapter4_links(release) == [
        "https://assets.publishing.service.gov.uk/media/x/July_PSS_2026_Chapter_4.xlsx"
    ]


def test_invalid_fiscal_year_rejected() -> None:
    with pytest.raises(ValueError):
        treasury.fiscal_start("2010")
