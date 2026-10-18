from __future__ import annotations

import csv
import io
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import pandas as pd
import pytest
import requests

from debt_data import charts, interest, sources
from debt_data.__main__ import main


DEBT_CSV = (
    '"Title","PS: Net Debt (excluding public sector banks) as a % of GDP: NSA"\n'
    '"CDID","HF6X"\n"Source dataset ID","PUSF"\n"Unit","%"\n'
    '"1999 DEC","35.5"\n"2000","37.0"\n"2000 Q1","36.0"\n'
    '"2000 JAN","35.0"\n"2000 FEB","35.2"\n'
)


def _yield_html(country="Germany", series_id="IRLTLT01DEM156N", value="-0.5"):
    return (
        "<table>"
        f"<tr><th>Series ID</th><td>{series_id}</td></tr>"
        f"<tr><th>Title</th><td>10-Year Government Bond Yields for {country}</td></tr>"
        "<tr><th>Units</th><td>Percent</td></tr>"
        "<tr><th>Frequency</th><td>Monthly</td></tr>"
        "<tr><th>Source</th><td>Organization for Economic Co-operation and Development</td></tr>"
        "</table><table id='data-table-observations'>"
        "<tr><th>DATE</th><th>VALUE</th></tr>"
        f"<tr><td>2000-01-01</td><td>{value}</td></tr>"
        "<tr><td>2000-02-01</td><td>.</td></tr>"
        "<tr><td>2000-03-01</td><td>0</td></tr></table>"
    )


