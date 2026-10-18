from __future__ import annotations

import csv
from io import StringIO
import json

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import pytest
import requests

from unemployment_data import charts, references, sources
from unemployment_data.__main__ import main
from vizstyle import ACCENT, MUTED, TEXT


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


@pytest.fixture
def reference_payload():
    dates = pd.date_range("2000-01-01", "2026-08-01", freq="MS").strftime("%Y-%m").tolist()
    codes = {
        "freq": ["M"], "s_adj": ["SA"], "age": ["TOTAL", "Y_LT25"],
        "unit": ["PC_ACT"], "sex": ["T"], "geo": ["EU27_2020", "US"], "time": dates,
    }
    return {
        "id": list(codes), "size": [len(values) for values in codes.values()],
        "dimension": {
            key: {"category": {"index": {code: i for i, code in enumerate(values)}}}
            for key, values in codes.items()
        },
        "updated": "2026-10-08T11:00:00+0200",
        "value": {
            str((age * 2 + geo) * len(dates) + month): value
            for age, values in enumerate(((6, 4), (15, 9)))
            for geo, value in enumerate(values)
            for month, date in enumerate(dates)
            if geo != 1 or date != "2025-10"
        },
    }


@pytest.fixture
def reference_frame(reference_payload):
    return references.validate(references.parse(reference_payload))


def test_reference_parser_preserves_aggregate_definitions_and_missing_source_values(reference_payload):
    reference_payload["status"] = {"0": "p"}
    frame = references.validate(references.parse(reference_payload))
    assert set(zip(frame["country"], frame["metric"], frame["age_group"])) == {
        ("EU", "unemployment_rate", "15-74"), ("EU", "youth_unemployment_rate", "15-24"),
        ("US", "unemployment_rate", "16+"), ("US", "youth_unemployment_rate", "16-24"),
    }
    assert frame.loc[(frame["country"] == "EU") & (frame["date"] == "2000-01-01"), "status"].tolist() == ["p", ""]
    assert not ((frame["country"] == "US") & (frame["date"] == "2025-10-01")).any()
    assert frame["dataset_updated"].eq(reference_payload["updated"]).all()
    assert frame.loc[frame["country"] == "EU", "series_id"].str.endswith(".EU27_2020").all()


def test_reference_parser_rejects_wrong_adjustment_and_dimensions(reference_payload):
    reference_payload["dimension"]["s_adj"]["category"]["index"] = {"NSA": 0}
    with pytest.raises(ValueError, match="Unexpected Eurostat unemployment series"):
        references.parse(reference_payload)
    reference_payload["id"].remove("s_adj")
    with pytest.raises(ValueError, match="dimensions"):
        references.parse(reference_payload)


@pytest.mark.parametrize(("column", "value"), [
    ("value", float("nan")), ("value", float("inf")), ("value", -1), ("value", 101),
    ("age_group", "16-24"), ("country", "Euro area"),
    ("seasonal_adjustment", "Not seasonally adjusted"), ("series_id", "une_rt_m.OTHER"),
    ("date", pd.Timestamp("2026-08-02")),
])
def test_reference_validation_rejects_wrong_values_and_definitions(reference_frame, column, value):
    reference_frame.loc[0, column] = value
    with pytest.raises(ValueError):
        references.validate(reference_frame)


def test_reference_validation_preserves_each_country_history_and_checks_freshness(reference_frame):
    with pytest.raises(ValueError, match="required unemployment reference history"):
        references.validate(reference_frame[reference_frame["date"] != "2005-01-01"])
    with pytest.raises(ValueError, match="Duplicate"):
        references.validate(pd.concat([reference_frame, reference_frame.iloc[:1]]))
    reduced = reference_frame[reference_frame["date"] != "2026-03-01"]
    references.validate(reduced)
    with pytest.raises(ValueError, match="previously published"):
        references.validate(reduced, previous=reference_frame)
    references.validate(reference_frame, as_of=pd.Timestamp("2027-01-15"))
    with pytest.raises(ValueError, match="90 days"):
        references.validate(reference_frame, as_of=pd.Timestamp("2027-01-15"), require_recent=True)
    with pytest.raises(ValueError, match="dates"):
        references.validate(reference_frame, as_of=pd.Timestamp("2026-10-01"))
    stale = reference_frame[reference_frame["date"] < "2026-01-01"]
    with pytest.raises(ValueError, match="120 days"):
        references.validate(stale, as_of=pd.Timestamp("2026-10-15"), require_recent=True)


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
    unemployment_frame, reference_frame, monkeypatch, tmp_path,
):
    path = tmp_path / "saved.csv"
    unemployment_frame.to_csv(path, index=False)
    before = path.read_bytes()
    reference_path = tmp_path / "references.csv"
    reference_frame.to_csv(reference_path, index=False)
    references_before = reference_path.read_bytes()

    def unexpected_fetch():
        pytest.fail("Offline reconstruction fetched a live source")

    captured = []
    monkeypatch.setattr(sources, "fetch", unexpected_fetch)
    monkeypatch.setattr(references, "fetch", unexpected_fetch)
    monkeypatch.setattr(charts, "make_charts", lambda frame, out, peers: captured.append((frame, peers)) or [])
    assert main([
        "--from-csv", str(path), "--references", str(reference_path),
        "--out", str(tmp_path / "charts"),
    ]) == 0
    assert len(captured[0][0]) == len(unemployment_frame)
    assert len(captured[0][1]) == len(reference_frame)
    assert path.read_bytes() == before
    assert reference_path.read_bytes() == references_before


