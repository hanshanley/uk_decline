from __future__ import annotations

import csv
from io import StringIO

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import pytest
import requests

from unemployment_data import charts, sources
from unemployment_data.__main__ import main


def _csv(metric, dates):
    series_id, _, title = sources.SERIES[metric]
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerows([
        ["Title", title], ["CDID", series_id], ["Source dataset ID", "LMS"],
        ["Unit", "%"], ["Release date", "15-09-2026"],
        ["2025", "99"], ["2025 Q1", "98"],
    ])
    value = 5 if metric == "unemployment_rate" else 15
    writer.writerows([[date.strftime("%Y %b").upper(), value] for date in dates])
    return stream.getvalue()


@pytest.fixture
def unemployment_frame():
    dates = pd.date_range("2000-01-01", "2026-06-01", freq="MS")
    return pd.concat([
        sources.parse_series(_csv(metric, dates), metric)
        for metric in sources.SERIES
    ], ignore_index=True)


def test_parser_uses_centre_month_for_full_period_and_ignores_annual_quarterly_rows():
    frame = sources.parse_series(
        _csv("unemployment_rate", pd.to_datetime(["2026-01-01", "2026-06-01"])),
        "unemployment_rate",
    )
    assert frame["value"].tolist() == [5, 5]
    assert frame["period_start"].tolist() == [
        pd.Timestamp("2025-12-01"), pd.Timestamp("2026-05-01"),
    ]
    assert frame["period_end"].tolist() == [
        pd.Timestamp("2026-02-28"), pd.Timestamp("2026-07-31"),
    ]
    assert charts.period_label(frame.iloc[0]["period_start"], frame.iloc[0]["period_end"]) == (
        "Dec 2025-Feb 2026"
    )
    assert charts.period_label(frame.iloc[1]["period_start"], frame.iloc[1]["period_end"]) == (
        "May-Jul 2026"
    )


@pytest.mark.parametrize(("old", "new"), [
    ("MGSX", "OTHER"),
    ('Unit,%', 'Unit,GBP'),
    ('dataset ID,LMS', 'dataset ID,PUSF'),
    ("seasonally adjusted", "not seasonally adjusted"),
])
def test_parser_rejects_changed_source_metadata(old, new):
    text = _csv("unemployment_rate", [pd.Timestamp("2026-06-01")])
    assert old in text
    with pytest.raises(ValueError, match="Unexpected ONS"):
        sources.parse_series(text.replace(old, new), "unemployment_rate")


def test_parser_rejects_duplicate_observations():
    text = _csv("unemployment_rate", [pd.Timestamp("2026-06-01")] * 2)
    with pytest.raises(ValueError, match="duplicate"):
        sources.parse_series(text, "unemployment_rate")


@pytest.mark.parametrize(("column", "value"), [
    ("value", float("nan")),
    ("value", float("inf")),
    ("value", -1),
    ("value", 101),
    ("age_group", "15-24"),
    ("seasonal_adjustment", "Not seasonally adjusted"),
    ("period_start", pd.Timestamp("2026-06-01")),
])
def test_validation_rejects_invalid_rates_definitions_and_periods(unemployment_frame, column, value):
    unemployment_frame.loc[0, column] = value
    with pytest.raises(ValueError):
        sources.validate(unemployment_frame)


def test_validation_preserves_baseline_and_previously_published_months(unemployment_frame):
    frame = sources.validate(unemployment_frame)
    with pytest.raises(ValueError, match="2000-2025"):
        sources.validate(frame[frame["date"] != "2005-01-01"])
    reduced = frame[frame["date"] != "2026-03-01"]
    assert len(sources.validate(reduced)) == len(frame) - 2
    with pytest.raises(ValueError, match="previously published"):
        sources.validate(reduced, previous=frame)
    with pytest.raises(ValueError, match="Duplicate"):
        sources.validate(pd.concat([frame, frame.iloc[:1]]))


def test_validation_requires_matching_releases_and_latest_periods(unemployment_frame):
    youth = unemployment_frame["metric"] == "youth_unemployment_rate"
    changed = unemployment_frame.copy()
    changed.loc[youth, "release_date"] = pd.Timestamp("2026-08-18")
    with pytest.raises(ValueError, match="same ONS release"):
        sources.validate(changed)
    latest_youth = youth & (unemployment_frame["date"] == "2026-06-01")
    with pytest.raises(ValueError, match="different latest periods"):
        sources.validate(unemployment_frame.loc[~latest_youth])


