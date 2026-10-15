"""Offline tests for the Trussell food-bank analysis."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.text import Text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from foodbank_data import charts, fetch, history, parse  # noqa: E402
from foodbank_data.sources import (  # noqa: E402
    CALENDAR_SOURCE,
    FISCAL_ARCHIVE,
    FISCAL_SLIDES_SOURCE,
    MIDYEAR_SOURCE,
    OUTPUT_DIR,
    RAW_DIR,
    Source,
)


def _workbook_bytes(periods: list[tuple[object, tuple[int, int, int, int]]]) -> bytes:
    columns = [("Nation and Region", "")]
    values: list[object] = ["United Kingdom"]
    metric_names = [
        "Parcels distributed for adults",
        "Parcels distributed for children",
        "Total parcels distributed",
        "Number of locations",
    ]
    for period, period_values in periods:
        columns.extend((period, metric) for metric in metric_names)
        values.extend(period_values)
    frame = pd.DataFrame(
        [values],
        columns=pd.MultiIndex.from_tuples(columns),
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Nations and regions", index=True)
    output.seek(0)
    return output.read()


def test_parse_calendar_synthetic_workbook() -> None:
    payload = _workbook_bytes(
        [
            (2019, (60, 40, 100, 3)),
            (2020, (90, 60, 150, 4)),
        ]
    )
    frame = parse.parse_calendar_years(io.BytesIO(payload))
    assert frame["year"].tolist() == [2019, 2020]
    assert frame["period_type"].unique().tolist() == ["calendar_year"]
    assert frame.loc[1, "change_vs_previous_pct"] == pytest.approx(50)
    assert frame.loc[1, "change_vs_2019_pct"] == pytest.approx(50)


def test_calendar_release_discovery_and_parsing_preserve_the_new_source():
    url = "https://cms.trussell.org.uk/sites/default/files/2027-03/eys_2026_parcel_stats.xlsx"
    html = f'<a href="{CALENDAR_SOURCE.url}">Archive</a><a href="{url}">Download full data</a>'
    source = fetch.discover_calendar_source(get_bytes=lambda _: html.encode())
    assert source.url == url
    assert source.filename == "food_bank_trussell_eys_2026.xlsx"
    payload = _workbook_bytes([(2026, (90, 60, 150, 4))])
    frame = parse.parse_calendar_years(
        io.BytesIO(payload), source_url=source.url, accessed_date="2027-03-24",
    )
    assert frame.iloc[0]["year"] == 2026
    assert frame.iloc[0]["source_url"] == url
    assert frame.iloc[0]["accessed_date"] == "2027-03-24"
    with pytest.raises(ValueError, match="no calendar-year"):
        fetch.discover_calendar_source(get_bytes=lambda _: b"<p>Publisher layout changed</p>")


def test_parse_midyear_synthetic_workbook() -> None:
    payload = _workbook_bytes(
        [
            ("1 April - 30 September 2019", (60, 40, 100, 3)),
            ("1 April - 30 September 2024", (102, 68, 170, 4)),
        ]
    )
    frame = parse.parse_midyear(io.BytesIO(payload))
    assert frame["period_label"].tolist() == ["Apr-Sep 2019", "Apr-Sep 2024"]
    assert frame.loc[1, "end_date"] == "2024-09-30"
    assert frame.loc[1, "change_vs_2019_pct"] == pytest.approx(70)


def test_validate_rejects_total_mismatch() -> None:
    frame = pd.DataFrame(
        [
            {
                "period_type": "calendar_year",
                "year": 2025,
                "period_label": "2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "adults": 10,
                "children": 5,
                "total": 99,
                "locations": 1,
                "source_url": "https://example.invalid",
                "accessed_date": "2026-08-16",
            }
        ]
    )
    with pytest.raises(ValueError, match=r"adult \+ child"):
        parse.validate(frame)


def test_parser_rejects_fractional_counts_instead_of_truncating():
    payload = _workbook_bytes([(2025, (10.5, 5.5, 15.9, 1))])
    with pytest.raises(ValueError, match="invalid UK count"):
        parse.parse_calendar_years(io.BytesIO(payload))


def test_chart_keeps_calendar_annotations_separate_and_readable(monkeypatch):
    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(RAW_DIR))
    fiscal = history.build_fiscal_history(FISCAL_ARCHIVE, FISCAL_SLIDES_SOURCE.path(RAW_DIR))
    original = charts.plt.subplots
    captured = []

    def capture(*args, **kwargs):
        fig, ax = original(*args, **kwargs)
        captured.append((fig, ax))
        return fig, ax

    monkeypatch.setattr(charts.plt, "subplots", capture)
    monkeypatch.setattr(charts, "save_chart", lambda *a, **k: None)
    charts.foodbank_history_chart(fiscal, annual)
    fig, (historical, recent) = captured[0]
    labels = [text.get_text() for text in recent.texts]
    assert "912k parcels\nfor children" in labels
    assert "1.73m parcels\nfor adults" in labels
    assert recent.get_title(loc="left") == "Calendar year 2025"
    assert "2005/06–2023/24" in historical.get_title(loc="left")
    assert historical.get_ylim() == recent.get_ylim()
    assert len(recent.patches) == 2
    assert sum(bar.get_height() for bar in recent.patches) == annual.iloc[-1]["total"]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    title_box = next(
        text.get_window_extent(renderer) for text in recent.findobj(Text)
        if text.get_text() == "Calendar year 2025"
    )
    boxes = [text.get_window_extent(renderer) for text in recent.texts]
    for index, box in enumerate(boxes):
        assert not box.overlaps(historical.get_window_extent(renderer))
        assert not box.overlaps(title_box)
        assert all(not box.overlaps(other) for other in boxes[index + 1:])
    for annotation in recent.texts:
        if annotation.get_text().endswith(("for children", "for adults")):
            assert annotation.arrow_patch is not None
            assert annotation.xy[0] == pytest.approx(0.36)
            bar = recent.patches[1 if annotation.get_text().endswith("for children") else 0]
            assert bar.get_y() < annotation.xy[1] < bar.get_y() + bar.get_height()


def test_official_workbooks_match_headlines() -> None:
    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(RAW_DIR))
    midyear = parse.parse_midyear(MIDYEAR_SOURCE.path(RAW_DIR))
    latest = annual.iloc[-1]
    latest_midyear = midyear.iloc[-1]
    assert (
        int(latest["year"]),
        int(latest["adults"]),
        int(latest["children"]),
        int(latest["total"]),
    ) == (2025, 1_732_619, 912_216, 2_644_835)
    assert latest["change_vs_previous_pct"] == pytest.approx(-11.740365, abs=1e-6)
    assert latest["change_vs_2019_pct"] == pytest.approx(44.93827, abs=1e-5)
    assert int(latest_midyear["total"]) == 1_428_681
    assert latest_midyear["change_vs_2019_pct"] == pytest.approx(69.277206, abs=1e-6)


def test_historical_archive_starts_with_observation_not_zero() -> None:
    frame = history.load_archive(FISCAL_ARCHIVE)
    assert frame.iloc[0]["period_label"] == "2005/06"
    assert int(frame.iloc[0]["total"]) == 2_814
    assert int(frame.iloc[-1]["total"]) == 1_332_952
    assert frame["start_year"].min() == 2005
    assert (frame["total"] > 0).all()
    assert 2000 not in frame["start_year"].tolist()


def test_official_fiscal_pptx_embedded_table() -> None:
    frame = history.parse_official_fiscal_pptx(
        FISCAL_SLIDES_SOURCE.path(RAW_DIR)
    )
    assert frame["period_label"].tolist() == [
        "2018/19",
        "2019/20",
        "2020/21",
        "2021/22",
        "2022/23",
        "2023/24",
    ]
    assert int(frame.iloc[0]["total"]) == 1_606_810
    assert int(frame.iloc[-1]["total"]) == 3_121_404
    assert int(frame.iloc[-1]["adults"]) == 1_977_308
    assert int(frame.iloc[-1]["children"]) == 1_144_096


def test_fiscal_series_preserves_comparability_break() -> None:
    frame = history.build_fiscal_history(
        FISCAL_ARCHIVE,
        FISCAL_SLIDES_SOURCE.path(RAW_DIR),
    )
    assert len(frame) == 19
    groups = frame.groupby("comparability_group", sort=False)
    assert groups["period_label"].first().to_dict() == {
        "historical_archive": "2005/06",
        "modern_fiscal": "2018/19",
    }
    first_modern = frame.loc[frame["period_label"] == "2018/19"].iloc[0]
    assert pd.isna(first_modern["change_within_series_pct"])
    assert set(frame["period_type"]) == {"financial_year"}


def test_download_is_offline_testable() -> None:
    fake_xlsx = io.BytesIO()
    with zipfile.ZipFile(fake_xlsx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    source = Source("test", "https://example.invalid/test.xlsx", ".food_bank_test.xlsx", "")
    destination = source.path(OUTPUT_DIR)
    try:
        written = fetch.download(
            source,
            OUTPUT_DIR,
            get_bytes=lambda url: fake_xlsx.getvalue(),
        )
        assert written == destination
        assert written.read_bytes() == fake_xlsx.getvalue()
    finally:
        destination.unlink(missing_ok=True)
        destination.with_suffix(destination.suffix + ".part").unlink(missing_ok=True)


def test_charts_render_from_official_data() -> None:
    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(RAW_DIR))
    midyear = parse.parse_midyear(MIDYEAR_SOURCE.path(RAW_DIR))
    fiscal = history.build_fiscal_history(
        FISCAL_ARCHIVE,
        FISCAL_SLIDES_SOURCE.path(RAW_DIR),
    )
    test_dir = OUTPUT_DIR / ".test"
    try:
        written = charts.make_charts(annual, midyear, fiscal, test_dir)
        assert {path.name for path in written} == {
            "trussell_food_parcels.png",
            "trussell_food_parcels_history.png",
        }
        assert all(path.stat().st_size > 50_000 for path in written)
    finally:
        for path in test_dir.glob("*"):
            path.unlink()
        test_dir.rmdir()


def test_public_chart_uses_one_calendar_timeline_and_keeps_2025_comparable(monkeypatch):
    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(RAW_DIR))
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: captured.append(fig))
    charts.foodbank_chart(annual)
    fig = captured[0]
    assert len(fig.axes) == 1
    ax = fig.axes[0]
    adults, children = ax.containers
    assert ax.get_xticks().tolist() == annual["year"].tolist()
    assert [bar.get_x() + bar.get_width() / 2 for bar in adults] == annual["year"].tolist()
    assert [bar.get_height() for bar in adults] == annual["adults"].tolist()
    assert [bar.get_height() + bar.get_y() for bar in children] == annual["total"].tolist()
    assert ax.get_xlabel() == "Calendar year (January-December)"
    assert "every bar covers January-December" in " ".join(text.get_text() for text in fig.texts)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    footer = next(text for text in fig.texts if text.get_text().startswith("Source:"))
    assert footer.get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0
    for text in (*fig.texts, *ax.texts):
        box = text.get_window_extent(renderer)
        assert 0 <= box.x0 < box.x1 <= fig.bbox.width


def test_public_chart_rejects_non_calendar_reporting_periods():
    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(RAW_DIR))
    annual.loc[annual.index[-1], "period_type"] = "financial_year"
    with pytest.raises(ValueError, match="calendar-year"):
        charts.foodbank_chart(annual)