def test_failed_reference_download_preserves_both_saved_tables(
    unemployment_frame, reference_frame, monkeypatch, tmp_path,
):
    path, reference_path = tmp_path / "uk.csv", tmp_path / "references.csv"
    unemployment_frame.to_csv(path, index=False)
    reference_frame.to_csv(reference_path, index=False)
    before = path.read_bytes(), reference_path.read_bytes()
    monkeypatch.setattr(sources, "fetch", lambda: unemployment_frame)

    def failed_fetch():
        raise requests.ConnectionError("Eurostat unavailable")

    monkeypatch.setattr(references, "fetch", failed_fetch)
    with pytest.raises(requests.ConnectionError, match="Eurostat unavailable"):
        main([
            "--csv", str(path), "--references", str(reference_path),
            "--out", str(tmp_path / "charts"),
        ])
    assert (path.read_bytes(), reference_path.read_bytes()) == before
    assert not (tmp_path / "charts").exists()


def test_saved_hover_data_has_three_series_with_only_actual_source_observations(
    unemployment_frame, reference_frame, tmp_path,
):
    outputs = charts.make_charts(unemployment_frame, tmp_path, reference_frame)
    for path, metric in zip(outputs, sources.SERIES):
        data = json.loads(path.with_suffix(".json").read_text())
        assert len(data["series"]) == 3
        for series, country in zip(data["series"], ("UK", "EU", "US")):
            source = unemployment_frame if country == "UK" else reference_frame
            expected = source.loc[
                (source["country"] == country) & (source["metric"] == metric),
            ].sort_values("date")
            assert [(point[2], point[3]) for point in series["points"]] == [
                (row.date.strftime("%Y-%m-%d"), f"{row.value:g}%")
                for row in expected.itertuples()
            ]


def test_rendered_charts_keep_missing_months_and_separate_text(
    unemployment_frame, reference_frame, monkeypatch, tmp_path,
):
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: figures.append(fig))
    frame = unemployment_frame[unemployment_frame["date"] != "2026-03-01"]
    reference_frame = reference_frame.loc[
        ~((reference_frame["country"] == "EU") & (reference_frame["date"] == "2026-03-01"))
    ]
    outputs = charts.make_charts(frame, tmp_path, reference_frame)
    assert [path.name for path in outputs] == [
        "uk_unemployment.png", "uk_youth_unemployment.png",
    ]
    for index, fig in enumerate(figures):
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        ax = fig.axes[0]
        assert ax.get_ylim()[0] == 0
        assert ax.get_ygridlines() and all(line.get_visible() for line in ax.get_ygridlines())
        assert not any(line.get_visible() for line in ax.get_xgridlines())
        assert ax.get_axisbelow() is True
        assert len(ax.lines) == 3
        for line in ax.lines:
            assert np.isnan(line.get_ydata()).sum() == 1
        subtitle = next(text for text in fig.texts if "Seasonally adjusted" in text.get_text())
        source = next(text for text in fig.texts if text.get_text().startswith("Source: "))
        ends = [text for text in ax.texts if text.get_text().strip()]
        latest = " ".join(text.get_text() for text in ends)
        assert "May-Jul 2026" in latest
        assert "Aug 2026" in latest
        assert "Office for National Statistics" in source.get_text()
        assert ax.get_legend() is None
        assert not any(text.get_text().startswith("Latest: ") for text in fig.texts)
        assert len(ends) == 3
        if index == 0:
            assert [line.get_label() for line in ax.lines] == ["UK (16+)", "EU (15-74)", "US (16+)"]
            assert "UK 5.0%" in latest
            assert "EU 6.0%" in latest
            assert "US 4.0%" in latest
        else:
            assert [line.get_label() for line in ax.lines] == ["UK (16-24)", "EU (15-24)", "US (16-24)"]
        expected_values = (5, 6, 4) if index == 0 else (15, 15, 9)
        for line, expected in zip(ax.lines, expected_values):
            assert np.all(line.get_ydata()[np.isfinite(line.get_ydata())] == expected)
        assert [line.get_color() for line in ax.lines] == [ACCENT, MUTED, TEXT]
        endpoint_boxes = [text.get_window_extent(renderer) for text in ends]
        assert all(not a.overlaps(b) for i, a in enumerate(endpoint_boxes) for b in endpoint_boxes[i+1:])
        assert all(box.x0 >= ax.bbox.x1 for box in endpoint_boxes)
        title_box = fig._suptitle.get_window_extent(renderer)
        subtitle_box = subtitle.get_window_extent(renderer)
        source_box = source.get_window_extent(renderer)
        assert title_box.y0 > subtitle_box.y1
        assert subtitle_box.y0 > ax.get_window_extent(renderer).y1
        assert source_box.y1 < ax.xaxis.label.get_window_extent(renderer).y0
        for box in (title_box, subtitle_box, source_box, *endpoint_boxes):
            assert 0 <= box.x0 < box.x1 <= fig.bbox.width
