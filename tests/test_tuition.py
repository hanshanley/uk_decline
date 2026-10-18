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
    out = build_dataset.convert(rows, rates)[0]
    assert out["annual_tuition_usd"] == 11610.0
    assert out["annual_tuition_usd_real2022"] is None


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


def test_fetch_rates_for_future_year_caps_world_bank_range(monkeypatch):
    calls = []

    def fake_fetch(indicator, iso3s, start, end):
        calls.append(end)
        return {"GBR": {2025: 0.8}}

    monkeypatch.setattr(rates, "_fetch_series", fake_fetch)
    got = rates.fetch_rates_for_years({"GBR": {2026}})
    assert got[("GBR", 2026)]["fx_year"] == 2025
    assert calls == [rates.dt.date.today().year - 1]


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
        {"country": "United Kingdom", "region": config.UK, "year": 2023, "annual_tuition_usd": 12179.48},
        {"country": "Germany", "region": config.EU, "year": 2023, "annual_tuition_usd": 0.0},
    ]  # note: no US region present
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        out = fh.name
    try:
        plot_tuition.plot_region_comparison(rows, "annual_tuition_usd", "USD", out)
        assert os.path.getsize(out) > 0
    finally:
        os.unlink(out)


def test_region_chart_includes_england_and_one_eu_summary_with_honest_units(monkeypatch, tmp_path):
    import pytest
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    rows = [
        {"country": "United Kingdom", "region": config.UK, "year": 2023, "annual_tuition_usd": 12890.5},
        {"country": "United States", "region": config.US, "year": 2023, "annual_tuition_usd": 11950},
        {"country": "Germany", "region": config.EU, "year": 2023, "annual_tuition_usd": 0},
        {"country": "Italy", "region": config.EU, "year": 2023, "annual_tuition_usd": 1600},
    ]
    captured = []
    monkeypatch.setattr(plot_tuition, "save_chart", lambda fig, *a, **k: captured.append(fig))
    plot_tuition.plot_region_comparison(rows, "annual_tuition_usd", "current US dollars", str(tmp_path / "chart.png"))
    fig = captured[0]
    ax = fig.axes[0]
    assert len(ax.patches) == 3
    assert [patch.get_width() for patch in ax.patches] == pytest.approx([800, 11950, 12890.5])
    labels = [label.get_text() for label in ax.get_yticklabels()]
    assert any("England (fee cap)" in label and "2023/24" in label for label in labels)
    assert any("EU sample (2/27 countries)" in label for label in labels)
    assert not any(label.startswith(("Germany", "Italy")) for label in labels)
    assert "not an official EU or student-weighted average" in fig.texts[0].get_text()
    assert "Currency conversion uses 2023 annual World Bank exchange rates." in " ".join(fig.texts[0].get_text().split())
    assert "constant" not in ax.get_xlabel()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[0].get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0


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


def test_historical_uk_cap_expands_to_annual_policy_schedule():
    rows = [
        {
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2012", "annual_tuition_local": "9000", "currency": "GBP",
            "source": "cap 2012", "source_url": "https://example.com/2012",
        },
        {
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2017", "annual_tuition_local": "9250", "currency": "GBP",
            "source": "cap 2017", "source_url": "https://example.com/2017",
        },
    ]
    expanded = build_history.expand_uk_fee_schedule(rows)
    by_year = {int(row["year"]): float(row["annual_tuition_local"]) for row in expanded}
    assert by_year == {
        2012: 9000, 2013: 9000, 2014: 9000, 2015: 9000, 2016: 9000,
        2017: 9250,
    }


def test_future_fee_cap_without_same_year_inputs_is_omitted(monkeypatch):
    calls = []

    def fake_fetch(indicator, iso3s, start, end):
        calls.append(end)
        if indicator == config.WB_CPI_INDICATOR:
            return {"USA": {2022: 100.0, 2025: 110.0}}
        return {"GBR": {2025: 0.8}}

    monkeypatch.setattr(build_history, "fetch_series", fake_fetch)
    monkeypatch.setattr(build_history, "load_cpi", lambda *a: {2022: 100, 2025: 110})
    rows = [{
        "country": "United Kingdom", "iso3": "GBR", "region": "UK",
        "year": "2026", "annual_tuition_local": "9790", "currency": "GBP",
        "source": "published cap", "source_url": "https://example.com",
    }]
    out = build_history.deflate_manual(rows)
    assert out[0]["year"] == 2026
    assert out[0]["real_2022_usd"] is None
    assert all(end <= build_history.dt.date.today().year - 1 for end in calls)


