from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import pandas as pd
import pytest
import requests

from debt_data import charts, sources
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
    monkeypatch.setattr(Figure, "savefig", lambda fig, *args, **kwargs: figures.append(fig))
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
        source = fig.texts[-1]
        assert source.get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0


def test_borrowing_chart_does_not_connect_missing_recent_months(debt_frame, monkeypatch, tmp_path):
    missing = (
        debt_frame["metric"].eq(sources.YIELD_METRIC)
        & debt_frame["country"].eq("United Kingdom")
        & debt_frame["date"].eq(pd.Timestamp("2026-04-01"))
    )
    figures = []
    monkeypatch.setattr(Figure, "savefig", lambda fig, *args, **kwargs: figures.append(fig))
    charts.make_charts(debt_frame[~missing], tmp_path)
    uk = figures[1].axes[0].lines[0]
    assert pd.isna(uk.get_ydata()).sum() == 1
