from __future__ import annotations

import csv
import io
import json

from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
import pandas as pd
import pytest
import requests

from ppp_data import inflation
from vizstyle import country_color


def response(classification, changes=None, *, codes=None):
    flow, default_codes = inflation.FLOWS[classification]
    codes = default_codes if codes is None else codes
    agency, dataset, version = flow.split(",")
    fields = [
        "DATAFLOW", *inflation.DIMENSIONS, "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT_MULT",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    end = pd.Timestamp.now().to_period("M").start_time - pd.DateOffset(months=1)
    for code in codes:
        start = (
            "2000-12-01" if code == inflation.EU_CODE else
            "2026-01-01" if code == "POL" and classification == "2018" else "2000-01-01"
        )
        stop = min(end, pd.Timestamp("2025-12-01")) if code == "POL" and classification == "1999" else end
        for month in pd.date_range(start, stop, freq="MS"):
            if code == "USA" and month == pd.Timestamp("2025-10-01"):
                continue
            row = dict(inflation.DIMENSIONS, REF_AREA=code)
            row.update(
                DATAFLOW=f"{agency}:{dataset}({version})", TIME_PERIOD=f"{month:%Y-%m}",
                OBS_VALUE=-.5 if month.year == 2015 else 3, OBS_STATUS="A", UNIT_MULT="",
            )
            row.update(changes or {})
            writer.writerow(row)
    return stream.getvalue()


@pytest.fixture
def inflation_frame(monkeypatch):
    def download(url, **kwargs):
        classification = next(key for key, (flow, _) in inflation.FLOWS.items() if flow in url)
        assert kwargs["params"] == {"format": "csvfile", "startPeriod": "2000-01"}
        return response(classification)

    monkeypatch.setattr(inflation, "get_text", download)
    return inflation.fetch()


@pytest.fixture
def eu_inflation_frame():
    return inflation.validate(inflation.parse(
        response("2018", {"OBS_VALUE": "4.7"}, codes=(inflation.EU_CODE,)),
        "2018", "2026-10-18T18:00:00Z",
    ), countries=(inflation.EU_CODE,))


def test_inflation_selection_keeps_real_months_negative_rates_and_current_classification(inflation_frame):
    assert (inflation_frame["value"] == -.5).any()
    assert not (
        inflation_frame["iso3"].eq("USA") & inflation_frame["date"].eq("2025-10-01")
    ).any()
    poland = inflation_frame[inflation_frame["iso3"] == "POL"]
    assert poland.loc[poland["date"] < "2026-01-01", "classification"].eq("1999").all()
    assert poland.loc[poland["date"] >= "2026-01-01", "classification"].eq("2018").all()
    france = inflation_frame[inflation_frame["iso3"] == "FRA"]
    assert france["classification"].eq("2018").all()
    assert not inflation_frame.duplicated(["iso3", "date"]).any()


@pytest.mark.parametrize("change", [
    {"FREQ": "A"}, {"METHODOLOGY": "HICP"}, {"MEASURE": "IT_W"},
    {"UNIT_MEASURE": "IX"}, {"EXPENDITURE": "CP01"}, {"ADJUSTMENT": "S"},
    {"TRANSFORMATION": "G1"}, {"UNIT_MULT": "2"}, {"OBS_VALUE": "nan"},
    {"OBS_VALUE": "-100"}, {"OBS_STATUS": "UNKNOWN"}, {"TIME_PERIOD": "2025"},
])
def test_parser_rejects_wrong_inflation_definition_and_invalid_rates(change):
    with pytest.raises(ValueError):
        inflation.parse(response("1999", change), "1999", "2026-10-18T18:00:00Z")


def test_validation_protects_monthly_history_provenance_and_freshness(inflation_frame):
    missing = inflation_frame[
        ~(inflation_frame["iso3"].eq("POL") & inflation_frame["date"].eq("2025-12-01"))
    ]
    with pytest.raises(ValueError, match="monthly coverage"):
        inflation.validate(missing)
    latest = inflation_frame["date"].max()
    reduced = inflation_frame[
        ~(inflation_frame["iso3"].eq("GBR") & inflation_frame["date"].eq(latest))
    ]
    with pytest.raises(ValueError, match="previously published"):
        inflation.validate(reduced, previous=inflation_frame)
    corrupt = inflation_frame.copy()
    corrupt.loc[0, "series_id"] = corrupt.loc[0, "series_id"].replace(".CPI.", ".CORE.")
    with pytest.raises(ValueError, match="provenance"):
        inflation.validate(corrupt)
    inflation.validate(inflation_frame, as_of=latest + pd.DateOffset(years=1))
    with pytest.raises(ValueError, match="120 days"):
        inflation.validate(
            inflation_frame, as_of=latest + pd.DateOffset(years=1), require_recent=True,
        )


def test_failed_inflation_fetch_preserves_csv_and_published_chart(inflation_frame, monkeypatch, tmp_path):
    saved = tmp_path / "inflation.csv"
    inflation_frame.to_csv(saved, index=False)
    before = saved.read_bytes()
    chart = tmp_path / "charts/consumer_price_inflation.png"
    chart.parent.mkdir()
    chart.write_bytes(b"previous published figure")

    def fail():
        raise requests.ConnectionError("current CPI source unavailable")

    monkeypatch.setattr(inflation, "fetch", fail)
    with pytest.raises(requests.ConnectionError):
        inflation.main(["--csv", str(saved), "--out", str(chart.parent)])
    assert saved.read_bytes() == before
    assert chart.read_bytes() == b"previous published figure"


@pytest.mark.parametrize("comparison", ["all", "four_country", "uk_us_eu"])
def test_inflation_plot_keeps_source_points_gaps_colors_and_explanations(
    inflation_frame, eu_inflation_frame, comparison, monkeypatch, tmp_path,
):
    original_save = inflation.save_chart
    figures = []

    def save(fig, *args, **kwargs):
        figures.append(fig)
        return original_save(fig, *args, **kwargs)

    monkeypatch.setattr(inflation, "save_chart", save)
    frame = inflation_frame.copy()
    frame.loc[frame["iso3"].isin(["ITA", "POL"]), "value"] = 50
    path = inflation.make_chart(frame, tmp_path, comparison=comparison, eu_frame=eu_inflation_frame)
    data = json.loads(path.with_suffix(".json").read_text())
    expected_codes = inflation.COMPARISONS[comparison]
    assert {series["label"] for series in data["series"]} == {
        inflation.AREAS[code] for code in expected_codes
    }
    source = pd.concat([frame, eu_inflation_frame], ignore_index=True)
    for series in data["series"]:
        part = source[source["country"] == series["label"]]
        assert [(point[2], point[3]) for point in series["points"]] == [
            (f"{row.date:%Y-%m-%d}", f"{row.value:g}%") for row in part.itertuples()
        ]
    fig, ax = figures[0], figures[0].axes[0]
    for line in ax.lines[:len(expected_codes)]:
        assert line.get_color() == country_color(line.get_label())
    if comparison != "all":
        assert ax.get_ylim()[1] < 10
    assert np.isnan(ax.lines[1].get_ydata()).sum() == 1
    footer = fig.texts[-1].get_text().replace("\n", " ")
    assert "UK: CPIH" in footer and "not a PPP" in footer
    assert "prices rise more slowly" in footer and "not filled" in footer
    if comparison == "uk_us_eu":
        assert "not the euro area or an average" in footer
        assert "December 2000" in footer
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[-1].get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0


def test_eu_inflation_uses_complete_current_classification_and_protects_published_coverage(
    eu_inflation_frame, monkeypatch,
):
    def download(url, **kwargs):
        assert inflation.FLOWS["2018"][0] in url
        assert url.endswith("/EU27_2020.M.N.CPI.PA._T.N.GY")
        assert kwargs["params"] == {"format": "csvfile", "startPeriod": "2000-12"}
        return response("2018", {"OBS_VALUE": "4.7"}, codes=(inflation.EU_CODE,))

    monkeypatch.setattr(inflation, "get_text", download)
    frame = inflation.fetch_eu()
    assert set(frame["iso3"]) == {inflation.EU_CODE}
    assert frame["date"].min() == pd.Timestamp("2000-12-01")
    assert frame["value"].eq(4.7).all()
    with pytest.raises(ValueError, match="monthly coverage"):
        inflation.validate(frame.iloc[1:], countries=(inflation.EU_CODE,))
    with pytest.raises(ValueError, match="previously published"):
        inflation.validate(frame.iloc[:-1], eu_inflation_frame, countries=(inflation.EU_CODE,))


def test_uk_us_eu_plot_requires_the_actual_aggregate(inflation_frame, tmp_path):
    with pytest.raises(ValueError, match="published EU-27 aggregate"):
        inflation.make_chart(inflation_frame, tmp_path, comparison="uk_us_eu")
    assert not list(tmp_path.glob("*.png"))


def test_offline_inflation_rebuild_writes_all_versions_without_rewriting_sources(
    inflation_frame, eu_inflation_frame, monkeypatch, tmp_path,
):
    saved, saved_eu = tmp_path / "national.csv", tmp_path / "eu.csv"
    inflation_frame.to_csv(saved, index=False)
    eu_inflation_frame.to_csv(saved_eu, index=False)
    before = saved.read_bytes(), saved_eu.read_bytes()
    monkeypatch.setattr(inflation, "fetch", lambda: pytest.fail("Offline charting must not fetch"))
    monkeypatch.setattr(inflation, "fetch_eu", lambda: pytest.fail("Offline charting must not fetch"))
    assert inflation.main([
        "--from-csv", str(saved), "--eu-csv", str(saved_eu), "--out", str(tmp_path),
    ]) == 0
    for suffix, count in (("", 6), ("_four_country", 4), ("_uk_us_eu", 3)):
        path = tmp_path / f"consumer_price_inflation{suffix}.png"
        assert path.exists()
        assert len(json.loads(path.with_suffix(".json").read_text())["series"]) == count
    assert (saved.read_bytes(), saved_eu.read_bytes()) == before


def test_failed_eu_fetch_preserves_both_sources_and_existing_figures(
    inflation_frame, eu_inflation_frame, monkeypatch, tmp_path,
):
    saved, saved_eu = tmp_path / "national.csv", tmp_path / "eu.csv"
    inflation_frame.to_csv(saved, index=False)
    eu_inflation_frame.to_csv(saved_eu, index=False)
    before = saved.read_bytes(), saved_eu.read_bytes()
    chart = tmp_path / "consumer_price_inflation_four_country.png"
    chart.write_bytes(b"previous four-country chart")
    monkeypatch.setattr(inflation, "fetch", lambda: inflation_frame)

    def fail():
        raise requests.ConnectionError("EU inflation source unavailable")

    monkeypatch.setattr(inflation, "fetch_eu", fail)
    with pytest.raises(requests.ConnectionError):
        inflation.main(["--csv", str(saved), "--eu-csv", str(saved_eu), "--out", str(tmp_path)])
    assert (saved.read_bytes(), saved_eu.read_bytes()) == before
    assert chart.read_bytes() == b"previous four-country chart"
