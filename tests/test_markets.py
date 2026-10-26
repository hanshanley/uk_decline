"""Offline unit tests for the markets_data pipeline (no network required).

Run directly:  python tests/test_markets.py
Or with pytest: pytest tests/test_markets.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from markets_data import charts, combine, markets, regions, worldbank  # noqa: E402


def test_cpi_adjusted_market_captions_are_explicit_and_clear_the_axis(monkeypatch, tmp_path):
    import pandas as pd
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    rows = [markets.make_row(regions.name_for_code(code), code, year,
                             "market_cap_usd_real", value)
            for code, value in (("GBR", 2e12), ("USA", 20e12)) for year in (2020, 2024)]
    frame = pd.DataFrame(rows)
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: captured.append(fig))
    charts.chart_metric(frame, "market_cap_usd_real", tmp_path)
    charts.chart_uk_us_ratio(frame, "market_cap_usd_real", tmp_path)
    for fig in captured:
        FigureCanvasAgg(fig).draw()
        renderer = fig.canvas.get_renderer()
        assert "us-cpi adjusted" in fig.axes[0].get_title().lower()
        note = fig.texts[0]
        assert "exchange-rate movements" in " ".join(note.get_text().split())
        assert note.get_window_extent(renderer).y1 < fig.axes[0].xaxis.label.get_window_extent(renderer).y0


def test_market_legends_date_each_country_without_changing_export_labels(monkeypatch, tmp_path):
    import pandas as pd

    frame = pd.DataFrame([
        markets.make_row(regions.name_for_code(code), code, year, "market_cap_usd", 1e12)
        for code, years in (("GBR", (2020, 2022)), ("USA", (2019, 2024))) for year in years
    ])
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: captured.append(fig))
    charts.chart_metric(frame, "market_cap_usd", tmp_path)
    ax = captured[0].axes[0]
    assert [text.get_text() for text in ax.get_legend().get_texts()] == [
        "United Kingdom (2020\u20132022)", "United States (2019\u20132024)",
    ]
    assert [line.get_label() for line in ax.lines] == ["United Kingdom", "United States"]


def test_china_listing_coverage_break_is_separate_and_keeps_actual_points(monkeypatch, tmp_path):
    import pandas as pd
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from vizstyle.hover import observations

    frame = pd.DataFrame([
        markets.make_row(regions.name_for_code(code), code, year, "listed_domestic_companies", value)
        for code, values in (("GBR", (2000, 1900, 1800)), ("USA", (4000, 4100, 4200)),
                             ("EUU", (5000, 5100, 5200)), ("JPN", (3000, 3100, 3200)),
                             ("CHN", (3584, 12730, 12341)))
        for year, value in zip((2018, 2019, 2020), values)
    ])
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: captured.append(fig))
    charts.chart_metric(frame, "listed_domestic_companies", tmp_path)
    fig = captured[0]
    left, right = fig.axes
    assert {line.get_label() for line in left.lines} == {
        "United Kingdom", "United States", "European Union", "Japan",
    }
    assert [line.get_label() for line in right.lines] == ["China"]
    china = right.lines[0]
    assert pd.isna(china.get_ydata()[list(china.get_xdata()).index(2018.5)])
    assert [segment.tolist() for collection in right.collections for segment in collection.get_segments()] == [
        [[2018., 3584.], [2019., 12730.]],
    ]
    points = [(series["label"], point[2]) for series in observations(fig, dpi=200)
              for point in series["points"]]
    assert len(points) == len(set(points)) == 15
    assert all(year in {"2018", "2019", "2020"} for _, year in points)
    assert "Not like-for-like" in " ".join(t.get_text() for t in right.texts)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    bounds = fig.legends[0].get_window_extent(canvas.get_renderer())
    assert not any(bounds.overlaps(ax.bbox) for ax in fig.axes)
    assert not bounds.overlaps(fig._suptitle.get_window_extent(canvas.get_renderer()))
    assert all((bounds.y0 - ax.title.get_window_extent(canvas.get_renderer()).y1)
               * 72 / fig.dpi >= 5 for ax in fig.axes)


def _lse_workbook(sheet, month, year, rows):
    import io
    import openpyxl

    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = sheet
    ws.append([None, f"{month} {year}"])
    if sheet == "AIM since launch":
        ws.append([None, "Year", "Number of Companies"])
        ws.append([None, None, "UK", None, "International", None, "Total"])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    return buffer


@pytest.fixture
def lse_catalogue(monkeypatch):
    from markets_data import lse_factsheets as lse

    def catalogue(market):
        return {
            (year, month): (
                f"{lse.BASE}/{lse.MARKETS[market]}/"
                f"{market} factsheet {lse.calendar.month_name[month]} {year}.xlsx"
            ).replace(" ", "%20")
            for year in range(2018, 2027) for month in range(1, 13)
        }

    monkeypatch.setattr(lse, "_factsheet_catalogue", catalogue)


def test_lse_annual_and_partial_year_rows_preserve_dates_and_both_sources(monkeypatch, tmp_path, lse_catalogue):
    import csv
    from datetime import date
    from markets_data import lse_factsheets as lse

    class Today(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 13)

    monkeypatch.setattr(lse, "date", Today)
    sources = {}
    for year, month, uk, international in (
        (2024, "December", 855, 183),
        (2025, "December", 776, 150),
        (2026, "July", 757, 147),
    ):
        sources[lse._factsheet_url("Main Market", year, month)] = _lse_workbook(
            "Summary", month, year, [
                [None, "Year", "Number of Companies"],
                [None, None, "UK", "International", None, "Total"],
                [None, year, uk, international, None, uk + international],
            ],
        )
    aim_url = lse._factsheet_url("AIM", 2026, "July")
    sources[aim_url] = _lse_workbook("AIM since launch", "July", 2026, [
        [None, "2024", "558", None, "61", None, "619"],
        [None, "2025", "530", None, "89", None, "619"],
        [None, "2026", "511", None, "87", None, "598"],
        [None, "Month", None, "New Issues"],
        [None, "Year", None, "Turnover Value", None, None, "Number of Trades"],
        [None, "2025", "999", None, "999", None, "1998"],
    ])
    requested = []

    def download(url):
        requested.append(url)
        return sources[url]

    monkeypatch.setattr(lse, "_download", download)
    path = lse.write_csv(tmp_path / "lse.csv", 2024, 2025, "2026-07")
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    uk = [row for row in rows if row["metric"] == "lse_companies_uk"]
    total = [row for row in rows if row["metric"] == "lse_companies_total"]
    assert [int(row["value"]) for row in uk] == [1413, 1306, 1268]
    assert [int(row["value"]) for row in total] == [1657, 1545, 1502]
    assert [row["date"] for row in uk] == ["2024-12-31", "2025-12-31", "2026-07-31"]
    assert all(row["aim_source_url"] == aim_url for row in rows)
    assert all(row["source_url"] in requested and "%20" in row["source_url"] for row in rows)
    assert all(row["source_accessed"] == "2026-10-13" for row in rows)
    assert len(requested) == 4


def test_lse_discovers_latest_common_completed_month_without_probing_urls(monkeypatch):
    from datetime import date
    from markets_data import lse_factsheets as lse

    class Today(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 15)

    monkeypatch.setattr(lse, "date", Today)
    monkeypatch.setattr(lse, "_factsheet_catalogue", lambda market: {
        (2026, month): "published-link"
        for month in ((7, 8, 10, 11) if market == "Main Market" else (7, 10, 11))
    })
    monkeypatch.setattr(lse, "_download", lambda url: pytest.fail("must not probe guessed URLs"))
    assert lse.latest_available_month() == "2026-07"


def test_lse_catalogue_uses_migrated_links_and_revision_filenames(monkeypatch):
    import requests
    from markets_data import lse_factsheets as lse

    requested = []
    link = f"{lse.BASE}/aim/AIM%20factsheet%20April%202026_1.xlsx"

    def get(url, **kwargs):
        requested.append(url)
        response = requests.Response()
        response.url = url
        response.status_code = 200
        response.json = lambda: {"Data": [
            {"displayTitle": "AIM Issuers by Country", "fileType": "xlsx"},
            {"displayTitle": "AIM factsheet April 2026.xlsx", "fileType": "xlsx", "downloadLink": link},
            {"displayTitle": "AIM factsheet March 2026.pdf", "fileType": "pdf"},
        ]}
        return response

    lse._factsheet_catalogue.cache_clear()
    monkeypatch.setattr(lse.requests, "get", get)
    try:
        assert lse._factsheet_url("AIM", 2026, "April") == link
        assert lse._factsheet_url("AIM", 2026, "April") == link
        assert requested == [f"{lse.BASE}/aim/latest.json", f"{lse.BASE}/aim/historic.json"]
        with pytest.raises(ValueError, match="not published"):
            lse._factsheet_url("AIM", 2026, "September")
    finally:
        lse._factsheet_catalogue.cache_clear()


@pytest.mark.parametrize("status", [403, 503])
def test_lse_catalogue_and_published_download_errors_are_not_hidden(monkeypatch, status):
    import requests
    from markets_data import lse_factsheets as lse

    def get(url, **kwargs):
        response = requests.Response()
        response.url = url
        response.status_code = status
        return response

    lse._factsheet_catalogue.cache_clear()
    monkeypatch.setattr(lse.requests, "get", get)
    try:
        with pytest.raises(requests.HTTPError):
            lse.latest_available_month()
        with pytest.raises(requests.HTTPError):
            lse._download(f"{lse.BASE}/aim/published.xlsx")
    finally:
        lse._factsheet_catalogue.cache_clear()


def test_lse_discovery_rejects_catalogues_without_a_recent_common_month(monkeypatch):
    from markets_data import lse_factsheets as lse

    monkeypatch.setattr(lse, "_factsheet_catalogue", lambda market: {})
    with pytest.raises(ValueError, match="no common completed month"):
        lse.latest_available_month()


def test_lse_removed_2022_archive_preserves_original_provenance_only(monkeypatch):
    from markets_data import lse_factsheets as lse

    monkeypatch.setattr(lse, "_factsheet_catalogue", lambda market: {
        (2023, 12): f"{lse.BASE}/{lse.MARKETS[market]}/published.xlsx",
    })
    monkeypatch.setattr(lse, "aim_history", lambda *args: {2023: (600, 100)})
    fetched = []

    def main_market(year, month):
        fetched.append((year, month))
        return 900, 200

    monkeypatch.setattr(lse, "main_market_year", main_market)
    rows = lse.build_rows(2022, 2023)
    old = [row for row in rows if row["year"] == 2022]
    assert {row["metric"]: row["value"] for row in old} == {
        "lse_companies_uk": 1619, "lse_companies_total": 1922,
    }
    assert all(row["source_accessed"] == "2026-10-16" for row in old)
    assert all("/sites/default/files/reports/" in row["source_url"] for row in old)
    assert fetched == [(2023, "December")]
    assert all(row["source_accessed"] == lse.date.today().isoformat()
               for row in rows if row["year"] == 2023)


def test_lse_restored_2022_archive_is_downloaded_again(monkeypatch, lse_catalogue):
    from markets_data import lse_factsheets as lse

    monkeypatch.setattr(lse, "aim_history", lambda *args: {2022: (600, 100)})
    fetched = []

    def main_market(year, month):
        fetched.append((year, month))
        return 900, 200

    monkeypatch.setattr(lse, "main_market_year", main_market)
    rows = lse.build_rows(2022, 2022)
    assert fetched == [(2022, "December")]
    assert {row["metric"]: row["value"] for row in rows} == {
        "lse_companies_uk": 1500, "lse_companies_total": 1800,
    }
    assert all(row["source_accessed"] == lse.date.today().isoformat() for row in rows)


def test_lse_refresh_cannot_replace_a_newer_month_with_an_older_snapshot(monkeypatch, tmp_path):
    import pytest
    from markets_data import lse_factsheets as lse

    path = tmp_path / "lse.csv"
    path.write_text("date\n2026-07-31\n")
    monkeypatch.setattr(lse, "build_rows", lambda *args: [{"date": "2025-12-31"}])
    with pytest.raises(ValueError, match="lose the latest"):
        lse.write_csv(path)
    assert path.read_text() == "date\n2026-07-31\n"


def test_lse_discovery_crosses_new_year_when_december_is_not_published(monkeypatch):
    from datetime import date
    from markets_data import lse_factsheets as lse

    class Today(date):
        @classmethod
        def today(cls):
            return cls(2027, 1, 15)

    monkeypatch.setattr(lse, "date", Today)
    monkeypatch.setattr(lse, "_factsheet_catalogue", lambda market: {
        (2026, 11): "published-link",
    })
    assert lse.latest_available_month() == "2026-11"


def test_lse_bad_main_market_counts_do_not_become_zero(monkeypatch, lse_catalogue):
    import pytest
    from markets_data import lse_factsheets as lse

    for international, total in ((None, 776), ("-", 776), (-1, 775), (1.5, 777.5), (150, 999)):
        monkeypatch.setattr(lse, "_download", lambda url: _lse_workbook(
            "Summary", "December", 2025, [
                [None, "Year", "Number of Companies"],
                [None, None, "UK", "International", None, "Total"],
                [None, 2025, 776, international, None, total],
            ],
        ))
        with pytest.raises(ValueError, match="counts"):
            lse.main_market_year(2025)


def test_lse_wrong_factsheet_month_is_rejected(monkeypatch, lse_catalogue):
    import pytest
    from markets_data import lse_factsheets as lse

    monkeypatch.setattr(lse, "_download", lambda url: _lse_workbook(
        "Summary", "June", 2026, [],
    ))
    with pytest.raises(ValueError, match="does not identify July 2026"):
        lse.main_market_year(2026, "July")


def test_lse_duplicate_and_missing_aim_counts_are_rejected(monkeypatch, lse_catalogue):
    import pytest
    from markets_data import lse_factsheets as lse

    row = [None, "2025", "530", None, "89", None, "619"]
    monkeypatch.setattr(lse, "_download", lambda url: _lse_workbook(
        "AIM since launch", "December", 2025, [row, row],
    ))
    with pytest.raises(ValueError, match="duplicate"):
        lse.aim_history(2025)
    row[4] = None
    monkeypatch.setattr(lse, "_download", lambda url: _lse_workbook(
        "AIM since launch", "December", 2025, [row],
    ))
    with pytest.raises(ValueError, match="missing or invalid"):
        lse.aim_history(2025)


def test_lse_missing_requested_year_preserves_saved_data(monkeypatch, tmp_path):
    import pytest
    from markets_data import lse_factsheets as lse

    monkeypatch.setattr(lse, "aim_history", lambda *args: {2025: (530, 89)})
    monkeypatch.setattr(lse, "main_market_year", lambda *args: (776, 150))
    path = tmp_path / "lse.csv"
    path.write_text("preserved observations\n")
    with pytest.raises(ValueError, match="2024.*row not found"):
        lse.write_csv(path, 2024, 2025)
    assert path.read_text() == "preserved observations\n"
    monkeypatch.setattr(lse, "build_rows", lambda *args: [])
    with pytest.raises(RuntimeError, match="no company counts"):
        lse.write_csv(path)
    assert path.read_text() == "preserved observations\n"


def test_lse_rejects_old_definition_and_invalid_snapshot_range(monkeypatch):
    import pytest
    from datetime import date
    from markets_data import lse_factsheets as lse

    class Today(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 13)

    monkeypatch.setattr(lse, "date", Today)
    for start, end, latest in (
        (2017, 2025, None), (2025, 2024, None), (2018, 2026, None),
        (2018, 2025, "2025-12"), (2018, 2025, "2026-10"), (2018, 2025, "2027-01"),
        (2018, 2025, "2026-13"), (2018, 2025, "2026-7"),
    ):
        with pytest.raises(ValueError):
            lse.build_rows(start, end, latest)


def test_lse_chart_uses_only_uk_series_and_discloses_partial_year(monkeypatch, tmp_path):
    import pandas as pd

    source = pd.DataFrame([
        {"region": "United Kingdom", "year": year, "date": date, "metric": metric, "value": value}
        for year, date, metric, value in (
            (2025, "2025-12-31", "lse_companies_uk", 1306),
            (2026, "2026-07-31", "lse_companies_uk", 1268),
            (2026, "2026-07-31", "lse_companies_total", 1502),
        )
    ])
    seen = []

    def save(fig, out_dir, name):
        ax = fig.axes[0]
        seen.append(list(ax.lines[0].get_ydata()))
        assert "31 July 2026" in " ".join(text.get_text() for text in ax.texts)
        caption = " ".join(" ".join(text.get_text().split()) for text in fig.texts)
        assert "not the World Bank / World Federation of Exchanges definition" in caption
        return tmp_path / name

    monkeypatch.setattr(charts, "_save", save)
    charts.chart_lse_companies(source, tmp_path)
    assert seen == [[1306, 1268]]


def test_empty_fetch_preserves_saved_market_outputs(monkeypatch, tmp_path):
    import pytest

    monkeypatch.setattr(combine, "fetch_all", lambda *args: ([], None))
    paths = [tmp_path / name for name in ("long.csv", "wide.csv", "manifest.json")]
    for path in paths:
        path.write_text("preserved source data\n")
    with pytest.raises(RuntimeError, match="Market sources returned no observations"):
        combine.build(path=paths[0], wide_path=paths[1], manifest_path=paths[2])
    assert all(path.read_text() == "preserved source data\n" for path in paths)


def test_metric_indicator_mapping() -> None:
    # Every metric maps to a World Bank indicator and back.
    assert markets.METRICS["market_cap_usd"].wb_indicator == "CM.MKT.LCAP.CD"
    assert markets.BY_INDICATOR["CM.MKT.LCAP.CD"] == "market_cap_usd"
    assert markets.BY_INDICATOR["CM.MKT.LCAP.GD.ZS"] == "market_cap_pct_gdp"
    assert markets.BY_INDICATOR["CM.MKT.LDOM.NO"] == "listed_domestic_companies"
    # Units are derived from the metric id by make_row.
    row = markets.make_row("United Kingdom", "GBR", 2020, "market_cap_usd", 3.2e12)
    assert row["unit"] == "current US$"
    assert set(row) == set(markets.ROW_FIELDS)


def test_regions_core_and_colours() -> None:
    core = regions.codes(core_only=True)
    assert core == ["GBR", "USA"]
    assert "WLD" in regions.codes()
    assert regions.name_for_code("USA") == "United States"
    # Every region has a stable chart colour.
    for code in regions.codes():
        assert code in regions.COLOURS


def test_worldbank_parse_paged(monkeypatch) -> None:
    # Two-page World Bank payload; nulls are dropped, values coerced to float.
    pages = {
        1: [
            {"pages": 2},
            [
                {"countryiso3code": "GBR", "date": "2020", "value": 3.2e12,
                 "country": {"id": "GB", "value": "United Kingdom"}},
                {"countryiso3code": "USA", "date": "2020", "value": None,
                 "country": {"id": "US", "value": "United States"}},
            ],
        ],
        2: [
            {"pages": 2},
            [
                {"countryiso3code": "USA", "date": "2020", "value": 40e12,
                 "country": {"id": "US", "value": "United States"}},
            ],
        ],
    }

    def fake_get_json(url, params=None, timeout=60):
        return pages[params["page"]]

    monkeypatch.setattr(worldbank, "get_json", fake_get_json)
    rows = worldbank.fetch(2020, 2020, codes=["GBR", "USA"],
                           indicators=["CM.MKT.LCAP.CD"])
    by_code = {r["region_code"]: r for r in rows}
    assert set(by_code) == {"GBR", "USA"}  # null USA on page 1 dropped
    assert by_code["GBR"]["value"] == 3.2e12
    assert by_code["GBR"]["metric"] == "market_cap_usd"
    assert by_code["USA"]["value"] == 40e12


def test_deflate_to_real() -> None:
    # Nominal market cap in two years; CPI 100 (2010) -> 200 (2020), base = 2020.
    nominal = [
        markets.make_row("United States", "USA", 2010, "market_cap_usd", 10e12),
        markets.make_row("United States", "USA", 2020, "market_cap_usd", 40e12),
        markets.make_row("United Kingdom", "GBR", 2010, "market_cap_usd", 2e12),
        # a non-USD metric must be ignored by the deflator
        markets.make_row("United States", "USA", 2020, "market_cap_pct_gdp", 200.0),
    ]
    cpi = {2010: 100.0, 2020: 200.0}
    real, base_year = markets.deflate_to_real(nominal, cpi)
    assert base_year == 2020
    by_key = {(r["region_code"], r["year"]): r for r in real}
    assert all(r["metric"] == "market_cap_usd_real" for r in real)
    assert all("US CPI" in r["source"] for r in real)
    assert all(r["unit"] == "constant 2020 US$" for r in real)
    # 2020 is the base year -> real == nominal.
    assert by_key[("USA", 2020)]["value"] == 40e12
    # 2010 dollars scaled up by 200/100 = 2x.
    assert by_key[("USA", 2010)]["value"] == 20e12
    assert by_key[("GBR", 2010)]["value"] == 4e12
    # pct_gdp row was not deflated.
    assert ("USA", 2020) in by_key and len(real) == 3


def test_deflate_missing_cpi_year_skipped() -> None:
    # A data year with no CPI observation must be dropped, not fabricated.
    nominal = [
        markets.make_row("United States", "USA", 2024, "market_cap_usd", 60e12),
        markets.make_row("United States", "USA", 2025, "market_cap_usd", 68e12),
    ]
    cpi = {2024: 140.0}  # 2025 absent
    real, base_year = markets.deflate_to_real(nominal, cpi)
    assert base_year == 2024
    years = {r["year"] for r in real}
    assert years == {2024}  # 2025 skipped


def test_to_wide_shape() -> None:
    rows = [
        markets.make_row("United Kingdom", "GBR", 2020, "market_cap_usd", 3.2e12),
        markets.make_row("United Kingdom", "GBR", 2020, "market_cap_pct_gdp", 120.0),
        markets.make_row("United States", "USA", 2020, "market_cap_usd", 40e12),
    ]
    df = combine.to_frame(rows)
    wide = combine.to_wide(df)
    assert list(wide.columns) == ["region", "region_code", "year", *combine.METRIC_ORDER]
    uk = wide[wide["region_code"] == "GBR"].iloc[0]
    assert uk["market_cap_usd"] == 3.2e12
    assert uk["market_cap_pct_gdp"] == 120.0
    us = wide[wide["region_code"] == "USA"].iloc[0]
    # Missing metric for the US row is null, not an error.
    import pandas as pd
    assert pd.isna(us["market_cap_pct_gdp"])


def test_chart_series_breaks_across_missing_years() -> None:
    import pandas as pd

    series = pd.Series([10.0, 20.0], index=[2014, 2021])
    continuous = charts._with_year_gaps(series)
    assert list(continuous.index) == list(range(2014, 2022))
    assert pd.isna(continuous.loc[2015])
    assert pd.isna(continuous.loc[2020])


def test_filtered_market_history_keeps_original_constant_dollar_base(tmp_path, monkeypatch):
    import pandas as pd
    from markets_data import summary

    nominal = [
        markets.make_row("United States", "USA", 2010, "market_cap_usd", 10e12),
        markets.make_row("United States", "USA", 2020, "market_cap_usd", 40e12),
    ]
    real, _ = markets.deflate_to_real(nominal, {2010: 100, 2020: 200})
    subset = pd.DataFrame(real).query("year == 2010")
    result = summary.build_summary(subset, tmp_path / "summary.md").read_text()
    assert "constant 2020 US$" in result
    assert "constant 2010 US$" not in result
    assert "accessed" not in result
    assert "accessed" not in charts._source_note("market_cap_usd_real")
    units = []

    def save(fig, out_dir, name):
        units.append(fig.axes[0].get_ylabel())
        return tmp_path / name

    monkeypatch.setattr(charts, "_save", save)
    charts.chart_metric(subset, "market_cap_usd_real", tmp_path)
    assert units == ["constant 2020 US$"]


def test_offline_market_plot_preserves_saved_large_value_precision(tmp_path, monkeypatch):
    import pandas as pd
    from markets_data import charts

    value = 9568188789479.037
    path = tmp_path / "markets.csv"
    pd.DataFrame([
        markets.make_row("United States", "USA", 2016, "market_cap_usd_real", value),
        markets.make_row("United States", "USA", 2017, "market_cap_usd_real", value + 1),
    ]).to_csv(path, index=False)
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: figures.append(fig))
    charts.make_charts(path, tmp_path)
    assert figures[0].axes[0].lines[0].get_ydata()[0] == value


def _run() -> int:
    import pytest

    return pytest.main([str(Path(__file__).resolve()), "-q"])


if __name__ == "__main__":
    raise SystemExit(_run())
