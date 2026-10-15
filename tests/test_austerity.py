"""Offline tests for the HM Treasury austerity analysis."""

from __future__ import annotations

import pandas as pd
import pytest

from austerity_data import charts, treasury


def _aggregate_sheet() -> pd.DataFrame:
    data = [[None] * 15 for _ in range(9)]
    data[5][1] = "2009-10"
    data[5][3], data[5][9], data[5][10], data[5][13], data[5][14] = (
        900,
        70,
        3.0,
        1020,
        46,
    )
    data[6][1] = "2010-11"
    data[6][3], data[6][9], data[6][10], data[6][13], data[6][14] = (
        920,
        58,
        2.4,
        1040,
        45,
    )
    data[7][1] = "2013-14"
    data[7][3], data[7][9], data[7][10], data[7][13], data[7][14] = (
        915,
        36,
        1.5,
        1015,
        42,
    )
    return pd.DataFrame(data)


def _functions_sheet() -> pd.DataFrame:
    data = [[None] * 5 for _ in range(12)]
    data[4] = [None, "2010-11", "2011-12", "2012-13", "2019-20"]
    data[5] = ["3. Public order and safety", 50, 47, 43, 45]
    data[6] = ["6. Housing and community amenities", 20, 15, 14, 18]
    data[7] = ["7. Health", 170, 171, 173, 200]
    data[8] = ["8. Recreation, culture and religion", 20, 18, 16, 17]
    data[9] = ["2. Defence(2)", 60, 57, 54, 56]
    data[10] = ["of which: public and common services", 10, 9, 8, 9]
    return pd.DataFrame(data)


def _historical_functions_sheet() -> pd.DataFrame:
    data = [[None] * 7 for _ in range(12)]
    data[4] = [None, None, "2000-01", "2001-02", "2002-03", "2003-04", "2010-11"]
    data[6] = [None, "3. Public order and safety", 40, 43, 45, 47, 50]
    data[7] = [None, "6. Housing and community amenities", 10, 12, 14, 15, 20]
    data[8] = [None, "7. Health", 100, 110, 120, 130, 170]
    data[9] = [None, "8. Recreation, culture and religion", 12, 14, 15, 17, 20]
    data[10] = [None, "2. Defence(2)", 48, 50, 52, 54, 60]
    return pd.DataFrame(data)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        treasury.build_rows(
            {
                "4_1": _aggregate_sheet(),
                "4_3": _functions_sheet(),
                "historical_4_3": _historical_functions_sheet(),
            }
        )
    )


def test_parse_aggregates_values_and_units() -> None:
    rows = treasury.parse_aggregates(_aggregate_sheet())
    by = {(r["financial_year"], r["metric"]): r for r in rows}
    assert by[("2010-11", "public_sector_net_investment_pct_gdp")]["value"] == 2.4
    assert by[("2013-14", "total_managed_expenditure_real")]["value"] == 1015
    assert by[("2009-10", "public_sector_current_expenditure_real")]["year"] == 2009
    assert all(set(row) == set(treasury.ROW_FIELDS) for row in rows)


def test_parse_functions_ignores_subfunctions() -> None:
    rows = treasury.parse_functions(_functions_sheet())
    categories = {row["category"] for row in rows}
    assert "public_order_safety" in categories
    assert "housing_community" in categories
    assert "public_common_services" not in categories
    assert len(rows) == 5 * 4


def test_parse_historical_functions_and_source() -> None:
    rows = treasury.parse_historical_functions(_historical_functions_sheet())
    assert len(rows) == 5 * 5
    first = next(
        row for row in rows
        if row["category"] == "housing_community"
        and row["financial_year"] == "2000-01"
    )
    assert first["value"] == 10
    assert "2012" in first["source"]
    assert "2011-12 prices" in first["unit"]


def test_index_and_trough_math() -> None:
    frame = _frame()
    housing = charts.indexed_function_series(frame, "housing_community")
    assert housing.iloc[0]["financial_year"] == "2000-01"
    assert housing.iloc[0]["index"] == pytest.approx(50)
    assert housing[housing["financial_year"] == "2012-13"].iloc[0]["index"] == 70
    change, year = charts.trough_change(frame, "housing_community")
    assert change == pytest.approx(-30)
    assert year == "2012-13"


def test_new_spending_year_and_high_value_are_not_silently_dropped(monkeypatch, tmp_path):
    frame = _frame()
    newer = frame.loc[
        (frame["financial_year"] == "2019-20") &
        (frame["metric"] == "functional_spending_real")
    ].copy()
    newer["financial_year"], newer["year"] = "2027-28", 2027
    newer["value"] *= 3
    newer["source"] = "HM Treasury, Public Spending Statistics, July 2028"
    frame = pd.concat([frame, newer, pd.DataFrame([
        treasury._row("2027-28", "public_sector_net_investment_pct_gdp",
                      "United Kingdom", 4., "percent of GDP")
    ])], ignore_index=True)
    figures = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: figures.append(fig))
    charts.make_chart(frame, tmp_path / "spending.png")
    fig = figures[0]
    assert all(ax.get_xlim()[1] > 2027 for ax in fig.axes)
    for ax in fig.axes[:4]:
        line = ax.lines[0]
        assert line.get_xdata()[-1] == 2027
        assert line.get_ydata()[-1] <= ax.get_ylim()[1]
    text = " ".join(item.get_text() for item in fig.texts)
    assert "2027" in text and "July 2028" in text


