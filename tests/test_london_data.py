"""Tests for the london_data analysis (ONS regional GDP -> London concentration).

Parsing/derivation is tested on a small synthetic workbook (no network); a light
integration test runs the real parser only if the committed CSV is present.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from london_data import ons

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _fake_sheet(header_years, rows):
    """Build a Table-5/7-shaped DataFrame: row0 title, row1 header, then data rows.

    ``rows`` = list of (itl, code, name, [values...]).
    """
    width = 3 + len(header_years)
    data = [["title"] + [None] * (width - 1),
            ["ITL", "ITL code", "Region name"] + list(header_years)]
    for itl, code, name, vals in rows:
        data.append([itl, code, name] + list(vals))
    return pd.DataFrame(data)


def _fake_workbook():
    years = [2000, 2001]
    gdp = _fake_sheet(years, [
        ("UK", "UK", "United Kingdom", [1000.0, 1100.0]),
        ("ITL1", "TLI", "London", [200.0, 253.0]),
        ("ITL1", "TLC", "North East", [50.0, 55.0]),
    ])
    per_head = _fake_sheet(years, [
        ("UK", "UK", "United Kingdom", [20000.0, 21000.0]),
        ("ITL1", "TLI", "London", [34000.0, 36000.0]),
    ])
    return {"Table 5": gdp, "Table 7": per_head}


def test_build_rows_share_and_index_math():
    rows = ons.build_rows(_fake_workbook())
    by = {(r["region"], r["year"], r["metric"]): r["value"] for r in rows}

    # London share of UK GDP: 200/1000 = 20.0%, 253/1100 = 23.0%
    assert by[("London", 2000, "share_of_uk_gdp_pct")] == pytest.approx(20.0)
    assert by[("London", 2001, "share_of_uk_gdp_pct")] == pytest.approx(23.0)

    # Per-head index (UK=100): 34000/20000*100 = 170; 36000/21000*100 = 171.4286
    assert by[("London", 2000, "gdp_per_head_index_uk100")] == pytest.approx(170.0)
    assert by[("London", 2001, "gdp_per_head_index_uk100")] == pytest.approx(171.4286, abs=1e-3)

    # Raw levels are carried through unchanged.
    assert by[("United Kingdom", 2000, "gdp_current_gbp_m")] == 1000.0
    assert by[("London", 2001, "gdp_per_head_gbp")] == 36000.0


def test_build_rows_units_and_regions():
    rows = ons.build_rows(_fake_workbook())
    units = {r["metric"]: r["unit"] for r in rows}
    assert units["share_of_uk_gdp_pct"] == "percent"
    assert units["gdp_per_head_index_uk100"] == "index, UK=100"
    # Only London gets the derived ratios; UK is the denominator, not a share row.
    shares = {r["region"] for r in rows if r["metric"] == "share_of_uk_gdp_pct"}
    assert shares == {"London"}
    # Every row cites ONS.
    assert all("Office for National Statistics" in r["source"] for r in rows)


def test_missing_code_raises():
    wb = _fake_workbook()
    wb["Table 5"] = _fake_sheet([2000], [("UK", "UK", "United Kingdom", [1.0])])  # no London
    with pytest.raises(KeyError):
        ons.build_rows(wb)


@pytest.mark.skipif(not (ROOT / "data" / "london_gdp.csv").exists(),
                    reason="committed/generated london_gdp.csv not present")
def test_real_csv_is_sane():
    df = pd.read_csv(ROOT / "data" / "london_gdp.csv")
    share = df[df["metric"] == "share_of_uk_gdp_pct"].sort_values("year")
    # London's share is a plausible 15-30% and the series spans back to the late 1990s.
    assert share["value"].between(15, 30).all()
    assert share["year"].min() <= 1999
    # The share trend rises overall (end above start) — the concentration story.
    assert share["value"].iloc[-1] > share["value"].iloc[0]


def test_to_float_tolerates_ons_markers():
    # ONS footnote/suppression tokens must parse to None, not crash.
    assert ons._to_float("[r]") is None
    assert ons._to_float(":") is None
    assert ons._to_float("-") is None
    assert ons._to_float("1234.5") == 1234.5
    assert ons._to_float(1000) == 1000.0
    assert ons._to_float(float("nan")) is None
    assert ons._to_float(float("inf")) is None


def test_build_rows_skips_suppressed_denominator():
    years = [2000, 2001]
    gdp = _fake_sheet(years, [
        ("UK", "UK", "United Kingdom", [1000.0, "[x]"]),   # 2001 UK GDP suppressed
        ("ITL1", "TLI", "London", [200.0, 253.0]),
    ])
    per_head = _fake_sheet(years, [
        ("UK", "UK", "United Kingdom", [20000.0, 21000.0]),
        ("ITL1", "TLI", "London", [34000.0, 36000.0]),
    ])
    rows = ons.build_rows({"Table 5": gdp, "Table 7": per_head})
    shares = {r["year"] for r in rows if r["metric"] == "share_of_uk_gdp_pct"}
    # 2000 share computes; 2001 is skipped (suppressed denominator), not a crash.
    assert 2000 in shares and 2001 not in shares


def test_resolve_xlsx_url_prefers_pinned_when_no_dated_edition(monkeypatch):
    class _Resp:
        text = '<a href="/file?uri=/some/other/notanedition.xlsx">x</a>'

    monkeypatch.setattr(ons, "_get", lambda url, timeout=60: _Resp())
    # No /1998toYYYY/ edition link -> must fall back to the pinned URL, not the stray xlsx.
    assert ons.resolve_xlsx_url() == ons.PINNED_XLSX


def test_edition_links_and_latest_year(monkeypatch):
    html = """
    <a href="/file?uri=/x/1998to2023/a.xlsx">2023</a>
    <a href="/file?uri=/x/current/a.xlsx">current</a>
    <a href="/file?uri=/x/1998to2024/b.xlsx">2024</a>
    """
    assert ons._edition_links(html) == [
        (2023, "/file?uri=/x/1998to2023/a.xlsx"),
        (2024, "/file?uri=/x/1998to2024/b.xlsx"),
    ]

    class _Resp:
        text = html

    monkeypatch.setattr(ons, "_get", lambda url, timeout=60: _Resp())
    assert ons.latest_published_year() == 2024


def test_availability_status_uses_release_calendar(monkeypatch):
    monkeypatch.setattr(ons, "latest_published_year", lambda timeout=60: 2023)
    monkeypatch.setattr(
        ons,
        "next_release",
        lambda year, timeout=60: {
            "title": "Regional economic activity by gross domestic product, UK: 1998 to 2024",
            "release_date": "2026-09-23T08:30:00.000Z",
            "uri": "/releases/example",
        },
    )
    status = ons.availability_status(2024)
    assert status["available"] is False
    assert status["latest_published_year"] == 2023
    assert status["next_release"]["release_date"].startswith("2026-09-23")
