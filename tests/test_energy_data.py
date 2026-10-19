import io
import json

from matplotlib.backends.backend_agg import FigureCanvasAgg
import pandas as pd
import pytest

from energy_data import charts, sources
from energy_data.__main__ import main


def workbook(fuel, change=None, *, industrial=False):
    title = (
        "Annual non-domestic electricity prices in the EU including taxes "
        "(excluding VAT and other recoverable taxes and levies)"
        if industrial else f"Annual domestic {fuel} prices in the EU including all taxes and levies"
    )
    band = "2,000 - 19,999 MWh" if industrial else (
        "2,500 - 4,999" if fuel == "electricity" else "5,557 - 55,556"
    )
    rows = [
        [title],
        ["In pence per kWh."],
        ["Prices are converted to sterling using the exchange rate at time of publication for each period."],
        ["Medium consumers: consuming " + band + " kWh per annum."],
        ["Annual average is presented as the unweighted average of semesters one and two for the year."],
        ["Customer size", "Year", "UK", "Germany", "France"],
    ]
    base = 18 if fuel == "electricity" else 5
    rows.extend([
        ["Medium", year, base + (year - 2008) * .2, base * 1.2 + (year - 2008) * .3, base * .8]
        for year in range(2008, 2026)
    ])
    rows.append(["Small", 2025, 999, 999, 999])
    if change:
        change(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([["Energy Prices"], ["Publication date: 29/09/2026"]]).to_excel(
            writer, sheet_name="Cover sheet", index=False, header=False,
        )
        pd.DataFrame(rows).to_excel(writer, sheet_name="Annual incl tax", index=False, header=False)
    return output.getvalue()


@pytest.fixture
def energy_frame():
    european = pd.concat([
        sources.parse_workbook(workbook(fuel), fuel, f"https://assets.publishing.service.gov.uk/{fuel}.xlsx")
        for fuel in sources.TABLES
    ])
    years = range(2008, 2026)
    return sources.validate(sources.add_us(
        european,
        {"electricity": {year: 10. for year in years}, "gas": {year: 12. for year in years}},
        {year: 1000. for year in years}, {year: .8 for year in years},
        release="2026-10-18",
    ))


@pytest.fixture
def industrial_frame():
    europe = sources.parse_workbook(
        workbook("electricity", industrial=True), "electricity",
        "https://assets.publishing.service.gov.uk/industrial.xlsx", industrial=True,
    )
    return sources.validate(sources.add_us(
        europe, {"electricity": {year: 10. for year in range(2008, 2026)}}, {},
        {year: .8 for year in range(2008, 2026)}, release="2026-10-19", industrial=True,
    ), industrial=True)


def test_industrial_profile_selects_business_band_and_industrial_not_residential_prices(industrial_frame):
    assert len(industrial_frame) == 72
    europe = industrial_frame.query("iso3 != 'USA'")
    assert europe["consumer_scope"].eq("2,000-19,999 MWh/year").all()
    assert europe["tax_basis"].str.contains("excluding VAT").all()
    us = industrial_frame.query("iso3 == 'USA'")
    assert us["source_table"].eq("ESICUUS").all()
    assert us["value"].eq(8.).all()
    with pytest.raises(ValueError, match="coverage"):
        sources.validate(industrial_frame)
    for column, value in [
        ("source_table", "ESRCUUS"), ("consumer_scope", "All residential customers"),
    ]:
        changed = industrial_frame.copy()
        changed.loc[changed["iso3"] == "USA", column] = value
        with pytest.raises(ValueError):
            sources.validate(changed, industrial=True)
    changed = industrial_frame.copy()
    changed.loc[changed["iso3"] != "USA", "tax_basis"] = "All taxes and levies included"
    with pytest.raises(ValueError, match="tax and consumer"):
        sources.validate(changed, industrial=True)


def test_industrial_source_rejects_household_workbook():
    with pytest.raises(ValueError, match="definition"):
        sources.parse_workbook(
            workbook("electricity"), "electricity",
            "https://assets.publishing.service.gov.uk/industrial.xlsx", industrial=True,
        )


def test_industrial_fetch_failure_preserves_both_saved_datasets(energy_frame, industrial_frame, monkeypatch, tmp_path):
    household, industry = tmp_path / "household.csv", tmp_path / "industry.csv"
    energy_frame.to_csv(household, index=False)
    industrial_frame.to_csv(industry, index=False)
    before = household.read_bytes(), industry.read_bytes()

    def fetch(*, previous=None, industrial=False):
        if industrial:
            raise ValueError("US industrial source unavailable")
        return energy_frame

    monkeypatch.setattr(sources, "fetch", fetch)
    with pytest.raises(ValueError, match="industrial source"):
        main(["--csv", str(household), "--industrial-csv", str(industry), "--out", str(tmp_path / "charts")])
    assert (household.read_bytes(), industry.read_bytes()) == before
    assert not (tmp_path / "charts").exists()


def test_industrial_offline_rebuild_adds_one_four_country_chart_without_fetching(
    energy_frame, industrial_frame, monkeypatch, tmp_path,
):
    household, industry = tmp_path / "household.csv", tmp_path / "industry.csv"
    energy_frame.to_csv(household, index=False)
    industrial_frame.to_csv(industry, index=False)
    before = household.read_bytes(), industry.read_bytes()
    monkeypatch.setattr(sources, "fetch", lambda **kwargs: pytest.fail("Offline energy rebuild fetched data"))
    assert main([
        "--from-csv", str(household), "--industrial-from-csv", str(industry),
        "--out", str(tmp_path / "charts"),
    ]) == 0
    assert (household.read_bytes(), industry.read_bytes()) == before
    files = list((tmp_path / "charts").glob("*.png"))
    assert len(files) == 3
    data = json.loads((tmp_path / "charts/industrial_electricity_prices.json").read_text())
    assert {series["label"] for series in data["series"]} == set(sources.COUNTRIES.values())
    assert sum(len(series["points"]) for series in data["series"]) == 72


def test_default_weekly_entrypoint_fetches_both_profiles_and_regenerates_every_energy_chart(
    energy_frame, industrial_frame, monkeypatch, tmp_path,
):
    from scripts.build_site import ANALYSES
    from scripts.refresh_data import STEPS

    fetched = []

    def fetch(*, previous=None, industrial=False):
        fetched.append(industrial)
        return industrial_frame if industrial else energy_frame

    monkeypatch.setattr(sources, "fetch", fetch)
    household, industry = tmp_path / "household.csv", tmp_path / "industry.csv"
    out = tmp_path / "charts"
    assert main([
        "--csv", str(household), "--industrial-csv", str(industry), "--out", str(out),
    ]) == 0
    assert fetched == [False, True]
    analysis = next(item for item in ANALYSES if item.slug == "energy-costs")
    assert {path.name for path in out.glob("*.png")} == set(analysis.charts)
    for frame, original in (
        (sources.validate(pd.read_csv(household)), energy_frame),
        (sources.validate(pd.read_csv(industry), industrial=True), industrial_frame),
    ):
        pd.testing.assert_frame_equal(frame[["iso3", "fuel", "year", "value"]],
                                      original[["iso3", "fuel", "year", "value"]])
    assert STEPS["energy-costs"] == (("-m", "energy_data"),)


def test_industrial_chart_discloses_non_household_scope_and_tax_treatment(industrial_frame, monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: captured.append(fig))
    paths = charts.make_charts(industrial_frame, tmp_path, industrial=True)
    assert [p.name for p in paths] == ["industrial_electricity_prices.png"]
    fig = captured[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    text = " ".join(" ".join(item.get_text() for item in fig.texts).split())
    assert "medium non-household users; US: industrial sector" in text
    assert "excludes VAT and other recoverable" in text
    assert "ESICUUS" in text and "ESRCUUS" not in text
    ax = fig.axes[0]
    assert len(ax.lines) == 4
    assert all(label.get_text().endswith("p") for label in ax.get_yticklabels())
    ticks = ax.get_xticks()
    assert all(right - left == 2 for left, right in zip(ticks, ticks[1:]))
    note = next(item for item in fig.texts if item.get_text().startswith("Sources:"))
    assert note.get_window_extent(canvas.get_renderer()).y1 < ax.xaxis.label.get_window_extent(canvas.get_renderer()).y0


def test_comparison_selects_tax_inclusive_medium_prices_and_preserves_raw_units(energy_frame):
    assert len(energy_frame) == 144
    uk = energy_frame.query("iso3 == 'GBR' and fuel == 'electricity' and year == 2025").iloc[0]
    assert uk["value"] == pytest.approx(21.4)
    assert uk["source_value"] == uk["value"]
    assert uk["conversion_factor"] == 1
    assert energy_frame["value"].max() < 999
    us = energy_frame.query("iso3 == 'USA' and year == 2025").set_index("fuel")
    assert us.loc["electricity", "value"] == 8
    assert us.loc["gas", "value"] == pytest.approx(12 * .8 * 100 / (1000 * 1000 / 3412))
    assert us["consumer_scope"].eq("All residential customers").all()
    assert us["vintage_kind"].eq("Retrieved source snapshot").all()
    assert energy_frame.query("iso3 != 'USA'")["vintage_kind"].eq("Workbook publication date").all()


def test_parser_keeps_source_revisions_without_selecting_a_different_band():
    frame = sources.parse_workbook(
        workbook("gas", lambda rows: rows[6].__setitem__(1, "2008r")), "gas",
        "https://assets.publishing.service.gov.uk/gas.xlsx",
    )
    assert frame.query("year == 2008")["status"].eq("r").all()
    assert set(frame["consumer_scope"]) == {sources.BANDS["gas"]}


@pytest.mark.parametrize("index,value", [
    (0, "Annual prices excluding tax"), (1, "In euro per kWh."),
    (3, "Medium consumers: 1,000 - 2,499 kWh"), (4, "Annual prices use only the latest semester"),
])
def test_parser_rejects_changed_energy_definitions(index, value):
    with pytest.raises(ValueError, match="definition"):
        sources.parse_workbook(
            workbook("electricity", lambda rows: rows[index].__setitem__(0, value)),
            "electricity", "https://assets.publishing.service.gov.uk/electricity.xlsx",
        )


def test_eia_uses_published_annual_rate_not_mean_of_monthly_prices():
    url, code, unit, description = sources.EIA["electricity"]
    frame = pd.DataFrame([
        dict(MSN=code, YYYYMM=period, Value=value, Description=description, Unit=unit)
        for period, value in [("196013", "Not Available"), ("202501", "99"), ("202502", "77"), ("202513", "17.3")]
    ])
    assert sources.parse_eia(frame.to_csv(index=False), code, unit, description) == {2025: 17.3}
    frame.loc[3, "Value"] = "Not Available"
    with pytest.raises(ValueError, match="Invalid energy"):
        sources.parse_eia(frame.to_csv(index=False), code, unit, description)
    frame.loc[3, "Value"] = "17.3"
    frame["Unit"] = "Dollars per Kilowatthour"
    with pytest.raises(ValueError, match="Unexpected EIA"):
        sources.parse_eia(frame.to_csv(index=False), code, unit, description)


@pytest.mark.parametrize("column,value", [
    ("value", 0), ("source_value", 200), ("conversion_factor", .01),
    ("unit", "USD/kWh"), ("consumer_scope", "Industrial"), ("tax_basis", "Before VAT"),
])
def test_validation_rejects_wrong_price_units_scope_and_calculation(energy_frame, column, value):
    energy_frame.loc[0, column] = value
    with pytest.raises(ValueError):
        sources.validate(energy_frame)


def test_missing_or_wrong_fx_and_heat_inputs_cannot_silently_change_us_prices(energy_frame):
    for column in ("gbp_per_usd", "btu_per_cubic_foot"):
        changed = energy_frame.copy()
        changed.loc[(changed["iso3"] == "USA") & (changed["fuel"] == "gas"), column] = float("nan")
        with pytest.raises(ValueError):
            sources.validate(changed)
    changed = energy_frame.copy()
    changed.loc[changed["iso3"] == "USA", "gbp_per_usd"] *= 2
    with pytest.raises(ValueError, match="conversion"):
        sources.validate(changed)
    with pytest.raises(ValueError, match="history"):
        sources.validate(energy_frame.iloc[1:])
    with pytest.raises(ValueError, match="duplicate"):
        sources.validate(pd.concat([energy_frame, energy_frame.iloc[:1]]))


def test_world_bank_rates_reject_missing_inverted_or_incomplete_source():
    payload = [
        dict(pages=1, sourceid="2", total=1),
        [dict(countryiso3code="GBR", indicator={"id": "PA.NUS.FCRF"}, date="2025", value=.76)],
    ]
    assert sources.parse_fx(payload) == {2025: .76}
    payload[1][0]["value"] = None
    with pytest.raises(ValueError):
        sources.parse_fx(payload)
    payload[1][0]["value"] = .76
    payload[1][0]["indicator"]["id"] = "PA.NUS.PPP"
    with pytest.raises(ValueError):
        sources.parse_fx(payload)


def test_source_failure_preserves_previous_saved_prices(energy_frame, monkeypatch, tmp_path):
    path = tmp_path / "energy.csv"
    energy_frame.to_csv(path, index=False)
    before = path.read_bytes()

    def fail(**kwargs):
        raise ValueError("missing US annual heat-content input")

    monkeypatch.setattr(sources, "fetch", fail)
    with pytest.raises(ValueError, match="heat-content"):
        main(["--csv", str(path), "--out", str(tmp_path / "charts")])
    assert path.read_bytes() == before
    assert not (tmp_path / "charts").exists()


def test_offline_rebuild_keeps_saved_inputs_and_all_four_hover_series(energy_frame, monkeypatch, tmp_path):
    path = tmp_path / "energy.csv"
    energy_frame.to_csv(path, index=False)
    before = path.read_bytes()
    monkeypatch.setattr(sources, "fetch", lambda **kwargs: pytest.fail("Offline rebuild fetched data"))
    assert main(["--from-csv", str(path), "--out", str(tmp_path / "charts")]) == 0
    assert path.read_bytes() == before
    for fuel in sources.TABLES:
        data = json.loads((tmp_path / "charts" / f"household_{fuel}_prices.json").read_text())
        assert {series["label"] for series in data["series"]} == set(sources.COUNTRIES.values())
        assert sum(len(series["points"]) for series in data["series"]) == 72


def test_comparison_disclosures_gridlines_and_notes_remain_visible(energy_frame, monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(charts, "save_chart", lambda fig, *args, **kwargs: captured.append(fig))
    charts.make_charts(energy_frame, tmp_path)
    for fig in captured:
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        ax = fig.axes[0]
        assert len(ax.lines) == 4
        ticks = ax.get_xticks()
        assert all(right - left == 2 for left, right in zip(ticks, ticks[1:]))
        assert all("(2025)" in text.get_text() for text in ax.texts if text.get_text())
        first_year = ax.get_xticklabels()[0].get_window_extent(renderer)
        assert all(text.get_text().endswith("p") for text in ax.get_yticklabels())
        zero = next(text for text in ax.get_yticklabels() if text.get_text() == "0p").get_window_extent(renderer)
        assert first_year.y1 + 5 < zero.y0
        assert zero.x1 + 5 < first_year.x0
        assert all(line.get_visible() for line in ax.get_ygridlines())
        texts = " ".join(text.get_text() for text in fig.texts)
        assert "medium-use households; US: all residential" in texts
        assert "not a matched-usage tariff comparison" in texts
        assert "purchasing-power-adjusted" in texts
        note = next(text for text in fig.texts if text.get_text().startswith("Sources:"))
        assert note.get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0
        for line in ax.lines:
            assert list(line.get_xdata()) == list(range(2008, 2026))