def test_zero_fee_country_is_not_requested_from_fx_api(monkeypatch):
    calls = []

    def fake_fetch(indicator, iso3s, start, end):
        calls.append((indicator, tuple(iso3s)))
        if indicator == config.WB_CPI_INDICATOR:
            return {"USA": {2022: 100.0}}
        return {"GBR": {2022: 0.8}}

    monkeypatch.setattr(build_history, "fetch_series", fake_fetch)
    monkeypatch.setattr(build_history, "load_cpi", lambda *a: {2022: 100})
    rows = [
        {
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2022", "annual_tuition_local": "9250", "currency": "GBP",
            "source": "UK", "source_url": "https://example.com/uk",
        },
        {
            "country": "Germany", "iso3": "DEU", "region": "EU",
            "year": "2022", "annual_tuition_local": "0", "currency": "EUR",
            "source": "DE", "source_url": "https://example.com/de",
        },
    ]
    out = build_history.deflate_manual(rows)
    fx_calls = [iso3s for indicator, iso3s in calls if indicator == config.WB_FX_INDICATOR]
    assert fx_calls == [("GBR",)]
    assert next(row for row in out if row["iso3"] == "DEU")["real_2022_usd"] == 0


def test_future_snapshot_does_not_substitute_nearest_published_cpi(monkeypatch):
    monkeypatch.setattr(
        build_dataset,
        "load_cpi",
        lambda *a, **k: {2022: 100.0, 2025: 110.0},
    )
    got = build_dataset._us_cpi_deflator({2026})
    assert got == {}


def test_snapshot_cpi_request_includes_exact_base_year(monkeypatch):
    calls = []

    def fetch(start, end):
        calls.append(start)
        return {2022: 100.0, 2025: 110.0}

    monkeypatch.setattr(build_dataset, "load_cpi", fetch)
    assert build_dataset._us_cpi_deflator({2025}) == {2025: 100 / 110}
    assert calls == [2022]


def test_zero_snapshot_fee_needs_no_fx_or_cpi():
    rows = [{
        "country": "Germany", "iso3": "DEU", "region": "EU",
        "annual_tuition_local": "0", "currency": "EUR", "year": "2024",
    }]
    out = build_dataset.convert(rows, {})[0]
    assert out["annual_tuition_usd"] == out["annual_tuition_usd_real2022"] == 0


def test_snapshot_currency_mismatch_is_not_converted():
    import pytest

    rows = [{
        "country": "Croatia", "iso3": "HRV", "region": "EU",
        "annual_tuition_local": "1000", "currency": "HRK", "year": "2022",
    }]
    with pytest.raises(ValueError, match="currencies do not match"):
        build_dataset.convert(rows, {"HRV": {
            "currency": "EUR", "fx_lcu_per_usd": 0.9, "fx_year": 2024,
        }}, {2022: 1})


def test_history_preserves_free_uk_anchor_and_annual_upratings():
    uk = [r for r in build_history.expand_uk_fee_schedule(build_history.load_manual())
          if r["iso3"] == "GBR"]
    values = {int(r["year"]): float(r["annual_tuition_local"]) for r in uk}
    assert values[1971] == 0
    assert values[2005] == 1175
    assert values[2011] == 3375
    assert values[2016] == 9000


def test_history_plot_does_not_connect_free_uk_anchor_to_fee_introduction(tmp_path, monkeypatch):
    import math
    from tuition import plot_history

    monkeypatch.setattr(plot_history, "load_history",
                        lambda: {config.UK: [(1971, 0), (1998, 2973), (1999, 3000)]})
    figures = []
    close = plot_history.plt.close
    monkeypatch.setattr(plot_history.plt, "close", figures.append)
    out = tmp_path / "tuition_history.png"
    plot_history.plot(str(out))
    fig = figures[-1]
    try:
        fee_line, zero_anchors = fig.axes[0].lines
        positive = [(x, y) for x, y in zip(fee_line.get_xdata(), fee_line.get_ydata())
                    if not math.isnan(y)]
        assert positive == [(1998, 2973), (1999, 3000)]
        assert math.isnan(fee_line.get_ydata()[0])
        assert list(zero_anchors.get_xdata()) == [1971]
        assert list(zero_anchors.get_ydata()) == [0]
        assert zero_anchors.get_linestyle() == "None"
        assert out.stat().st_size > 0
    finally:
        close(fig)