@pytest.fixture
def debt_frame():
    rows = []
    for date in pd.date_range("2000-01-01", "2026-08-01", freq="MS"):
        rows.append({
            "date": date, "country": "United Kingdom", "metric": sources.DEBT_METRIC,
            "value": 60 + (date.year - 2000), "unit": "percent of GDP",
            "source": "ONS", "series_id": "HF6X",
        })
        for index, (country, code) in enumerate(sources.YIELD_SERIES.items()):
            rows.append({
                "date": date, "country": country, "metric": sources.YIELD_METRIC,
                "value": 4 - index * 0.4, "unit": "percent per annum",
                "source": "OECD", "series_id": code,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def daily_frame():
    dates = pd.bdate_range("2000-01-04", "2026-10-12")
    return pd.DataFrame({
        "date": dates, "country": "United Kingdom", "metric": sources.DAILY_METRIC,
        "value": 4.5, "unit": "percent per annum", "source": "Bank of England",
        "series_id": sources.DAILY_SERIES,
    })


def test_daily_yield_parser_preserves_observation_dates_and_missing_days():
    frame = sources.parse_daily_yields(
        "DATE,IUDMNPY\n04 Jan 2000,-0.5\n05 Jan 2000,..\n06 Jan 2000,0\n"
    )
    assert frame["date"].tolist() == ["2000-01-04", "2000-01-06"]
    assert frame["value"].tolist() == [-0.5, 0]


@pytest.mark.parametrize("text", [
    "DATE,OTHER\n04 Jan 2000,4.5\n",
    "DATE,IUDMNPY\n04 Jan 2000,4.5\n04 Jan 2000,4.6\n",
    "DATE,IUDMNPY\n04 Jan 2000,nan\n",
    "DATE,IUDMNPY\n04 Jan 2000,4.5,extra\n",
])
def test_daily_yield_parser_rejects_wrong_series_and_invalid_observations(text):
    with pytest.raises(ValueError):
        sources.parse_daily_yields(text)


def test_daily_yield_validation_checks_freshness_and_preserves_history(daily_frame):
    today = pd.Timestamp("2026-10-14")
    sources.validate_daily(daily_frame, require_recent=True, as_of=today)
    with pytest.raises(ValueError, match="seven days"):
        sources.validate_daily(
            daily_frame, require_recent=True, as_of=pd.Timestamp("2026-10-22"),
        )
    with pytest.raises(ValueError, match="dates"):
        sources.validate_daily(daily_frame, as_of=pd.Timestamp("2026-10-09"))
    with pytest.raises(ValueError, match="previously published"):
        sources.validate_daily(daily_frame.iloc[:-1], previous=daily_frame, as_of=today)
    with pytest.raises(ValueError, match="historical"):
        sources.validate_daily(daily_frame[daily_frame["date"].dt.year != 2005], as_of=today)


def test_failed_daily_download_preserves_both_saved_inputs(
    debt_frame, daily_frame, budget_frame, monkeypatch, tmp_path,
):
    monthly_csv, daily_csv = tmp_path / "monthly.csv", tmp_path / "daily.csv"
    debt_frame.to_csv(monthly_csv, index=False)
    daily_frame.to_csv(daily_csv, index=False)
    saved = monthly_csv.read_bytes(), daily_csv.read_bytes()
    monkeypatch.setattr(sources, "fetch", lambda: debt_frame)
    monkeypatch.setattr(interest, "fetch", lambda: budget_frame)

    def fail():
        raise requests.ConnectionError("daily yield source unavailable")

    monkeypatch.setattr(sources, "fetch_daily", fail)
    with pytest.raises(requests.ConnectionError, match="daily yield"):
        main(["--csv", str(monthly_csv), "--daily-csv", str(daily_csv),
              "--interest-csv", str(tmp_path / "interest.csv"),
              "--out", str(tmp_path / "charts")])
    assert (monthly_csv.read_bytes(), daily_csv.read_bytes()) == saved
    assert not (tmp_path / "charts").exists()


def test_debt_parser_selects_monthly_net_debt_percent_not_annual_or_quarterly_values():
    rows = sources.parse_debt(DEBT_CSV)
    assert [row["date"] for row in rows] == ["2000-01-01", "2000-02-01"]
    assert [row["value"] for row in rows] == [35.0, 35.2]
    assert all(row["metric"] == sources.DEBT_METRIC for row in rows)


@pytest.mark.parametrize("text", [
    DEBT_CSV.replace("HF6X", "OTHER"),
    DEBT_CSV.replace('"Unit","%"', '"Unit","GBP million"'),
    DEBT_CSV + '"2000 JAN","36.0"\n',
    DEBT_CSV.replace('"35.0"', '"NaN"'),
    DEBT_CSV.replace('"35.0"', '"not numeric"'),
])
def test_debt_parser_rejects_wrong_series_units_duplicates_and_invalid_numbers(text):
    with pytest.raises(ValueError):
        sources.parse_debt(text)


def test_yield_parser_preserves_negative_and_zero_rates_without_filling_missing_months():
    rows = sources.parse_yields(_yield_html(), "Germany", "IRLTLT01DEM156N")
    assert [row["date"] for row in rows] == ["2000-01-01", "2000-03-01"]
    assert [row["value"] for row in rows] == [-0.5, 0]


@pytest.mark.parametrize("html", [
    _yield_html().replace("IRLTLT01DEM156N", "OTHER"),
    _yield_html().replace("Percent", "Index"),
    _yield_html().replace("Monthly", "Daily"),
    _yield_html().replace("10-Year", "3-Month"),
    _yield_html().replace("2000-03-01", "2000-01-01"),
    _yield_html(value="inf"),
])
def test_yield_parser_rejects_incompatible_or_invalid_observations(html):
    with pytest.raises(ValueError):
        sources.parse_yields(html, "Germany", "IRLTLT01DEM156N")


def test_validation_rejects_lost_historical_or_previously_published_months(debt_frame):
    assert len(sources.validate(debt_frame)) == len(debt_frame)
    with pytest.raises(ValueError, match="historical coverage"):
        sources.validate(debt_frame.drop(index=0))
    with pytest.raises(ValueError, match="previously published"):
        sources.validate(debt_frame.iloc[:-1], previous=debt_frame)


def test_failed_yield_download_does_not_replace_saved_debt_inputs(monkeypatch, tmp_path):
    csv = tmp_path / "debt.csv"
    csv.write_text("previous saved data")
    # The saved frame is read before the fresh source download starts.
    monkeypatch.setattr(pd, "read_csv", lambda _: pd.DataFrame())

    def get_text(url, **kwargs):
        if url == sources.ONS_CSV:
            return DEBT_CSV
        raise requests.ConnectionError("yield source unavailable")

    monkeypatch.setattr(sources, "get_text", get_text)
    with pytest.raises(requests.ConnectionError, match="yield source unavailable"):
        main(["--csv", str(csv), "--out", str(tmp_path / "charts")])
    assert csv.read_text() == "previous saved data"
    assert not (tmp_path / "charts").exists()


def test_debt_charts_use_year_ticks_and_separate_debt_stock_from_yields(
    debt_frame, monkeypatch, tmp_path,
):
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    paths = charts.make_charts(debt_frame, tmp_path)
    assert [Path(path).name for path in paths] == [
        "uk_public_debt_pct_gdp.png", "government_borrowing_costs.png",
    ]
    assert [len(fig.axes[0].lines) for fig in figures] == [1, 6]
    assert "net debt" in figures[0]._suptitle.get_text()
    assert "borrowing rates" in figures[1]._suptitle.get_text()
    for fig in figures:
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        ax = fig.axes[0]
        assert all(label.get_text().isdigit() for label in ax.get_xticklabels())
        assert max(int(label.get_text()) for label in ax.get_xticklabels()) <= 2026
        assert ax.get_xlim()[1] - ax.dataLim.x1 < 100
        source = fig.texts[-1]
        assert source.get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0


def test_borrowing_chart_does_not_connect_missing_recent_months(debt_frame, monkeypatch, tmp_path):
    missing = (
        debt_frame["metric"].eq(sources.YIELD_METRIC)
        & debt_frame["country"].eq("United Kingdom")
        & debt_frame["date"].eq(pd.Timestamp("2026-04-01"))
    )
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    charts.make_charts(debt_frame[~missing], tmp_path)
    uk = figures[1].axes[0].lines[0]
    assert pd.isna(uk.get_ydata()).sum() == 1


def test_daily_chart_is_separate_recent_and_does_not_fill_missing_days(
    debt_frame, daily_frame, monkeypatch, tmp_path,
):
    daily_frame = daily_frame[daily_frame["date"] != pd.Timestamp("2026-10-08")]
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    paths = charts.make_charts(debt_frame, tmp_path, daily=daily_frame)
    assert paths[-1].name == "uk_borrowing_costs_daily.png"
    fig = figures[-1]
    ax = fig.axes[0]
    assert len(ax.lines) == 1
    assert pd.isna(ax.lines[0].get_ydata()).sum() == 1
    assert "12 Oct 2026" in fig.texts[1].get_text()
    assert "not spliced" in fig.texts[-1].get_text()
    assert ax.get_xlim()[1] - ax.dataLim.x1 <= 14
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[-1].get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0


def _interest_csv(records):
    fields = [
        "DATAFLOW", *interest.DIMENSIONS, "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT",
        "CURRENCY", "CONSOLIDATION", "OBS_STATUS", "OBS_STATUS_2", "CONF_STATUS",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        code, transaction = record.get("REF_AREA", "GBR"), record.get("TRANSACTION", "D41")
        row = {key: value.split("+")[0] for key, value in interest.DIMENSIONS.items()}
        row.update(
            DATAFLOW="OECD.SDD.NAD:DSD_NASEC10@DF_TABLE12(1.1)",
            REF_AREA=code, TRANSACTION=transaction, TIME_PERIOD=2023,
            OBS_VALUE=10 if transaction == "D41" else 200,
            UNIT_MULT=6, CURRENCY=interest.CURRENCIES.get(code, "GBP"),
            CONSOLIDATION="C" if transaction == "D41" else "P",
            OBS_STATUS="A", CONF_STATUS="F",
        )
        row.update(record)
        writer.writerow(row)
    return output.getvalue()


def _parse_interest(text):
    return interest.parse(
        text, end=2025, retrieved="2026-10-18T16:00:00Z", source_url="source",
        flow=interest.FLOW + ",1.1",
    )


def _federal_html(component, *, changes=None, records=None):
    series, title = interest.US_SERIES[component]
    metadata = {
        "Series ID": series, "Title": title, "Source": "U.S. Bureau of Economic Analysis",
        "Release": "Gross Domestic Product", "Frequency": "Annual",
        "Units": "Billions of Dollars", "Seasonal Adjustment": "Not Seasonally Adjusted",
        "Last Updated": "2026-09-30 7:59 AM CDT",
    }
    metadata.update(changes or {})
    records = records if records is not None else [
        (year, 10 if component == "interest" else 200) for year in range(2000, 2026)
    ]
    return (
        "<table>" + "".join(f"<tr><th>{key}</th><td>{value}</td></tr>"
                           for key, value in metadata.items())
        + "</table><table id='data-table-observations'><tr><th>DATE</th><th>VALUE</th></tr>"
        + "".join(f"<tr><td>{year}-01-01</td><td>{value}</td></tr>" for year, value in records)
        + "</table>"
    )


@pytest.fixture
def budget_frame(monkeypatch):
    records = [
        dict(REF_AREA=code, TIME_PERIOD=year, TRANSACTION=transaction)
        for code in interest.COUNTRIES if code != "USA"
        for year in range(2000, interest.BASELINE_END[code] + 1)
        for transaction in ("D41", "OTE")
    ]

    def download(url, **kwargs):
        if url.startswith(interest.BASE):
            return _interest_csv(records)
        component = next(key for key, (series, _) in interest.US_SERIES.items() if url.endswith(series))
        return _federal_html(component)

    monkeypatch.setattr(interest, "get_text", download)
    monkeypatch.setattr(interest, "get_json", lambda *args, **kwargs: {"data": {"dataflows": [{
        "agencyID": "OECD.SDD.NAD", "id": "DSD_NASEC10@DF_TABLE12", "version": "1.1",
    }]}})
    return interest.fetch()


def test_interest_ratio_uses_matched_national_currency_units_and_keeps_source_flags():
    text = _interest_csv([
        dict(OBS_VALUE=12_000, UNIT_MULT=6, OBS_STATUS="P"),
        dict(TRANSACTION="OTE", OBS_VALUE=1000, UNIT_MULT=9, OBS_STATUS="E"),
    ])
    frame = _parse_interest(text)
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["interest"] == 12_000_000_000
    assert row["expenditure"] == 1_000_000_000_000
    assert row["value"] == pytest.approx(1.2)
    assert row["status"] == "E;P"
    assert row["currency"] == "GBP"
    assert ".GBR.S1311._Z.D.D41." in row["interest_series_id"]
    assert ".GBR.S1311._Z.D.OTE." in row["expenditure_series_id"]
    fractional = _parse_interest(_interest_csv([
        dict(REF_AREA="FRA", OBS_VALUE="66635.9"),
        dict(REF_AREA="FRA", TRANSACTION="OTE", OBS_VALUE=1000, UNIT_MULT=9),
    ]))
    assert fractional.iloc[0]["interest"] == 66_635_900_000


@pytest.mark.parametrize("change", [
    {"SECTOR": "S13"}, {"SECTOR": "S1312"}, {"SECTOR": "S1313"},
    {"FREQ": "Q"}, {"TRANSACTION": "D4"}, {"ACCOUNTING_ENTRY": "C"},
    {"PRICE_BASE": "Q"}, {"UNIT_MEASURE": "USD"}, {"CURRENCY": "USD"},
    {"CONSOLIDATION": "N"}, {"OBS_VALUE": "nan"}, {"OBS_VALUE": "-1"},
    {"UNIT_MULT": ""}, {"TIME_PERIOD": 2026}, {"OBS_STATUS": "UNKNOWN"},
])
def test_interest_parser_rejects_incompatible_governments_units_and_invalid_values(change):
    with pytest.raises(ValueError):
        _parse_interest(_interest_csv([change]))


def test_interest_parser_does_not_invent_components_or_publish_forecasts():
    for records in (
        [{}, {}],
        [{}, dict(TRANSACTION="OTE", TIME_PERIOD=2022)],
        [{}, dict(TRANSACTION="OTE", OBS_VALUE=0)],
    ):
        with pytest.raises(ValueError):
            _parse_interest(_interest_csv(records))
    forecasts = [
        dict(TRANSACTION=transaction, OBS_STATUS="F") for transaction in ("D41", "OTE")
    ]
    assert _parse_interest(_interest_csv(forecasts)).empty


def test_interest_validation_protects_published_coverage_and_source_calculation(budget_frame):
    with pytest.raises(ValueError, match="annual coverage"):
        interest.validate(budget_frame.iloc[1:])
    corrupt = budget_frame.copy()
    corrupt.loc[0, "value"] += .1
    with pytest.raises(ValueError, match="numerator/denominator"):
        interest.validate(corrupt)
    previous = budget_frame.copy()
    previous.loc[previous.index[-1], "year"] = 2026
    with pytest.raises(ValueError, match="previously published"):
        interest.validate(budget_frame, previous=previous)
    mixed = budget_frame.copy()
    mixed.loc[0, "source_vintage"] = "OECD Economic Outlook 119"
    with pytest.raises(ValueError, match="provenance"):
        interest.validate(mixed)
    broad = budget_frame.copy()
    broad.loc[0, "expenditure_series_id"] = broad.loc[0, "expenditure_series_id"].replace(".S1311.", ".S13.")
    with pytest.raises(ValueError, match="S1311"):
        interest.validate(broad)
    broad = budget_frame.copy()
    broad.loc[broad["iso3"] == "USA", "expenditure_series_id"] = "W068RC1A027NBEA"
    with pytest.raises(ValueError, match="federal-only"):
        interest.validate(broad)


def test_interest_refresh_discovers_new_oecd_version_without_splicing_us_components(
    budget_frame, monkeypatch,
):
    monkeypatch.setattr(interest, "get_json", lambda *args, **kwargs: {"data": {"dataflows": [{
        "agencyID": "OECD.SDD.NAD", "id": "DSD_NASEC10@DF_TABLE12", "version": "1.2",
    }]}})
    records = [
        dict(REF_AREA=row.iso3, TIME_PERIOD=row.year, TRANSACTION=transaction)
        for row in budget_frame.itertuples() if row.iso3 != "USA"
        for transaction in ("D41", "OTE")
    ]
    original_download = interest.get_text

    def download(url, **kwargs):
        if not url.startswith(interest.BASE):
            return original_download(url, **kwargs)
        assert ",1.2/" in url
        assert kwargs["params"]["endPeriod"] == str(pd.Timestamp.now(tz="UTC").year - 1)
        return _interest_csv(records).replace("DF_TABLE12(1.1)", "DF_TABLE12(1.2)")

    monkeypatch.setattr(interest, "get_text", download)
    frame = interest.fetch()
    european = frame[frame["iso3"] != "USA"]
    assert european["interest_series_id"].str.contains(",1.2/", regex=False).all()
    assert european["expenditure_series_id"].str.contains(",1.2/", regex=False).all()
    us = frame[frame["iso3"] == "USA"]
    assert us["source_vintage"].eq("BEA NIPA (FRED updated 2026-09-30)").all()
    assert set(us["year"]) == set(range(2000, 2026))


@pytest.mark.parametrize("changes", [
    {"Title": "Government total expenditures"}, {"Series ID": "W068RC1A027NBEA"},
    {"Frequency": "Quarterly"}, {"Units": "Percent of GDP"},
    {"Seasonal Adjustment": "Seasonally Adjusted Annual Rate"},
])
def test_federal_parser_rejects_general_government_and_incompatible_series(changes):
    with pytest.raises(ValueError, match="metadata"):
        interest.parse_federal(_federal_html("expenditure", changes=changes), "expenditure", end=2025)


def test_federal_parser_scales_annual_dollars_and_rejects_duplicate_years():
    values, updated = interest.parse_federal(
        _federal_html("interest", records=[(2024, "1117.544"), (2025, "1217.730")]),
        "interest", end=2025,
    )
    assert values == {2024: 1_117_544_000_000, 2025: 1_217_730_000_000}
    assert updated == "2026-09-30"
    with pytest.raises(ValueError, match="Duplicate"):
        interest.parse_federal(
            _federal_html("interest", records=[(2025, 10), (2025, 20)]),
            "interest", end=2025,
        )


@pytest.mark.parametrize("problem", ["missing-year", "mixed-release"])
def test_federal_refresh_rejects_unmatched_components_and_release_dates(
    budget_frame, monkeypatch, problem,
):
    original = interest.get_text

    def download(url, **kwargs):
        if not url.endswith(interest.US_SERIES["expenditure"][0]):
            return original(url, **kwargs)
        if problem == "mixed-release":
            return _federal_html("expenditure", changes={"Last Updated": "2026-09-29 7:51 AM CDT"})
        return _federal_html("expenditure", records=[(year, 200) for year in range(2000, 2025)])

    monkeypatch.setattr(interest, "get_text", download)
    with pytest.raises(ValueError, match="Unmatched|different release dates"):
        interest.fetch()


def test_failed_interest_source_preserves_saved_inputs_and_does_not_render(
    debt_frame, daily_frame, budget_frame, monkeypatch, tmp_path,
):
    monthly_csv, daily_csv, budget_csv = (
        tmp_path / name for name in ("monthly.csv", "daily.csv", "interest.csv")
    )
    for path, frame in ((monthly_csv, debt_frame), (daily_csv, daily_frame), (budget_csv, budget_frame)):
        frame.to_csv(path, index=False)
    saved = [path.read_bytes() for path in (monthly_csv, daily_csv, budget_csv)]
    monkeypatch.setattr(sources, "fetch", lambda: debt_frame)

    def fail():
        raise requests.ConnectionError("interest expenditure source unavailable")

    monkeypatch.setattr(interest, "fetch", fail)
    with pytest.raises(requests.ConnectionError, match="interest expenditure"):
        main(["--csv", str(monthly_csv), "--daily-csv", str(daily_csv),
              "--interest-csv", str(budget_csv), "--out", str(tmp_path / "charts")])
    assert [path.read_bytes() for path in (monthly_csv, daily_csv, budget_csv)] == saved
    assert not (tmp_path / "charts").exists()


def test_interest_chart_has_all_peers_correct_units_and_dated_latest_points(
    debt_frame, budget_frame, monkeypatch, tmp_path,
):
    figures = []
    marked = budget_frame["iso3"].eq("GBR") & budget_frame["year"].eq(2018)
    budget_frame.loc[marked, "status"] = "B;P"
    budget_frame.loc[budget_frame.index[-1], "status"] = "P"
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    paths = charts.make_charts(debt_frame, tmp_path, budget=budget_frame)
    assert paths[-1].name == "debt_interest_budget_share.png"
    fig, ax = figures[-1], figures[-1].axes[0]
    assert {line.get_label() for line in ax.lines} == set(charts.COLORS)
    assert "central/federal government spending" in ax.get_ylabel()
    assert ax.get_xlabel() == "Calendar year"
    assert ax.get_ylim()[0] == 0
    labels = [text.get_text().strip() for text in ax.texts]
    assert any("United States 5.0%\n  2025" == label for label in labels)
    assert any("United Kingdom 5.0%\n  2025" == label for label in labels)
    assert not any(label.endswith(" P") for label in labels)
    footer = fig.texts[-1].get_text().replace("\n", " ")
    assert "Latest observation flags:" in footer
    assert "central government S1311" in footer
    assert "BEA federal national accounts" in footer
    assert "does not add state/local budgets" in footer
    assert "principal repayments are excluded" in footer
    assert "accounting conventions" in footer
    assert "Central/federal government only" in fig.texts[1].get_text()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[-1].get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0
