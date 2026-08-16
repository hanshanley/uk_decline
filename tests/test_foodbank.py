"""Offline tests for the Trussell food-bank analysis."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

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
            "trussell_food_parcels_history.png",
            "trussell_food_parcels_annual.png",
            "trussell_food_parcels_midyear.png",
        }
        assert all(path.stat().st_size > 50_000 for path in written)
    finally:
        for path in test_dir.glob("*"):
            path.unlink()
        test_dir.rmdir()