def test_nces_history_uses_same_calendar_cpi_basis(tmp_path, monkeypatch):
    csv = tmp_path / "nces.csv"
    csv.write_text(
        "year,tuition_current_usd,tuition_constant2022_usd,source,source_url\n"
        "2020,1000,1250,NCES,https://nces.ed.gov\n"
        "2022,1100,1100,NCES,https://nces.ed.gov\n"
    )
    monkeypatch.setattr(config, "NCES_CSV", csv)
    out = build_history.load_nces({2020: 100, 2022: 110})
    assert [r["real_2022_usd"] for r in out] == [1100, 1100]


def test_history_missing_exact_base_cpi_is_not_substituted(monkeypatch):
    import pytest

    monkeypatch.setattr(build_history, "load_cpi",
                        lambda *a, **k: {2021: 100, 2023: 110})
    monkeypatch.setattr(build_history, "fetch_series", lambda *a, **k: {})
    with pytest.raises(RuntimeError, match="CPI"):
        build_history.deflate_manual([{
            "country": "United Kingdom", "iso3": "GBR", "region": "UK",
            "year": "2022", "annual_tuition_local": "9250", "currency": "GBP",
            "source": "cap", "source_url": "https://example.com",
        }])


def test_nces_default_cpi_range_includes_observations_after_base_year(tmp_path, monkeypatch):
    csv = tmp_path / "nces.csv"
    csv.write_text(
        "year,tuition_current_usd,source,source_url\n"
        "2022,9750,NCES,https://nces.ed.gov\n"
        "2023,9872,NCES,https://nces.ed.gov\n"
    )
    monkeypatch.setattr(config, "NCES_CSV", csv)
    calls = []

    def fetch(start, end):
        calls.append((start, end))
        return {2022: 100, 2023: 110}

    monkeypatch.setattr(build_history, "load_cpi", fetch)
    out = build_history.load_nces()
    assert calls == [(2022, 2023)]
    assert out[-1]["real_2022_usd"] == round(9872 * 100 / 110, 2)


def _bls_payload(annual):
    from tuition.cpi import SERIES_ID

    return {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"seriesID": SERIES_ID, "data": [
            {"year": str(year), "period": "M13", "value": str(value)}
            for year, value in annual
        ] + [{"year": "2025", "period": "M12", "value": "999"}]}]},
    }


def test_bls_uses_published_annual_not_december_or_monthly_average():
    from tuition import cpi

    assert cpi.parse(_bls_payload([(2024, 313.689), (2025, 321.943)]),
                     2024, 2025) == {2024: 313.689, 2025: 321.943}


def test_bls_invalid_refresh_preserves_saved_data(tmp_path, monkeypatch):
    import pytest
    from tuition import cpi

    path = tmp_path / "cpi.csv"
    path.write_text("saved data\n")
    monkeypatch.setattr(config, "CPI_CSV", path)
    for payload in (
        {"status": "REQUEST_NOT_PROCESSED", "message": ["limit reached"]},
        _bls_payload([]),
        _bls_payload([(1963, 30), (1963, 31)]),
        _bls_payload([(1963, float("nan"))]),
        _bls_payload([(1963, 0)]),
    ):
        monkeypatch.setattr(cpi, "get_json", lambda *a, **k: payload)
        with pytest.raises(ValueError, match="BLS"):
            cpi.main()
        assert path.read_text() == "saved data\n"


