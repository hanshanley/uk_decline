import json

import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from europe_data import gdp_comparisons as gdp, worldbank


@pytest.fixture
def frame():
    records = []
    for iso3, local, fx, ppp, volume in (
        ("GBR", (40_000, 44_000), (.8, .5), (.7, .7), (40_000, 44_000)),
        ("USA", (80_000, 96_000), (1., 1.), (1., 1.), (80_000, 96_000)),
    ):
        for index, year in enumerate((2007, 2025)):
            records.append({
                "iso3": iso3, "year": year, gdp.LOCAL: local[index], gdp.FX: fx[index],
                gdp.PPP: ppp[index], gdp.NOMINAL: local[index] / fx[index],
                gdp.CURRENT_PPP: local[index] / ppp[index],
                gdp.CONSTANT_PPP: volume[index] * (1.2 if iso3 == "GBR" else 1.),
                gdp.REAL: float(volume[index]),
            })
    return pd.DataFrame(records)


@pytest.mark.parametrize("metric", [gdp.FX, gdp.PPP, gdp.NOMINAL, gdp.CURRENT_PPP, gdp.REAL])
def test_conversion_audit_rejects_wrong_rates_years_and_real_series(frame, metric):
    gdp.validate_conversions(frame)
    frame.loc[1, metric] *= 1.1
    with pytest.raises(ValueError, match="mismatch|disagree"):
        gdp.validate_conversions(frame)


def test_conversion_audit_requires_same_year_inputs_and_unique_observations(frame):
    with pytest.raises(ValueError, match="unique"):
        gdp.validate_conversions(pd.concat([frame, frame.iloc[:1]]))
    frame.loc[1, gdp.FX] = np.nan
    with pytest.raises(ValueError, match="same-year"):
        gdp.validate_conversions(frame)


def test_conversion_inputs_are_fetched_only_for_uk_and_us(monkeypatch):
    calls = []

    def fetch(indicator, codes, start, end):
        calls.append((indicator, codes))
        return []

    monkeypatch.setattr(worldbank, "_fetch_indicator", fetch)
    worldbank.fetch(2007, 2025, iso3s=["GBR", "USA", "DEU", "EUU"])
    for indicator, codes in calls:
        assert codes == (
            ["GBR", "USA"] if indicator in {"NY.GDP.PCAP.CN", "PA.NUS.FCRF", "PA.NUS.PPP"}
            else ["GBR", "USA", "DEU", "EUU"]
        )


def test_comparison_chart_separates_fx_from_volumes_and_preserves_actual_hover_values(
    frame, tmp_path, monkeypatch,
):
    figures = []
    original = gdp.save_chart

    def save(fig, *args, **kwargs):
        figures.append(fig)
        original(fig, *args, **kwargs)

    monkeypatch.setattr(gdp, "save_chart", save)
    gdp.make_chart(frame, tmp_path)
    data = json.loads((tmp_path / "us_uk_gdp_measures.json").read_text())
    assert len(data["series"]) == 4
    assert [point[2] for point in data["series"][0]["points"]] == ["2007", "2025"]
    fig = figures[0]
    # A stronger pound changes nominal dollars, not the source's real or PPP conversions.
    assert fig.axes[0].lines[0].get_ydata()[[0, -1]] == pytest.approx([160, 100 * 96 / 88])
    assert fig.axes[1].lines[0].get_ydata()[[0, -1]] == pytest.approx([140, 100 * 96 / (44 / .7)])
    assert fig.axes[2].lines[0].get_ydata()[[0, -1]] == pytest.approx([100 * 80 / 48, 100 * 96 / 52.8])
    assert fig.axes[3].lines[0].get_ydata()[[0, -1]] == pytest.approx([1.25, 2.])
    assert np.isnan(fig.axes[0].lines[0].get_ydata()[1:-1]).all()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    for ax in fig.axes:
        title = ax.title if ax.title.get_text() else ax._left_title
        assert title.get_window_extent(renderer).y0 > ax.texts[0].get_window_extent(renderer).y1
        assert ax.texts[0].get_window_extent(renderer).y0 > ax.get_window_extent(renderer).y1
    top_bottom = min(ax.get_tightbbox(renderer).y0 for ax in fig.axes[:2])
    bottom_top = max(ax.get_tightbbox(renderer).y1 for ax in fig.axes[2:])
    assert top_bottom > bottom_top
    for ax in fig.axes:
        assert ax.texts[1].get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0
    source = fig.texts[-1].get_window_extent(renderer)
    assert source.y1 < min(ax.texts[1].get_window_extent(renderer).y0 for ax in fig.axes[2:])


def test_failed_currency_check_preserves_saved_europe_inputs(frame, tmp_path, monkeypatch):
    from europe_data import fetch_data

    frame.loc[1, gdp.FX] = .8  # Incorrectly reuse the old year's rate.
    rows = [
        {"iso3": row.iso3, "year": row.year, "metric": metric, "value": getattr(row, metric)}
        for row in frame.itertuples() for metric in frame.columns[2:]
    ]
    monkeypatch.setattr(fetch_data.worldbank, "fetch", lambda *args: rows)
    monkeypatch.setattr(fetch_data.worldbank, "us_cpi", lambda *args: {})
    saved = tmp_path / "europe_combined_wide.csv"
    saved.write_text("preserved published inputs\n")
    with pytest.raises(ValueError, match="conversion mismatch"):
        fetch_data.main(["--sources", "worldbank", "--out", str(tmp_path)])
    assert saved.read_text() == "preserved published inputs\n"
    assert not (tmp_path / "gdp_per_capita_ppp.csv").exists()
