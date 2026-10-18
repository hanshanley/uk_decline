"""Newer income figures must not masquerade as extensions of OECD medians."""

import io

import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from europe_data import recent_income as recent
from scripts import refresh_data


def workbook(rows, sheet):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, header=False, index=False)
    return buffer.getvalue()


def ons_rows():
    return [
        ["Table 1: Timeseries of mean and median equivalised household disposable income, UK (2024/25 prices)"],
        [], [], [], [],
        ["", "All people"], ["Year", "Mean", "Median"],
        *[[f"{year - 1}/{str(year)[-2:]}", 50000, 30000 + year]
          for year in range(2018, 2026)],
    ]


def census_rows():
    return [
        ["Accessible table"],
        ["Table 10. Selected Measures of Household Post-Tax Income Dispersion: 2009 to 2025"],
        ["Income in 2025 dollars, adjusted using the Chained Consumer Price Index"],
        [], [], ["Year", "", "", "", "", "50th\npercentile\n(median)"],
        *[[str(year) + (" 2" if year == 2024 else ""), "", "", "", "", 70000 + year]
          for year in range(2018, 2026)],
        ["2 Implementation of updated population controls."],
    ]


@pytest.fixture
def sources():
    uk = recent.parse_ons(workbook(ons_rows(), "Table 1"), "https://www.ons.gov.uk/uk.xlsx")
    us = recent.parse_census(workbook(census_rows(), "table10"), "https://www2.census.gov/us.xlsx")
    eu = [
        {
            "country": country, "year": year, "survey_year": year + 1,
            "period": str(year), "value": 20000 + year, "unit": "PPS",
            "price_base": "current", "definition": recent.DEFINITIONS[country][1],
            "status": "b" if year == 2021 else "",
            "source_url": "https://ec.europa.eu/eurostat/",
        }
        for country in recent.EU_COUNTRIES.values() for year in range(2018, 2025)
    ]
    return pd.DataFrame(uk + us + eu)


def test_national_parsers_use_post_tax_median_and_source_price_bases(sources):
    frame = recent.validate(sources)
    uk = frame[frame.country.eq("United Kingdom")].iloc[-1]
    us = frame[frame.country.eq("United States")].iloc[-1]
    assert (uk["year"], uk["period"], uk["value"], uk["price_base"]) == (
        2025, "2024/25", 32025, "2024/25",
    )
    assert (us["year"], us["survey_year"], us["value"], us["price_base"]) == (
        2025, 2026, 72025, "2025",
    )
    assert "population controls" in frame.loc[
        frame.country.eq("United States") & frame.year.eq(2024), "status"
    ].iloc[0]


def test_fetch_preserves_values_and_maps_european_survey_years(monkeypatch, sources):
    monkeypatch.setattr(recent, "ons_link", lambda _: "https://www.ons.gov.uk/uk.xlsx")
    monkeypatch.setattr(recent, "census_link", lambda _: "https://www2.census.gov/us.xlsx")
    uk, us = workbook(ons_rows(), "Table 1"), workbook(census_rows(), "table10")
    monkeypatch.setattr(recent, "download", lambda url: uk if url.endswith("uk.xlsx") else us)
    european = sources[sources.country.isin(recent.EU_COUNTRIES.values())]
    rows = [
        {"country": row.country, "year": row.survey_year, "value": row.value, "status": row.status}
        for row in european.itertuples()
    ]
    monkeypatch.setattr(recent.eurostat, "fetch", lambda *a, **kw: rows)
    frame = recent.fetch()
    assert frame.loc[frame.country.eq("Poland"), "year"].max() == 2024
    assert frame.loc[frame.country.eq("Poland"), "survey_year"].max() == 2025
    assert frame.loc[frame.country.eq("Poland"), "value"].tolist() == european.loc[
        european.country.eq("Poland"), "value"
    ].tolist()


def test_wrong_national_tables_and_non_numeric_income_fail():
    rows = ons_rows()
    rows[5][1] = "Non-retired"
    with pytest.raises(ValueError, match="Unexpected ONS"):
        recent.parse_ons(workbook(rows, "Table 1"), "url")
    rows = census_rows()
    rows[1][0] = "Pre-tax income"
    with pytest.raises(ValueError, match="Unexpected Census"):
        recent.parse_census(workbook(rows, "table10"), "url")
    rows = census_rows()
    rows[-2][-1] = "suppressed"
    with pytest.raises(ValueError):
        recent.parse_census(workbook(rows, "table10"), "url")