def _collegeboard_frame():
    import pandas as pd
    from tuition.fetch_collegeboard import FIRST_YEAR, LAST_YEAR

    rows = [
        ["Tuition and Fees in 2025 Dollars"] + [None] * 11,
        ["25-26", 99999, None, 99999] + [None] * 8,
        [None, "Tuition and Fees in Current Dollars"] + [None] * 5
        + ["Tuition and Fees and Housing and Food in Current Dollars"] + [None] * 4,
        ["Academic Year", "Private Nonprofit Four-Year", "One-Year % Change",
         "Public Four-Year"] + [None] * 5 + ["Public Four-Year", None, None],
    ]
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        value = 11950 if year == LAST_YEAR else 430 + year - FIRST_YEAR
        rows.append([f"{year % 100:02}-{(year + 1) % 100:02}", 45000, None, value]
                    + [None] * 5 + [99999, None, None])
    rows.append([
        "SOURCES: 1987-88 and after: full-time undergraduate enrollment; "
        "1986-87 and prior: full-time equivalent enrollment."
    ] + [None] * 11)
    return pd.DataFrame(rows)


def test_collegeboard_parses_complete_nominal_source_not_housing_or_constant_dollars():
    from tuition import fetch_collegeboard

    rows = fetch_collegeboard.parse(_collegeboard_frame())
    assert [r["year"] for r in rows] == list(range(1971, 2026))
    assert rows[0]["tuition_current_usd"] == 430
    assert rows[-1]["tuition_current_usd"] == 11950
    assert "full-time-equivalent" in rows[15]["source"]
    assert "Annual Survey" in rows[16]["source"]


def test_collegeboard_discovers_and_validates_a_new_complete_publisher_edition():
    import pandas as pd
    import pytest
    from tuition import fetch_collegeboard as source

    url = source.SOURCE_URL.replace("2025", "2026")
    discovered = source.latest_workbook(
        f'<a href="{source.SOURCE_URL}">Archive</a><a href="{url}">Latest Excel data</a>'
    )
    assert discovered == (url, 2026)
    frame = _collegeboard_frame()
    row = ["26-27", 45000, None, 12500] + [None] * 5 + [99999, None, None]
    frame = pd.concat([frame.iloc[:-1], pd.DataFrame([row]), frame.iloc[-1:]], ignore_index=True)
    rows = source.parse(frame, edition=2026, source_url=url)
    assert rows[-1]["year"] == 2026
    assert rows[-1]["tuition_current_usd"] == 12500
    assert rows[-1]["source_url"] == url
    assert "Pricing 2026" in rows[-1]["source"]
    with pytest.raises(ValueError, match="no pricing-data workbook"):
        source.latest_workbook('<a href="https://example.invalid/data.xlsx">Not the publisher</a>')


def test_collegeboard_missing_or_duplicate_year_does_not_replace_saved_data(tmp_path, monkeypatch):
    import pytest
    from tuition import fetch_collegeboard

    path = tmp_path / "collegeboard.csv"
    path.write_text("saved history\n")
    workbook = tmp_path / "input.xlsx"
    workbook.write_bytes(b"placeholder; reader mocked")
    monkeypatch.setattr(config, "COLLEGEBOARD_CSV", path)
    for label in ("missing", "24-25", "25-27"):
        frame = _collegeboard_frame()
        frame.iloc[-2, 0] = label
        monkeypatch.setattr(fetch_collegeboard.pd, "read_excel", lambda *a, **k: frame)
        with pytest.raises(ValueError, match="College Board"):
            fetch_collegeboard.main(["--input", str(workbook)])
        assert path.read_text() == "saved history\n"


def test_collegeboard_chart_breaks_at_collection_change(tmp_path, monkeypatch):
    import math
    from tuition import plot_history

    monkeypatch.setattr(plot_history, "load_history", lambda: {
        config.US: [(1986, 4000), (1987, 4100), (1988, 4200)],
    })
    figures = []
    monkeypatch.setattr(plot_history, "save_chart",
                        lambda fig, *a, **k: figures.append(fig))
    plot_history.plot(str(tmp_path / "history.png"))
    line = figures[0].axes[0].lines[0]
    assert any(math.isnan(value) for value in line.get_ydata())
    assert 4100 in line.get_ydata(), "the break must not discard the 1987 observation"