def test_live_freshness_check_does_not_prevent_offline_reconstruction(unemployment_frame):
    today = pd.Timestamp("2027-01-15")
    sources.validate(unemployment_frame, as_of=today)
    with pytest.raises(ValueError, match="90 days"):
        sources.validate(unemployment_frame, as_of=today, require_recent=True)
    with pytest.raises(ValueError, match="release dates"):
        sources.validate(unemployment_frame, as_of=pd.Timestamp("2026-09-01"))


def test_failed_youth_download_preserves_saved_input(unemployment_frame, monkeypatch, tmp_path):
    path = tmp_path / "unemployment.csv"
    unemployment_frame.to_csv(path, index=False)
    before = path.read_bytes()

    def download(url, *, params, timeout):
        if "/mgsx/" in params["uri"]:
            dates = unemployment_frame.loc[
                unemployment_frame["metric"] == "unemployment_rate", "date",
            ]
            return _csv("unemployment_rate", dates)
        assert "/mgwy/" in params["uri"]
        raise requests.ConnectionError("ONS youth source unavailable")

    monkeypatch.setattr(sources, "get_text", download)
    with pytest.raises(requests.ConnectionError, match="ONS youth source unavailable"):
        main(["--csv", str(path), "--out", str(tmp_path / "charts")])
    assert path.read_bytes() == before
    assert not (tmp_path / "charts").exists()


def test_offline_cli_uses_saved_data_without_fetching_or_replacing_it(
    unemployment_frame, monkeypatch, tmp_path,
):
    path = tmp_path / "saved.csv"
    unemployment_frame.to_csv(path, index=False)
    before = path.read_bytes()

    def unexpected_fetch():
        pytest.fail("Offline reconstruction fetched a live source")

    captured = []
    monkeypatch.setattr(sources, "fetch", unexpected_fetch)
    monkeypatch.setattr(charts, "make_charts", lambda frame, out: captured.append(frame) or [])
    assert main(["--from-csv", str(path), "--out", str(tmp_path / "charts")]) == 0
    assert len(captured[0]) == len(unemployment_frame)
    assert path.read_bytes() == before


def test_rendered_charts_keep_missing_months_and_separate_text(
    unemployment_frame, monkeypatch, tmp_path,
):
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    frame = unemployment_frame[unemployment_frame["date"] != "2026-03-01"]
    outputs = charts.make_charts(frame, tmp_path)
    assert [path.name for path in outputs] == [
        "uk_unemployment_comparison.png", "uk_unemployment.png", "uk_youth_unemployment.png",
    ]
    for index, fig in enumerate(figures):
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        ax = fig.axes[0]
        assert ax.get_ylim()[0] == 0
        assert len(ax.lines) == (2 if index == 0 else 1)
        for line in ax.lines:
            assert np.isnan(line.get_ydata()).sum() == 1
        subtitle = next(text for text in fig.texts if "seasonally adjusted" in text.get_text())
        latest = next(text for text in fig.texts if text.get_text().startswith("Latest: "))
        source = next(text for text in fig.texts if text.get_text().startswith("Source: "))
        assert "May-Jul 2026" in latest.get_text()
        assert "Office for National Statistics" in source.get_text()
        if index == 0:
            assert [line.get_label() for line in ax.lines] == ["Overall (16+)", "Youth (16-24)"]
            assert ax.lines[0].get_color() != ax.lines[1].get_color()
            assert "Overall: 5.0%" in latest.get_text()
            assert "Youth: 15.0%" in latest.get_text()
            for line, expected in zip(ax.lines, (5, 15)):
                assert np.all(line.get_ydata()[np.isfinite(line.get_ydata())] == expected)
            assert "overall includes young people" in source.get_text()
            legend_box = ax.get_legend().get_window_extent(renderer)
            assert legend_box.y1 <= ax.get_window_extent(renderer).y1
            assert legend_box.x1 <= ax.get_window_extent(renderer).x1
        title_box = fig._suptitle.get_window_extent(renderer)
        subtitle_box = subtitle.get_window_extent(renderer)
        latest_box = latest.get_window_extent(renderer)
        source_box = source.get_window_extent(renderer)
        assert title_box.y0 > subtitle_box.y1
        assert subtitle_box.y0 > latest_box.y1
        assert latest_box.y0 > ax.get_window_extent(renderer).y1
        assert source_box.y1 < ax.xaxis.label.get_window_extent(renderer).y0
        for box in (title_box, subtitle_box, latest_box, source_box):
            assert 0 <= box.x0 < box.x1 <= fig.bbox.width