def test_discovery_uses_latest_dated_source_and_historical_post_tax_table(monkeypatch):
    assert "2025/" in recent.ons_link(b"""
        <a href="/file?uri=/dataset/financialyearending2024/old.xlsx">xlsx</a>
        <a href="/file?uri=/dataset/financialyearending2025/new.xlsx">xlsx</a>
    """)
    requested = []

    def download(url):
        requested.append(url)
        return b"""<a href="https://www2.census.gov/tables/table10.xlsx">
          Selected Measures of Household Post-Tax Income Dispersion: 2009 to 2025
        </a>"""

    monkeypatch.setattr(recent, "download", download)
    link = recent.census_link(b"""
      <a href="/data/tables/2025/demo/income-poverty/p60-286.html">Old</a>
      <a href="/data/tables/2026/demo/income-poverty/p60-289.html">New</a>
    """)
    assert requested == ["https://www.census.gov/data/tables/2026/demo/income-poverty/p60-289.html"]
    assert link.endswith("table10.xlsx")
    with pytest.raises(ValueError, match="no dated"):
        recent.ons_link(b"<html></html>")
    with pytest.raises(ValueError, match="no dated"):
        recent.census_link(b"<html></html>")


@pytest.mark.parametrize("change", ["duplicate", "missing", "definition", "survey", "nan", "unit"])
def test_validation_rejects_missing_or_incompatible_observations(sources, change):
    if change == "duplicate":
        sources = pd.concat([sources, sources.iloc[[0]]])
    elif change == "missing":
        sources = sources.iloc[1:]
    elif change == "definition":
        sources.loc[0, "definition"] = "OECD square-root scale"
    elif change == "survey":
        sources.loc[sources.country.eq("Poland"), "survey_year"] -= 1
    elif change == "nan":
        sources.loc[0, "value"] = float("nan")
    elif change == "unit":
        sources.loc[sources.country.eq("Poland"), "unit"] = "USD"
    with pytest.raises(ValueError):
        recent.validate(sources)


def test_failed_live_source_preserves_saved_inputs_and_outputs(monkeypatch, tmp_path, sources):
    path = tmp_path / "income.csv"
    sources.to_csv(path, index=False)
    original = path.read_bytes()

    def fail():
        raise ValueError("Incomplete national source")

    monkeypatch.setattr(recent, "fetch", fail)
    with pytest.raises(ValueError, match="Incomplete national source"):
        recent.main(["--csv", str(path), "--out", str(tmp_path / "charts")])
    assert path.read_bytes() == original
    assert not (tmp_path / "charts").exists()


def test_refresh_does_not_drop_a_previously_published_later_year(sources):
    previous = sources.copy()
    previous.loc[previous.country.eq("Poland") & previous.year.eq(2024), "year"] = 2025
    with pytest.raises(ValueError, match="lost previously published"):
        recent.validate(sources, previous)


def test_newer_charts_separate_definitions_reference_years_and_hover(monkeypatch, tmp_path, sources):
    figures = []
    original = recent.save_chart

    def save(fig, *args, **kwargs):
        figures.append(fig)
        return original(fig, *args, **kwargs)

    monkeypatch.setattr(recent, "save_chart", save)
    paths = recent.charts(sources, tmp_path)
    assert all(path.exists() and path.with_suffix(".json").exists() for path in paths)
    national, european = figures
    assert len(national.axes) == 2
    assert "Not adjusted for household size" in national.axes[1].get_title(loc="left")
    assert "2024/25 £" in national.axes[0].get_ylabel()
    assert "2025 $" in national.axes[1].get_ylabel()
    assert "not comparable" in " ".join(t.get_text() for t in national.texts)
    assert set(line.get_label() for line in european.axes[0].lines) == set(recent.EU_COUNTRIES.values())
    assert all(max(line.get_xdata()) == 2024 for line in european.axes[0].lines)
    assert all(pd.isna(line.get_ydata()).any() for line in european.axes[0].lines)
    assert european.axes[0].collections
    for fig in figures:
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        note = fig.texts[-1].get_window_extent(renderer)
        assert all(not note.overlaps(ax.get_window_extent(renderer)) for ax in fig.axes)
    assert ("-m", "europe_data.recent_income") in refresh_data.STEPS["gdp-income"]
