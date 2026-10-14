"""Offline unit tests for the crime_data pipeline (no network required).

Run directly:  python tests/test_crime.py
Or with pytest: pytest tests/test_crime.py -q
"""

from __future__ import annotations

import sys
import io
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crime_data import charts, countries, csew, homicide, nations  # noqa: E402


def test_empty_fetch_preserves_saved_crime_data(monkeypatch, tmp_path):
    from crime_data import __main__ as cli

    path = tmp_path / "crime.csv"
    path.write_text("preserved source data\n")
    monkeypatch.setattr(cli, "CSEW_CSV", path)
    monkeypatch.setattr(csew, "build_rows", lambda: [])
    with pytest.raises(RuntimeError, match="Crime source returned no observations"):
        cli.main(["--sources", "csew", "--charts-dir", str(tmp_path)])
    assert path.read_text() == "preserved source data\n"


def test_country_mappings() -> None:
    assert countries.COUNTRIES[0].iso3 == countries.UK_ISO3 == "GBR"
    assert countries.group_for_iso3("GBR") == countries.UK
    assert countries.group_for_iso3("DEU") == countries.EU
    assert countries.group_for_iso3("USA") == countries.US
    assert countries.name_for_iso3("FRA") == "France"
    iso3s = countries.iso3_codes()
    assert len(iso3s) == len(set(iso3s)) == 29
    assert sum(1 for c in countries.COUNTRIES if c.group == countries.EU) == 27