def test_spending_rows_retain_discovered_release_source():
    rows = treasury.build_rows({
        "4_1": _aggregate_sheet(), "4_3": _functions_sheet(),
        "source": "HM Treasury, Public Spending Statistics, July 2027",
    })
    assert all("July 2027" in row["source"] for row in rows)


def test_missing_release_discovery_does_not_silently_use_old_pinned_vintage(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(treasury, "_get", lambda *a: SimpleNamespace(text="<html>No releases</html>"))
    with pytest.raises(RuntimeError, match="refusing a stale pinned refresh"):
        treasury.resolve_release_url()


def test_release_and_workbook_link_parsing() -> None:
    html = """
    <a href="/government/statistics/public-spending-statistics-release-july-2025">x</a>
    <a href="/government/statistics/public-spending-statistics-release-july-2026">y</a>
    """
    links = treasury._release_links(html)
    assert max(links)[0] == 2026
    release = """
    <a href="https://assets.publishing.service.gov.uk/media/x/Chapter_1.xlsx">one</a>
    <a href="https://assets.publishing.service.gov.uk/media/x/July_PSS_2026_Chapter_4.xlsx">four</a>
    """
    assert treasury._chapter4_links(release) == [
        "https://assets.publishing.service.gov.uk/media/x/July_PSS_2026_Chapter_4.xlsx"
    ]


def test_invalid_fiscal_year_rejected() -> None:
    with pytest.raises(ValueError):
        treasury.fiscal_start("2010")


def test_investment_annotation_uses_actual_austerity_trough(monkeypatch):
    from matplotlib.axes import Axes

    frame = _frame()
    frame = pd.concat([frame, pd.DataFrame([
        treasury._row("2012-13", "public_sector_net_investment_pct_gdp",
                      "United Kingdom", 1.0, "percent of GDP"),
        treasury._row("2024-25", "public_sector_net_investment_pct_gdp",
                      "United Kingdom", 0.1, "percent of GDP"),
    ])], ignore_index=True)
    labels = []
    original = Axes.annotate

    def capture(self, text, *args, **kwargs):
        labels.append(text)
        return original(self, text, *args, **kwargs)

    monkeypatch.setattr(Axes, "annotate", capture)
    monkeypatch.setattr(charts, "save_chart", lambda *a, **k: None)
    charts.make_chart(frame)
    assert "2012-13 low\n1.0% of GDP" in labels
    assert all("2024-25 low" not in label for label in labels)


def test_summary_cannot_substitute_earlier_endpoint(tmp_path):
    from austerity_data import summary

    frame = _frame()
    frame = frame[~((frame["category"] == "housing_community")
                    & (frame["financial_year"] == charts.END_YEAR))]
    with pytest.raises(ValueError, match="endpoint"):
        summary.build_summary(frame, tmp_path / "summary.md")


def test_investment_footer_has_separate_lines_and_clears_axis_labels(monkeypatch):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: captured.append(fig))
    charts.make_chart(_frame())
    fig = captured[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    footer = next(text for text in fig.texts if text.get_text().startswith("Note:"))
    assert "\nSource:" in footer.get_text()
    assert "\nContext:" in footer.get_text()
    assert footer.get_window_extent(renderer).y1 + 5 < min(
        tick.get_window_extent(renderer).y0 for tick in fig.axes[-1].get_xticklabels()
    )


@pytest.mark.parametrize("font", ["DejaVu Serif", "DejaVu Sans"])
def test_investment_baseline_label_clears_the_published_curve(monkeypatch, font):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.text import Text

    captured = []
    original_style = charts.house_style

    def style():
        original_style()
        charts.plt.rcParams["font.family"] = font

    monkeypatch.setattr(charts, "house_style", style)
    monkeypatch.setattr(charts, "save_chart", lambda fig, *a, **k: captured.append(fig))
    with charts.plt.rc_context():
        charts.make_chart(pd.read_csv(charts.ROOT / "data/austerity_spending.csv"))
        fig = captured[0]
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        ax = fig.axes[-1]
        annotation = next(text for text in ax.texts if text.get_text().startswith("2010\u201311\n"))
        # Exclude the intentional leader-line contact with the observation.
        box = Text.get_window_extent(annotation, renderer).padded(6)
        curve = ax.lines[0].get_path().transformed(ax.lines[0].get_transform())
        assert not curve.intersects_bbox(box, filled=False)
        assert ax.bbox.contains(box.x0, box.y0)
        assert ax.bbox.contains(box.x1, box.y1)