def _nces_html(*, missing_year=None, current_header="Current dollars", invalid_year=None):
    import pandas as pd

    columns = [("Other", "Other", "Other", str(i)) for i in range(25)]
    columns[5] = (current_header, "Tuition and required fees2", "4-year", "6")
    columns[17] = ("Constant 2023-24 dollars1", "Tuition and required fees2", "4-year", "18")
    rows = []
    for label in ["All institutions", "Public institutions"]:
        rows.append([label] + [None] * 24)
        for year in [1963, *range(1968, 2024)]:
            if label == "Public institutions" and year == missing_year:
                continue
            academic = f"{year}-{str(year + 1)[-2:]}" + ("5" if year == 1985 else "")
            if year == 1999:
                academic = "1999-2000"
            row = [academic] + [None] * 24
            row[5], row[17] = (9872 if label == "Public institutions" else 50000), 10000
            if label == "Public institutions" and year == invalid_year:
                row[5] = "missing"
            rows.append(row)
    rows.extend([["Private institutions"] + [None] * 24,
                 ["2023-24"] + [99999] * 24])
    return pd.DataFrame(rows, columns=pd.MultiIndex.from_tuples(columns)).to_html(index=False)


def test_nces_parse_locates_public_section_and_keeps_latest_academic_year():
    from tuition import fetch_nces

    rows = fetch_nces.parse(_nces_html())
    assert len(rows) == 57
    assert rows[-1]["year"] == 2023
    assert rows[-1]["tuition_current_usd"] == 9872
    assert rows[-1]["constant_dollar_academic_year"] == "2023-24"
    assert "tuition_constant2022_usd" not in rows[-1]
    assert all(r["tuition_current_usd"] == 9872 for r in rows)


def test_nces_invalid_sources_preserve_saved_csv(tmp_path, monkeypatch):
    import pytest
    from tuition import fetch_nces

    path = tmp_path / "nces.csv"
    path.write_text("saved source data\n")
    monkeypatch.setattr(fetch_nces, "OUT_CSV", str(path))
    for html in [_nces_html(missing_year=2023), _nces_html(missing_year=2000),
                 _nces_html(invalid_year=2000), _nces_html(current_header="Room and board")]:
        monkeypatch.setattr(fetch_nces, "_load_html", lambda **kwargs: html)
        with pytest.raises(ValueError, match="NCES"):
            fetch_nces.main([])
        assert path.read_text() == "saved source data\n"


def test_current_nominal_cap_chart_is_not_truncated_by_missing_real_inputs(tmp_path, monkeypatch):
    from tuition import plot_history

    path = tmp_path / "history.csv"
    path.write_text(
        "region,year,nominal_local,real_2022_usd\n"
        "UK,2024,9250,11030\nUK,2025,9535,\nUK,2026,9790,\nUK,2099,10050,\n"
    )
    monkeypatch.setattr(config, "HISTORY_OUT_CSV", path)
    captured = []
    monkeypatch.setattr(plot_history, "save_chart",
                        lambda fig, *a, **k: captured.append(fig))
    plot_history.plot_nominal_cap(str(tmp_path / "cap.png"))
    axis = captured[0].axes[0]
    assert list(axis.lines[0].get_xdata()) == [2024, 2025, 2026]
    assert list(axis.lines[0].get_ydata()) == [9250, 9535, 9790]
    assert "£9,790 in 2026/27 (nominal pounds)" in axis.get_title()
    assert "not inflation-adjusted" in axis.get_ylabel()
    assert plot_history.load_history()["UK"] == [(2024, 11030)]