def _synthetic_a1a() -> pd.DataFrame:
    """A tiny header-less frame shaped like ONS Table_A1a (2 periods x a few rows)."""
    return pd.DataFrame([
        ["Table A1a: Trends in incidents of CSEW headline crime (1,000s)", None, None],
        ["England and Wales, year ending December 1981 to 2002", None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        ["Offence group\n[note 5]", "Jan 1981 to Dec 1981", "Apr 2001 to Mar 2002"],
        ["VIOLENCE", 2063, 2551],
        ["    Violence with injury", 1226, 1507],
        ["ROBBERY", 164, 340],
        ["Unweighted base - number of people aged 16 and over", 9898, 32787],
        ["ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE [note 8]", 11303, 12500],
        ["    Fraud [note 9][note 10]", "[x]", "[x]"],
    ])


def test_csew_parser_basic() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    # 'Unweighted base' rows are dropped; '[x]' fraud cells are skipped.
    assert not any("unweighted base" in r["offence_group"].lower() for r in rows)
    assert not any(r["offence_group"].lower().startswith("fraud") for r in rows)
    # Note markers are stripped from labels.
    assert any(r["offence_group"] == "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
               for r in rows)
    assert all("[note" not in r["offence_group"] for r in rows)


def test_csew_period_and_years() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    violence = sorted((r for r in rows if r["offence_group"] == "VIOLENCE"),
                      key=lambda r: r["date"])
    assert [r["year"] for r in violence] == [1981, 2002]
    assert violence[0]["period"] == "Jan 1981 to Dec 1981"
    assert violence[0]["date"] == "1981-12-31"
    # Apr 2001 to Mar 2002 -> year ending 2002, period end 31 March.
    assert violence[1]["date"] == "2002-03-31"
    assert violence[1]["value"] == 2551.0
    assert violence[0]["region"] == "England and Wales"
    assert violence[0]["unit"] == "incidents (thousands)"
    assert "Crime Survey for England and Wales" in violence[0]["source"]


def test_csew_indent_level() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    top = next(r for r in rows if r["offence_group"] == "VIOLENCE")
    sub = next(r for r in rows if r["offence_group"] == "Violence with injury")
    assert top["level"] == 0
    assert sub["level"] == 1


def test_csew_disambiguates_burglary_subcategories_despite_source_indentation():
    df = pd.DataFrame([
        ["Offence group", "Apr 2025 to Mar 2026"],
        ["    Domestic burglary", 348],
        ["With entry", 206],
        ["            With loss", 105],
        ["            No loss", 101],
        ["Attempts", 142],
        ["Domestic burglary in a dwelling", 238],
        ["        With entry", 125],
        ["            With loss", 57],
        ["            No loss", 68],
        ["        Attempts", 113],
        ["    Domestic burglary in a non-connected building to a dwelling", 110],
        ["        With entry", 81],
        ["            With loss", 48],
        ["            No loss", 33],
        ["        Attempts", 29],
    ])
    rows = csew.build_rows(df)
    values = {r["offence_group"]: r["value"] for r in rows}
    assert len(values) == len(rows) == 15
    assert values["Domestic burglary: Attempts"] == 142
    assert values["Domestic burglary in a dwelling: Attempts"] == 113
    assert values["Domestic burglary in a non-connected building to a dwelling: Attempts"] == 29
    assert values["Domestic burglary in a dwelling: With loss"] == 57
    assert sum(r["value"] for r in rows) == sum(df.iloc[1:, 1])


def test_csew_rejects_unresolved_duplicate_offence_observations():
    df = pd.DataFrame([
        ["Offence group", "Apr 2025 to Mar 2026"],
        ["VIOLENCE", 989],
        ["VIOLENCE", 989],
    ])
    with pytest.raises(ValueError, match="duplicate CSEW offence observation"):
        csew.build_rows(df)


@pytest.mark.parametrize("chart", [
    charts.chart_csew_total, charts.chart_csew_21st_century, charts.chart_fraud_gap,
])
def test_csew_charts_do_not_bridge_missing_pandemic_observations(chart, monkeypatch, tmp_path):
    df = pd.DataFrame([
        {"offence_group": group, "date": f"{year}-03-31",
         "value": value, "source": "ONS"}
        for year, value in [(2019, 6000), (2020, 5500), (2023, 4400), (2024, 4500)]
        for group in [charts.TOTAL_EXCL, charts.TOTAL_INCL]
    ])
    figures = []
    monkeypatch.setattr(charts, "_save", lambda fig, *a: figures.append(fig))
    chart(df, tmp_path)
    fig = figures[0]
    try:
        ax = fig.axes[0]
        for line in ax.lines:
            if line.get_linestyle() == "None":
                continue
            dates = pd.to_datetime(line.get_xdata())
            assert not (dates.min() <= pd.Timestamp("2020-03-31")
                        and dates.max() >= pd.Timestamp("2023-03-31"))
        if chart is charts.chart_fraud_gap:
            from matplotlib.dates import date2num

            for collection in ax.collections:
                for path in collection.get_paths():
                    xs = path.vertices[:, 0]
                    assert not (xs.min() <= date2num(pd.Timestamp("2020-03-31"))
                                and xs.max() >= date2num(pd.Timestamp("2023-03-31")))
        assert any("2021 or 2022" in t.get_text() for t in fig.texts)
    finally:
        charts.plt.close(fig)


def test_csew_retains_irregular_pre_annual_survey_intervals():
    df = pd.DataFrame({"date": pd.to_datetime([
        "1981-12-31", "1983-12-31", "1987-12-31", "2002-03-31", "2003-03-31",
    ])})
    assert len(list(charts._csew_segments(df))) == 1


def test_homicide_parser(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = [
        {"pages": 1},
        [
            {"countryiso3code": "GBR", "date": "2020", "value": 1.1},
            {"countryiso3code": "GBR", "date": "2019", "value": None},   # skipped
            {"countryiso3code": "USA", "date": "2020", "value": 6.5},
            {"countryiso3code": "ZZZ", "date": "2020", "value": 9.9},    # not in set
        ],
    ]

    class _Resp:
        def raise_for_status(self):  # noqa: D401
            pass

        def json(self):
            return payload

    monkeypatch.setattr(homicide.requests, "get", lambda *a, **k: _Resp())
    rows = homicide.build_rows(2019, 2020, iso3s=["GBR", "USA"])
    assert len(rows) == 2
    by = {r["iso3"]: r for r in rows}
    assert by["GBR"]["value"] == 1.1
    assert by["GBR"]["metric"] == "homicide_rate_per_100k"
    assert by["GBR"]["unit"] == "per 100,000 population"
    assert "UNODC" in by["GBR"]["source"]
    assert "USA" in by


def test_ons_host_allowlist() -> None:
    for bad in ("https://evil.example.com/x.xlsx", "http://ons.gov.uk.evil.com/x"):
        try:
            csew._ensure_ons_host(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"expected rejection of {bad!r}")
    csew._ensure_ons_host("https://www.ons.gov.uk/file?uri=x")  # ok, no raise


@pytest.mark.parametrize("statuses", [
    (429, 200),
    (429, 429, 429, 429),
    (404,),
])
def test_ons_metadata_retries_rate_limits_but_surfaces_failures(monkeypatch, statuses):
    received = []
    responses = iter(statuses)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            self.send_response(next(responses))
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    monkeypatch.setattr(csew, "ONS_BASE", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(csew, "_ensure_ons_host", lambda url: None)
    monkeypatch.setattr(csew._RETRY_ADAPTER.max_retries, "backoff_factor", 0)
    try:
        if statuses[-1] == 200:
            assert csew._get_json("/dataset") == {"ok": True}
        else:
            with pytest.raises(csew.requests.HTTPError):
                csew._get_json("/dataset")
        assert received == ["/dataset/data"] * len(statuses)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_ons_retry_client_still_rejects_off_host_redirects(monkeypatch):
    received = []

    def redirect(url, **kwargs):
        received.append(url)
        assert kwargs["allow_redirects"] is False
        response = csew.requests.Response()
        response.status_code = 302
        response.headers["Location"] = "https://example.invalid/workbook.xlsx"
        return response

    monkeypatch.setattr(csew._SESSION, "get", redirect)
    url = "https://www.ons.gov.uk/file?uri=x"
    with pytest.raises(ValueError, match="untrusted host"):
        csew._ons_get(url, timeout=1)
    assert received == [url]


def test_download_workbook_accepts_current_sheet_name(monkeypatch) -> None:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _synthetic_a1a().to_excel(writer, sheet_name="Table A1a", header=False, index=False)

    class _Resp:
        content = buf.getvalue()

    monkeypatch.setattr(csew, "_ons_get", lambda *a, **k: _Resp())
    rows = csew.build_rows(csew.download_workbook("https://www.ons.gov.uk/file?uri=x"))
    assert any(r["year"] == 2002 for r in rows)


def test_21st_century_chart_filters_out_earlier_data() -> None:
    df = pd.DataFrame([
        {
            "offence_group": charts.TOTAL_EXCL,
            "date": "1995-12-31",
            "value": 19_786.0,
            "source": "Test source",
        },
        {
            "offence_group": charts.TOTAL_EXCL,
            "date": "2002-03-31",
            "value": 12_771.0,
            "source": "Test source",
        },
        {
            "offence_group": charts.TOTAL_EXCL,
            "date": "2024-03-31",
            "value": 4_589.0,
            "source": "Test source",
        },
    ])

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        path = charts.chart_csew_21st_century(df, out_dir)

        assert path == out_dir / "crime_csew_21st_century.png"
        assert path.is_file()


def test_fraud_gap_labels_combined_fraud_and_computer_misuse(monkeypatch) -> None:
    df = pd.DataFrame([
        {
            "offence_group": group,
            "date": f"{year}-03-31",
            "value": value,
            "source": "Test source",
        }
        for year, excl, incl in ((2017, 60, 100), (2026, 45, 100))
        for group, value in ((charts.TOTAL_EXCL, excl), (charts.TOTAL_INCL, incl))
    ])
    captured = {}

    def capture(fig, out_dir, filename):
        ax = fig.axes[0]
        captured["title"] = ax.get_title(loc="left")
        captured["labels"] = [text.get_text() for text in ax.texts]
        charts.plt.close(fig)
        return out_dir / filename

    monkeypatch.setattr(charts, "_save", capture)
    charts.chart_fraud_gap(df, Path("."))
    assert captured["title"] == "Fraud & computer misuse: 55% of headline crime (year ending March 2026)"
    assert "Including fraud &\ncomputer misuse  0.1M" in captured["labels"]
    assert "Excluding fraud &\ncomputer misuse  0.0M" in captured["labels"]


def test_fraud_gap_compares_matching_dates_and_handles_one_shared_period(monkeypatch):
    df = pd.DataFrame([
        {"offence_group": group, "date": date, "value": value, "source": "Test"}
        for group, date, value in (
            (charts.TOTAL_EXCL, "2024-03-31", 40),
            (charts.TOTAL_INCL, "2024-03-31", 100),
            (charts.TOTAL_INCL, "2025-03-31", 200),
        )
    ])
    captured = {}

    def capture(fig, out_dir, filename):
        ax = fig.axes[0]
        captured["title"] = ax.get_title(loc="left")
        captured["gap_date"] = next(
            text.xy[0] for text in ax.texts
            if "M fraud &" in text.get_text()
        )
        charts.plt.close(fig)
        return out_dir / filename

    monkeypatch.setattr(charts, "_save", capture)
    charts.chart_fraud_gap(df, Path("."))
    assert captured["title"] == "Fraud & computer misuse: 60% of headline crime (year ending March 2024)"
    assert captured["gap_date"] == pd.Timestamp("2024-03-31")


def test_homicide_financial_year_labels_use_end_year():
    for label, year in (
        ("1980-81", 1981), ("1999-00", 2000), ("2024/25", 2025),
        ("2024–25", 2025), ("2024-2025", 2025),
        ("Year ending March 2025", 2025), ("Mid-2024", 2024),
    ):
        assert nations._period_end_year(label) == year


@pytest.fixture
def scottish_homicide_answer():
    rows = "".join(
        f"<tr><td><p>{year - 1}-{year % 100:02d}</p></td><td><p>{year - 1900}</p></td></tr>"
        for year in range(2000, 2026)
    )
    return (
        "<main><h2>Question reference: S6W-43088</h2>"
        "<p>Homicide in Scotland 2024-25</p><table><tbody>"
        "<tr><td><p>Year</p></td><td><p>Total Victims</p></td></tr>"
        f"{rows}</tbody></table></main>"
    )


def test_scottish_homicide_reads_complete_official_victim_table(scottish_homicide_answer):
    counts = nations._extract_scotland_counts(scottish_homicide_answer)
    assert len(counts) == 26
    assert counts[2000] == 100
    assert counts[2025] == 125


@pytest.mark.parametrize(("old", "new"), [
    ("S6W-43088", "S6W-00000"),
    ("2024-25</p><table", "2023-24</p><table"),
    ("Total Victims", "Total Cases"),
    ("<tr><td><p>1999-00</p></td><td><p>100</p></td></tr>", ""),
    ("2000-01", "1999-00"),
    ("1999-00", "2000"),
    ("1999-00", "1998-00"),
    (">100</p>", ">-1</p>"),
    (">100</p>", ">1.5</p>"),
    (">100</p>", ">not available</p>"),
])
def test_scottish_homicide_rejects_wrong_or_incomplete_tables(
    scottish_homicide_answer, old, new,
):
    with pytest.raises(ValueError):
        nations._extract_scotland_counts(scottish_homicide_answer.replace(old, new))


def test_homicide_download_rejects_incomplete_responses_and_off_host_redirects(monkeypatch):
    response = nations.requests.Response()
    response.status_code = 202
    monkeypatch.setattr(nations.requests, "get", lambda *args, **kwargs: response)
    with pytest.raises(nations.requests.HTTPError, match="received 202"):
        nations._get(nations.SCOTLAND_ANSWER_URL, ("parliament.scot",))

    response.status_code = 302
    response.headers["Location"] = "https://example.invalid/table"
    with pytest.raises(ValueError, match="untrusted host"):
        nations._get(nations.SCOTLAND_ANSWER_URL, ("parliament.scot",))


def test_scottish_homicide_uses_population_within_financial_year():
    rows = nations._assemble_rows(
        england_wales_rates={},
        scotland_counts={2025: 45},
        northern_ireland_counts={2024: 12},
        scotland_population={2024: 5_000_000},
        northern_ireland_population={2023: 1_000_000, 2024: 2_000_000},
        start=2000,
    )
    by = {row["jurisdiction"]: row for row in rows}
    assert by[nations.SCOTLAND]["year"] == 2025
    assert by[nations.SCOTLAND]["value"] == 9.0
    assert by[nations.NORTHERN_IRELAND]["value"] == 6.0


def test_homicide_source_attribution_fits_below_period_note(monkeypatch, tmp_path):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    rows = nations._assemble_rows(
        england_wales_rates={2000: 12.5, 2025: 8.6},
        scotland_counts={2000: 123, 2025: 45},
        northern_ireland_counts={2000: 30, 2024: 18},
        scotland_population={1999: 5_000_000, 2024: 5_500_000},
        northern_ireland_population={2000: 1_500_000, 2024: 2_000_000},
        start=2000,
    )
    captured = {}
    save = charts._save

    def capture(fig, out_dir, filename, **kwargs):
        captured["figure"] = fig
        return save(fig, out_dir, filename, **kwargs)

    monkeypatch.setattr(charts, "_save", capture)
    charts.chart_homicide_nations(pd.DataFrame(rows), tmp_path)
    fig = captured["figure"]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    source = next(text for text in fig.texts if text.get_text().startswith("Source:"))
    period = next(text for text in fig.texts if text.get_text().startswith("Periods:"))
    source_box = source.get_window_extent(renderer)
    period_box = period.get_window_extent(renderer)
    assert source_box.y1 + 2 <= period_box.y0
    assert period_box.y1 + 2 <= min(
        tick.get_window_extent(renderer).y0
        for tick in fig.axes[0].get_xticklabels() if tick.get_visible()
    )
    assert source_box.x1 <= fig.bbox.x1
    assert source_box.y0 >= 0


def test_nation_homicide_rows_start_in_2000() -> None:
    rows = nations._assemble_rows(
        england_wales_rates={1999: 13.0, 2000: 12.5, 2001: 14.0},
        scotland_counts={1999: 100, 2000: 120},
        northern_ireland_counts={1999: 20, 2000: 30},
        scotland_population={1999: 5_000_000, 2000: 5_000_000},
        northern_ireland_population={1999: 1_500_000, 2000: 1_500_000},
        start=2000,
    )

    assert min(row["year"] for row in rows) == 2000
    assert {row["jurisdiction"] for row in rows} == {
        nations.ENGLAND_WALES,
        nations.SCOTLAND,
        nations.NORTHERN_IRELAND,
    }
    scotland = next(row for row in rows if row["jurisdiction"] == nations.SCOTLAND)
    assert scotland["value"] == 24.0


def _run() -> int:
    return int(pytest.main([__file__, "-q"]))


if __name__ == "__main__":
    raise SystemExit(_run())
