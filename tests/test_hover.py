from datetime import datetime
import hashlib
import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np
from PIL import Image
import pytest

from scripts import chart_data
from vizstyle import save_chart


def test_hover_keeps_real_dates_percentages_and_missing_observations(tmp_path):
    fig, ax = plt.subplots()
    ax.plot(
        [datetime(2024, month, 1) for month in (1, 2, 3)],
        [4.25, np.nan, 5.5], label="UK",
    )
    ax.axhline(6, label="Reference, not a measured series")
    ax.yaxis.set_major_formatter(PercentFormatter())
    path = tmp_path / "rate.png"
    save_chart(fig, path, dpi=150, bbox_inches="tight")
    data = chart_data.load_chart_data(tmp_path, path.relative_to(tmp_path))
    assert data["image_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(data["series"]) == 1
    assert data["series"][0]["label"] == "UK"
    assert [point[2:] for point in data["series"][0]["points"]] == [
        ["2024-01-01", "4.25%"], ["2024-03-01", "5.5%"],
    ]
    plt.close(fig)


def test_hover_positions_match_saved_tight_crop_pixels(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([2025], [4.9], "o", color="#ff0000", markersize=12, label="UK")
    path = tmp_path / "point.png"
    save_chart(fig, path, dpi=160, bbox_inches="tight", pad_inches=.23)
    data = json.loads(path.with_suffix(".json").read_text())
    point = data["series"][0]["points"][0]
    pixels = np.asarray(Image.open(path).convert("RGB"))
    ys, xs = np.where((pixels[:, :, 0] > 240) & (pixels[:, :, 1] < 20) & (pixels[:, :, 2] < 20))
    assert abs(xs.mean() - point[0] * pixels.shape[1]) < 1
    assert abs(ys.mean() - point[1] * pixels.shape[0]) < 1
    assert fig.dpi == 100
    plt.close(fig)


@pytest.mark.parametrize("layout", ["left-panel", "figure"])
def test_save_chart_separates_tight_titles_and_subtitles_without_moving_data(tmp_path, layout):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([2024, 2025], [2, 3], label="UK")
    ax.set_xticks([2024, 2025], ["2024", "2025"])
    if layout == "left-panel":
        title = ax.set_title("Public sector net investment", loc="left", fontsize=16, pad=12)
        subtitle = ax.text(0, 1.01, "Percent of GDP", transform=ax.transAxes, fontsize=10)
    else:
        title = fig.suptitle("Main title", fontsize=20, y=.98)
        subtitle = fig.text(.5, .93, "Subtitle", ha="center", fontsize=12)
    subtitle_position = subtitle.get_position()
    bounds = ax.get_position().bounds
    path = tmp_path / "spaced.png"
    save_chart(fig, path, dpi=180, bbox_inches="tight")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    gap = (
        title.get_window_extent(renderer).y0 - subtitle.get_window_extent(renderer).y1
    ) * 72 / fig.dpi
    assert 4.5 <= gap <= 6
    first = title.get_window_extent(renderer).bounds
    save_chart(fig, path, dpi=180, bbox_inches="tight")
    fig.canvas.draw()
    assert title.get_window_extent(fig.canvas.get_renderer()).bounds == pytest.approx(first)
    assert ax.get_position().bounds == pytest.approx(bounds)
    assert subtitle.get_position() == subtitle_position
    points = json.loads(path.with_suffix(".json").read_text())["series"][0]["points"]
    assert [point[2:4] for point in points] == [["2024", "2"], ["2025", "3"]]
    plt.close(fig)


def test_save_chart_preserves_already_generous_title_spacing(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([2025], [2], "o")
    title = ax.set_title("Title", pad=45)
    ax.text(.5, 1.01, "Subtitle", transform=ax.transAxes, ha="center", fontsize=10)
    fig.canvas.draw()
    before = title.get_window_extent(fig.canvas.get_renderer()).bounds
    save_chart(fig, tmp_path / "unchanged.png", dpi=150, bbox_inches="tight")
    fig.canvas.draw()
    assert title.get_window_extent(fig.canvas.get_renderer()).bounds == pytest.approx(before)
    plt.close(fig)


def test_save_chart_gently_increases_multiline_title_leading(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([2025], [2], "o")
    title = ax.set_title("Main title\nSecond line", fontsize=18, linespacing=1.2)
    fig.canvas.draw()
    before = title.get_window_extent(fig.canvas.get_renderer()).height
    save_chart(fig, tmp_path / "multiline.png", dpi=150, bbox_inches="tight")
    fig.canvas.draw()
    increase = (
        title.get_window_extent(fig.canvas.get_renderer()).height - before
    ) * 72 / fig.dpi
    assert 1 <= increase <= 4
    plt.close(fig)


def test_manual_date_ticks_do_not_export_dates_as_year_labels_or_day_numbers(tmp_path):
    import matplotlib.dates as mdates

    fig, ax = plt.subplots()
    dates = [datetime(2025, 1, 1), datetime(2025, 2, 1), datetime(2025, 3, 1)]
    ax.plot(dates, [4., 5., 6.], label="UK")
    ax.set_xticks([dates[0], dates[-1]])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    path = tmp_path / "monthly.png"
    save_chart(fig, path, bbox_inches="tight")
    payload = json.loads(path.with_suffix(".json").read_text())
    assert [point[2] for point in payload["series"][0]["points"]] == [
        "2025-01-01", "2025-02-01", "2025-03-01",
    ]
    plt.close(fig)


def test_stacked_and_horizontal_bars_report_segment_not_cumulative_values(tmp_path):
    fig, (vertical, horizontal) = plt.subplots(1, 2)
    vertical.bar(["2025"], [20], label="Adults")
    vertical.bar(["2025"], [10], bottom=[20], label="Children")
    horizontal.barh(["UK"], [4.25], label="Rate")
    horizontal.plot([4.25], [0], "o", label="Endpoint")
    horizontal.xaxis.set_major_formatter(PercentFormatter())
    path = tmp_path / "bars.png"
    save_chart(fig, path, dpi=120, bbox_inches="tight")
    series = chart_data.load_chart_data(tmp_path, path.relative_to(tmp_path))["series"]
    assert [(item["label"], item["points"][0][2:4]) for item in series] == [
        ("Adults", ["2025", "20"]), ("Children", ["2025", "10"]),
        ("Endpoint", ["UK", "4.25%"]), ("Rate", ["UK", "4.25%"]),
    ]
    for item in series:
        point = item["points"][0]
        if len(point) == 4:
            continue
        left, top, right, bottom = point[4]
        assert left <= point[0] <= right
        assert top <= point[1] <= bottom
    plt.close(fig)


def test_sparse_year_ticks_do_not_turn_years_into_comma_separated_numbers(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([2020, 2021, 2022], [1, 2, 3])
    ax.set_xticks([2020, 2022], ["2019/20", "2021/22"])
    path = tmp_path / "years.png"
    save_chart(fig, path, bbox_inches="tight")
    payload = json.loads(path.with_suffix(".json").read_text())
    assert [point[2] for point in payload["series"][0]["points"]] == ["2019/20", "2020/21", "2021/22"]
    plt.close(fig)


def test_grouped_bars_keep_categories_and_currency_without_exporting_missing_values(tmp_path):
    fig, ax = plt.subplots()
    bars = ax.bar([-.25, .75], [1250.5, 0], label="Fees")
    bars[1].set_alpha(0)
    ax.set_xticks([0, 1], ["England", "Unavailable"])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"£{value:,.0f}"))
    path = tmp_path / "fees.png"
    save_chart(fig, path, bbox_inches="tight")
    payload = json.loads(path.with_suffix(".json").read_text())
    points = payload["series"][0]["points"]
    assert len(points) == 1
    assert points[0][2:4] == ["England", "£1,250.5"]
    plt.close(fig)


@pytest.mark.parametrize("label, formatter, expected", [
    ("Rate (%)", None, "4.9%"),
    ("Visas granted", FuncFormatter(lambda value, _: f"{value:,.0f}k"), "4,900"),
])
def test_hover_reports_axis_units_without_rounding_away_the_observation(tmp_path, label, formatter, expected):
    fig, ax = plt.subplots()
    ax.plot([2025], [4.9])
    ax.set_ylabel(label)
    if formatter is not None:
        ax.yaxis.set_major_formatter(formatter)
    path = tmp_path / "units.png"
    save_chart(fig, path)
    payload = json.loads(path.with_suffix(".json").read_text())
    assert payload["series"][0]["points"][0][3] == expected
    plt.close(fig)


def test_stacked_areas_report_actual_shares_not_upper_boundaries(tmp_path):
    fig, ax = plt.subplots()
    ax.stackplot([2020, 2021], [20, 21], [60, 61], [20, 18], labels=["Children", "Working-age", "Older"])
    ax.yaxis.set_major_formatter(PercentFormatter())
    path = tmp_path / "areas.png"
    save_chart(fig, path, dpi=100, bbox_inches="tight")
    series = chart_data.load_chart_data(tmp_path, path.relative_to(tmp_path))["series"]
    assert [(item["label"], item["points"][-1][3]) for item in series] == [
        ("Children", "21%"), ("Working-age", "61%"), ("Older", "18%"),
    ]
    plt.close(fig)


def test_stale_or_invalid_observations_cannot_be_published(tmp_path, monkeypatch):
    fig, ax = plt.subplots()
    ax.plot([2024, 2025], [4, 5])
    chart = tmp_path / "plot.png"
    save_chart(fig, chart, bbox_inches="tight")
    monkeypatch.setattr(chart_data, "tracked_charts", lambda _: [chart.relative_to(tmp_path)])
    with pytest.raises(RuntimeError, match="not regenerated"):
        chart_data.validate_refresh(tmp_path, time.time_ns())
    payload = json.loads(chart.with_suffix(".json").read_text())
    payload["series"][0]["points"][0][0] = float("nan")
    chart.with_suffix(".json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="invalid observation"):
        chart_data.load_chart_data(tmp_path, chart.relative_to(tmp_path))
    chart.write_bytes(b"new chart with old observations")
    with pytest.raises(ValueError, match="do not match"):
        chart_data.load_chart_data(tmp_path, chart.relative_to(tmp_path))
    plt.close(fig)