def test_real_snapshot_with_only_zero_median_eu_remains_readable(tmp_path, monkeypatch):
    rows = [
        {"country": country, "region": config.EU, "year": 2023,
         "annual_tuition_usd_real2022": value}
        for country, value in [("Germany", 0), ("Denmark", 0), ("France", 170)]
    ] + [
        {"country": country, "region": region, "year": year,
         "annual_tuition_usd_real2022": None}
        for country, region, year in [
            ("Italy", config.EU, 2023),
            ("United States", config.US, 2023), ("England", config.UK, 2023),
        ]
    ]
    captured = []
    monkeypatch.setattr(plot_tuition, "save_chart",
                        lambda fig, *a, **k: captured.append(fig))
    plot_tuition.plot_region_comparison(
        rows, "annual_tuition_usd_real2022", "constant 2022 USD", str(tmp_path / "real.png"))
    assert captured[0].axes[0].get_xlim()[0] == 0
    assert captured[0].axes[0].get_xlim()[1] > 170 / 3
    assert [text.get_text() for text in captured[0].axes[0].get_yticklabels()] == [
        "EU sample (3/27 countries)\n2023/24"
    ]
    note = " ".join(captured[0].texts[0].get_text().split())
    assert "Not plotted: Italy (2023), United States (2023), England (2023)" in note
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = captured[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    note_bounds = fig.texts[0].get_window_extent(renderer)
    assert note_bounds.x1 <= fig.bbox.x1
    assert note_bounds.y1 < fig.axes[0].xaxis.label.get_window_extent(renderer).y0


def test_tuition_country_bars_keep_country_colors_without_a_misleading_region_legend(monkeypatch, tmp_path):
    rows = [
        dict(country=country, region=region, year=year, annual_tuition_usd_real2022=value)
        for country, region, year, value in (
            ("England", config.UK, 2026, None), ("Germany", config.EU, 2023, 0),
            ("United States", config.US, 2025, 10000),
        )
    ]
    captured = []
    monkeypatch.setattr(plot_tuition, "save_chart", lambda fig, *a, **k: captured.append(fig))
    plot_tuition.plot_by_country(
        rows, "annual_tuition_usd_real2022", "constant 2022 USD", str(tmp_path / "real.png"),
    )
    from matplotlib.colors import to_rgba
    from vizstyle import country_color

    ax = captured[0].axes[0]
    assert ax.get_legend() is None
    assert [bar.get_facecolor() for bar in ax.patches] == [
        to_rgba(country_color("Germany")), to_rgba(country_color("US")),
    ]
    assert "EU sample (1/27 countries)" in captured[0].axes[0].get_title()
    assert "Not plotted: England (2026)" in " ".join(captured[0].texts[0].get_text().split())


def test_compact_tuition_ranking_stops_at_france_and_preserves_values_and_colors(tmp_path):
    import json
    from matplotlib.colors import to_rgba
    from unittest.mock import patch
    from vizstyle import country_color

    rows = [
        dict(country=country, region=region, year=2025, fx_year=2025, annual_tuition_usd=value)
        for country, region, value in (
            ("France", config.EU, 201.14),
            ("United Kingdom", config.UK, 12554.74),
            ("United States", config.US, 11950),
            ("Belgium", config.EU, 1307.39),
            ("Germany", config.EU, 0),
            ("Portugal", config.EU, 787.6),
            ("Sweden", config.EU, 150),
        )
    ]
    before = [dict(row) for row in rows]
    figures = []
    original = plot_tuition.save_chart

    def save(fig, *args, **kwargs):
        figures.append(fig)
        return original(fig, *args, **kwargs)

    path = tmp_path / "compact.png"
    with patch.object(plot_tuition, "save_chart", save):
        plot_tuition.plot_by_country(
            rows, "annual_tuition_usd", "US dollars", str(path), through_country="France",
        )
    assert rows == before
    ax = figures[0].axes[0]
    assert [text.get_text() for text in ax.get_yticklabels()] == [
        "France", "Portugal", "Belgium", "United States", "England (fee cap)",
    ]
    assert [bar.get_width() for bar in ax.patches] == [201.14, 787.6, 1307.39, 11950, 12554.74]
    assert [bar.get_facecolor() for bar in ax.patches][-3:] == [
        to_rgba(country_color("EU")), to_rgba(country_color("US")), to_rgba(country_color("UK")),
    ]
    data = json.loads(path.with_suffix(".json").read_text())
    assert [(point[2], point[3]) for series in data["series"] for point in series["points"]] == [
        ("France", "$201.14"), ("Portugal", "$787.6"), ("Belgium", "$1,307.39"),
        ("United States", "$11,950"), ("England (fee cap)", "$12,554.74"),
    ]
    footer = " ".join(figures[0].texts[-1].get_text().split())
    assert "lower-fee countries omitted, not missing" in footer
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(figures[0])
    canvas.draw()
    renderer = canvas.get_renderer()
    assert figures[0].texts[-1].get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0


def test_compact_tuition_ranking_rejects_missing_cutoff_country(tmp_path):
    import pytest

    rows = [dict(country="Germany", region=config.EU, year=2025, fx_year=2025, annual_tuition_usd=0)]
    with pytest.raises(ValueError, match="cutoff country"):
        plot_tuition.plot_by_country(
            rows, "annual_tuition_usd", "US dollars", str(tmp_path / "missing.png"),
            through_country="France",
        )
    assert not (tmp_path / "missing.png").exists()


def _common_fee_book():
    import pandas as pd
    from tuition import common_year

    codes = list(common_year.EU_CODES.values())
    columns = ["Annual fee amount (in euro)", "Education cycle", "Student category", "Student status", *codes]
    amounts = [
        ":" if code in ("BG", "HR", "LV", "RO") else 0 if code == "DE" else 100
        for code in codes
    ]
    frame = pd.DataFrame([
        ["Reference academic year: 2023/2024"],
        ["Annual fee amount (national currency)", *columns[1:]],
        ["Most common", "First cycle", "Home students", "Full-time", *([99999] * len(codes))],
        columns,
        ["Most common", "First cycle", "Home students", "Full-time", *amounts],
    ])
    return {
        common_year.SHEET: frame,
        "Eurostat data": pd.DataFrame([["Euro/ECU exchange rates"], [2023]]),
    }


def test_common_fee_source_uses_euro_block_and_preserves_genuine_missing_amounts():
    from tuition import common_year

    rows = common_year.parse_eurydice(_common_fee_book(), 2023, "https://eurydice.eacea.ec.europa.eu/data.xlsx")
    by_code = {row["iso3"]: row for row in rows}
    assert len(rows) == 27
    assert by_code["DEU"]["annual_tuition_local"] == 0
    assert by_code["FRA"]["annual_tuition_local"] == 100
    assert {row["iso3"] for row in rows if row["annual_tuition_local"] is None} == {
        "BGR", "HRV", "LVA", "ROU",
    }
    assert all(row["currency"] == "EUR" and row["year"] == 2023 for row in rows)
    assert "Flemish Community" in by_code["BEL"]["notes"]


def test_common_fee_source_rejects_wrong_academic_year_or_student_cohort():
    import pytest
    from tuition import common_year

    with pytest.raises(ValueError, match="reference academic year"):
        common_year.parse_eurydice(_common_fee_book(), 2025, "https://source")
    book = _common_fee_book()
    book[common_year.SHEET].iloc[-1, 2] = "International students"
    with pytest.raises(ValueError, match="home/full-time/first-cycle"):
        common_year.parse_eurydice(book, 2023, "https://source")
    book = _common_fee_book()
    book["Eurostat data"].iloc[1, 0] = 2022
    with pytest.raises(ValueError, match="publisher exchange-rate year"):
        common_year.parse_eurydice(book, 2023, "https://source")


def test_common_year_builder_matches_fee_year_fx_year_and_missing_country_counts():
    import pytest
    from tuition import common_year

    rows = common_year.parse_eurydice(_common_fee_book(), 2023, "https://source")
    rows += common_year.national_rows([
        dict(iso3="GBR", year=2023, nominal_local=9250, currency="GBP", source="cap", source_url="https://source"),
        dict(iso3="USA", year=2023, nominal_local=11310, currency="USD", source="fees", source_url="https://source"),
    ], 2023)
    fx = {
        ("DEU", 2023): dict(currency="EUR", fx_lcu_per_usd=.8, fx_year=2023),
        ("GBR", 2023): dict(currency="GBP", fx_lcu_per_usd=.5, fx_year=2023),
    }
    built = common_year.build(rows, fx, {2023: .9})
    summary = aggregate_by_region(built, "annual_tuition_usd")
    assert summary["EU"]["n"] == 23
    assert summary["EU"]["mean_annual"] == pytest.approx(22 * 125 / 23)
    assert summary["UK"]["median_annual"] == 18500
    assert summary["US"]["median_annual"] == 11310
    assert built[-2]["annual_tuition_usd_real2022"] == 16650
    assert all(row["fx_year"] == 2023 and row["academic_year"] == "2023/24" for row in built)
    fx["DEU", 2023]["fx_year"] = 2022
    with pytest.raises(ValueError, match="exact 2023"):
        common_year.build(rows, fx, {2023: .9})


def test_common_fee_source_resolves_reference_year_instead_of_download_publication_year():
    from tuition import common_year

    year, url = common_year.latest_workbook(
        '<a href="/sites/default/files/2025-04/Open%20data_2022_2023_0.xlsx">Old</a>'
        '<a href="/sites/default/files/2025-09/Open%20data_2023-2024.xlsx">Current</a>'
        '<a href="https://untrusted.invalid/Open%20data_2025-2026.xlsx">Other</a>'
    )
    assert year == 2023 and "2025-09" in url


def test_common_fee_refresh_preserves_reported_amounts_and_does_not_regress_the_year():
    import pytest
    from tuition import common_year

    rows = common_year.load()
    changed = [dict(row) for row in rows]
    lost = next(row for row in changed if row["iso3"] == "DEU")
    for field in ("annual_tuition_local", "annual_tuition_usd", "annual_tuition_usd_real2022"):
        lost[field] = None
    with pytest.raises(ValueError, match="previously reported"):
        common_year.validate(changed, rows)
    newer = [{**row, "year": 2024} for row in rows]
    with pytest.raises(ValueError, match="regress"):
        common_year.validate(rows, newer)


def test_region_plot_refuses_a_mixed_academic_year_or_nearby_year_exchange_rate(tmp_path):
    import pytest
    from tuition import common_year

    for column, value in (("year", "2026"), ("fx_year", "2022")):
        rows = common_year.load()
        rows[0][column] = value
        with pytest.raises(ValueError, match="common academic year|same year's exchange rates"):
            plot_tuition.plot_region_comparison(rows, "annual_tuition_usd", "US dollars", str(tmp_path / "bad.png"))
        assert not (tmp_path / "bad.png").exists()


def test_common_year_tuition_rejects_mixed_fee_years_and_fx_years():
    import pytest
    from tuition import common_year

    rows = common_year.load()
    year = int(rows[0]["year"]) + 1
    for column, value in (("year", str(year)), ("academic_year", f"{year}/{(year+1)%100:02d}"),
                          ("fx_year", str(year))):
        changed = [dict(row) for row in rows]
        changed[-1][column] = value
        with pytest.raises(ValueError, match="academic years|metadata"):
            common_year.validate(changed)


def test_compact_tuition_plot_itself_refuses_mixed_years(tmp_path):
    import pytest
    from tuition import common_year

    rows = common_year.load()
    rows[0]["year"] = "2026"
    with pytest.raises(ValueError, match="one academic year"):
        plot_tuition.plot_by_country(
            rows, "annual_tuition_usd", "US dollars", str(tmp_path / "mixed.png"),
            through_country="France",
        )


def test_primary_eurydice_selector_keeps_most_common_first_cycle_and_missing_values():
    import pandas as pd
    import pytest
    from tuition import common_year

    codes = list(common_year.EU_CODES.values())
    values = [None if code == "BG" else 0 if code == "DE" else 200 for code in codes]
    table = pd.DataFrame([
        ["Reference academic year: 2023/2024", *([None] * (3 + len(codes)))],
        ["Annual fee amount (in euro)", "Cycle", "Student", "Attendance", *codes],
        ["Maximum", "First cycle", "Home students", "Full-time", *([9999] * len(codes))],
        ["Most common", "Second cycle", "Home students", "Full-time", *([8888] * len(codes))],
        ["Most common", "First cycle", "Home students", "Full-time", *values],
    ])
    book = _common_fee_book()
    book[common_year.SHEET] = table
    rows = common_year.parse_eurydice(book, 2023, "https://example.test/data.xlsx")
    by_code = {row["iso3"]: row for row in rows}
    assert len(rows) == 27
    assert by_code["BGR"]["annual_tuition_local"] is None
    assert by_code["DEU"]["annual_tuition_local"] == 0
    assert by_code["FRA"]["annual_tuition_local"] == 200
    assert "Flemish" in by_code["BEL"]["notes"]
    with pytest.raises(ValueError, match="reference academic year"):
        common_year.parse_eurydice(book, 2025, "https://example.test/data.xlsx")
