import csv
import io
import json

import pandas as pd
import pytest

from europe_data import income_estimates as model, oecd_income


def observed():
    return pd.DataFrame([
        dict(iso3=code, country=country, year=year, metric=oecd_income.METRIC,
             value=value, unit=oecd_income.UNIT)
        for code, country in model.COUNTRIES.items()
        for year, value in [(2022, 29000.), (2023, 30000.)]
    ])


def macro():
    data = {}
    for index, code in enumerate(model.COUNTRIES, start=1):
        for year, income, population, price_growth in [
            (2023, 100., 10., 1.), (2024, 120., 10., 1.1), (2025, 150., 12., 1.2),
        ]:
            data[code, year, model.INCOME_MEASURES[code]] = income
            data[code, year, "POP"] = population
            data[code, year, "PCP"] = index * 100 * price_growth
    data["USA", 2024, "PCP"] = 200 * 1.05
    data["USA", 2025, "PCP"] = 200 * 1.1
    return data


def estimates(actual=None, inputs=None):
    return model.build(
        observed() if actual is None else actual, macro() if inputs is None else inputs,
        through=2025, vintage="OECD Economic Outlook 119",
        source_url=f"{model.BASE}/{model.FLOW},1.5/fixture",
        retrieved="2026-10-18T12:00:00+00:00",
    )


def macro_csv(change=None):
    fields = [
        "DATAFLOW", "REF_AREA", "MEASURE", "FREQ", "TIME_PERIOD", "OBS_VALUE",
        "UNIT_MEASURE", "UNIT_MULT", "PRICE_BASE", "BASE_PER", "CURRENCY",
    ]
    rows = []
    for (code, year, measure), value in macro().items():
        rows.append(dict(
            DATAFLOW="OECD.ECO.MAD:DSD_EO@DF_EO(1.5)", REF_AREA=code, MEASURE=measure,
            FREQ="A", TIME_PERIOD=str(year), OBS_VALUE=str(value), UNIT_MULT="0",
            UNIT_MEASURE="PS" if measure == "POP" else "GR" if measure == "PCP" else "XDC",
            PRICE_BASE="D" if measure == "PCP" else "" if measure == "POP" else "V",
            BASE_PER=("2017" if code == "USA" else "2020") if measure == "PCP" else "",
            CURRENCY=model.CURRENCIES[code] if measure in {"YDH", "YDH_G"} else "",
        ))
    if change:
        change(rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def test_model_calibrates_growth_and_records_unrounded_inputs_without_changing_actuals():
    actual = observed()
    before = actual.copy(deep=True)
    result = model.validate(estimates(actual), actual)
    uk = result[(result["iso3"] == "GBR") & (result["year"] == 2025)].iloc[0]
    assert uk["unrounded_value"] == pytest.approx(30000 * 1.25 / (1.2 / 1.1))
    assert uk["value"] == 34400
    us = result[(result["iso3"] == "USA") & (result["year"] == 2025)].iloc[0]
    assert us["value"] == 37500
    assert len(result) == 12
    pd.testing.assert_frame_equal(actual, before)
    scaled = macro()
    for (code, year, measure), value in list(scaled.items()):
        if measure == "PCP":
            scaled[code, year, measure] = value * (3 if code == "USA" else 7)
        elif measure in {"YDH", "YDH_G"}:
            scaled[code, year, measure] = value * 1000
    pd.testing.assert_series_equal(estimates()["value"], estimates(inputs=scaled)["value"])


def test_actual_observations_replace_estimates_and_recalibrate_the_remaining_tail():
    actual = observed()
    new = actual.iloc[[0]].assign(
        iso3="USA", country="United States", year=2024, value=36000.,
    )
    actual = pd.concat([actual, new], ignore_index=True)
    result = model.validate(estimates(actual), actual)
    us = result[result["iso3"] == "USA"]
    assert us["year"].tolist() == [2025]
    assert us["base_year"].tolist() == [2024]
    assert us["base_value"].tolist() == [36000.]
    with pytest.raises(ValueError, match="identity, coverage"):
        model.validate(estimates(), actual)
    complete = pd.concat([actual, new.assign(year=2025, value=37500.)], ignore_index=True)
    assert "USA" not in set(model.validate(estimates(complete), complete)["iso3"])
    with pytest.raises(ValueError, match="two-year"):
        model.anchors(observed(), 2026)


@pytest.mark.parametrize("failure", ["missing", "duplicate", "formula", "anchor", "status", "release"])
def test_saved_models_reject_incomplete_mislabelled_or_stale_calculations(failure):
    frame = estimates()
    if failure == "missing":
        frame = frame.iloc[1:]
    elif failure == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    else:
        column, value = {
            "formula": ("value", 1), "anchor": ("base_value", 10000),
            "status": ("status", "OBSERVED"), "release": ("source_vintage", "unknown"),
        }[failure]
        frame.loc[0, column] = value
    with pytest.raises(ValueError):
        model.validate(frame, observed())


@pytest.mark.parametrize("field,value", [
    ("UNIT_MEASURE", "USD"), ("PRICE_BASE", "L"), ("CURRENCY", "JPY"),
    ("FREQ", "Q"), ("OBS_VALUE", "nan"), ("DATAFLOW", "other"),
])
def test_macro_inputs_fail_on_incompatible_definitions_or_values(field, value):
    text = macro_csv(lambda rows: rows[0].update({field: value}))
    with pytest.raises(ValueError):
        model.parse_macro(text, model.FLOW + ",1.5")


def test_macro_parser_preserves_country_specific_gross_net_conventions_and_reference_years():
    parsed = model.parse_macro(macro_csv(), model.FLOW + ",1.5")
    assert parsed == macro()
    blank_currency = macro_csv(
        lambda rows: [row.update(CURRENCY="") for row in rows if row["MEASURE"] in {"YDH", "YDH_G"}],
    )
    assert model.parse_macro(blank_currency, model.FLOW + ",1.5") == macro()
    changed_basis = macro_csv(
        lambda rows: next(row for row in rows if row["MEASURE"] == "PCP").update(BASE_PER="1990"),
    )
    with pytest.raises(ValueError, match="reference year changed"):
        model.parse_macro(changed_basis, model.FLOW + ",1.5")
    missing = macro()
    del missing["POL", 2025, "YDH"]
    with pytest.raises(ValueError, match="Missing income-model input"):
        estimates(inputs=missing)


def test_failed_fetch_preserves_the_previous_saved_model(monkeypatch, tmp_path):
    source, saved = tmp_path / "observed.csv", tmp_path / "estimates.csv"
    observed().to_csv(source, index=False)
    saved.write_text("previous verified model\n")

    def fail(*args, **kwargs):
        raise ValueError("incomplete official macro response")

    monkeypatch.setattr(model, "fetch", fail)
    with pytest.raises(ValueError, match="incomplete official"):
        model.main(["--observed", str(source), "--csv", str(saved)])
    assert saved.read_text() == "previous verified model\n"


@pytest.mark.parametrize("comparison,names", [
    ("four_country", {"United Kingdom", "United States", "Germany", "France"}),
    ("uk_us_eu", {"United Kingdom", "United States"}),
])
def test_income_variants_preserve_selected_observations_and_distinct_model_tails(
    comparison, names, monkeypatch, tmp_path,
):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from europe_data import plot_uk_decline as plots
    from vizstyle import country_color

    actual = observed()
    wide = actual[["country", "year", "value"]].rename(columns={"value": oecd_income.METRIC})
    eu = pd.DataFrame([
        dict(country=plots.EU_EUROSTAT[0], year=year, median_disposable_income=value)
        for year, value in [(2023, 11000.), (2024, 12000.), (2025, 13000.)]
    ])
    wide = pd.concat([wide, eu], ignore_index=True)
    before = wide.copy(deep=True)
    captured = []
    original_save = plots.save_chart

    def save(fig, *args, **kwargs):
        captured.append(fig)
        return original_save(fig, *args, **kwargs)

    monkeypatch.setattr(plots, "save_chart", save)
    plots.fig_median_income_oecd(wide, tmp_path, estimates=estimates(), comparison=comparison)
    assert len(captured) == 1
    fig, = captured
    ax = fig.axes[0]
    assert {line.get_label() for line in ax.lines} == names | {
        f"{name} (model estimate)" for name in names
    }
    for line in ax.lines:
        name = line.get_label().replace(" (model estimate)", "")
        assert line.get_color() == country_color(name)
        if "(model estimate)" in line.get_label():
            assert list(line.get_xdata()) == [2024, 2025]
            assert line.get_markerfacecolor() == plots.SUBSTACK_BG
        else:
            assert list(line.get_xdata()) == [2022, 2023]
            assert list(line.get_ydata()) == [29000., 30000.]
    if comparison == "uk_us_eu":
        assert len(fig.axes) == 2
        reference = fig.axes[1]
        assert len(reference.lines) == 1
        line, = reference.lines
        assert line.get_label() == "EU-27"
        assert line.get_color() == country_color("EU")
        assert list(line.get_xdata()) == [2022, 2023, 2024]
        assert list(line.get_ydata()) == [11000., 12000., 13000.]
        assert "PPS" in reference.get_ylabel()
        assert "survey year minus one" in reference.get_xlabel()
        assert not reference.patches
        assert "Different vertical scales" in " ".join(fig.texts[-1].get_text().split())
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        assert fig.texts[-1].get_window_extent(renderer).y1 < reference.xaxis.label.get_window_extent(renderer).y0
        assert reference.title.get_window_extent(renderer).y1 + 5 < ax.get_window_extent(renderer).y0
        data = json.loads((tmp_path / "median_disposable_income_oecd_uk_us_eu.json").read_text())
        series = next(item for item in data["series"] if item["label"] == "EU-27")
        assert "PPS" in series["y_label"]
        assert "survey year minus one" in series["x_label"]
        assert [point[2] for point in series["points"]] == ["2022", "2023", "2024"]
    pd.testing.assert_frame_equal(wide, before)


def test_income_eu_version_refuses_missing_reference_instead_of_averaging_nations(tmp_path):
    from europe_data import plot_uk_decline as plots

    wide = observed()[["country", "year", "value"]].rename(columns={"value": oecd_income.METRIC})
    wide["median_disposable_income"] = float("nan")
    with pytest.raises(ValueError, match="published EU median-income reference"):
        plots.fig_median_income_oecd(wide, tmp_path, estimates=estimates(), comparison="uk_us_eu")
    assert not list(tmp_path.glob("*.png"))


def test_future_observations_render_as_actuals_and_eventually_remove_the_model_tail(monkeypatch, tmp_path):
    from europe_data import plot_uk_decline as plots

    actual = pd.concat([
        observed(), observed().query("year == 2023 and iso3 == 'USA'").assign(year=2024, value=36000.),
    ], ignore_index=True)
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda fig, *a, **kw: captured.append(fig))

    def render(frame):
        wide = frame[["country", "year", "value"]].rename(columns={"value": oecd_income.METRIC})
        plots.fig_median_income_oecd(wide, tmp_path, estimates=estimates(frame))
        return captured[-2].axes[0]

    ax = render(actual)
    us = next(line for line in ax.lines if line.get_label() == "United States")
    modelled = next(line for line in ax.lines if line.get_label() == "United States (model estimate)")
    assert list(us.get_xdata()) == [2022, 2023, 2024]
    assert us.get_ydata()[-1] == 36000.
    assert list(modelled.get_xdata()) == [2025]
    complete = pd.concat([
        observed(),
        observed().query("year == 2023").assign(year=2024, value=36000.),
        observed().query("year == 2023").assign(year=2025, value=37500.),
    ], ignore_index=True)
    ax = render(complete)
    assert len(ax.lines) == 6
    assert all(list(line.get_xdata()) == [2022, 2023, 2024, 2025] for line in ax.lines)
    assert not ax.patches


def test_model_tail_is_distinct_in_rendering_and_hover_while_history_stays_observed(monkeypatch, tmp_path):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from europe_data import plot_uk_decline as plots
    from scripts import refresh_data

    actual = observed()
    wide = actual[["country", "year", "value"]].rename(columns={"value": oecd_income.METRIC})
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda fig, *a, **kw: captured.append(fig))
    plots.fig_median_income_oecd(wide, tmp_path, estimates=estimates())
    ax, history = [fig.axes[0] for fig in captured]
    assert "2022\u20132025" in ax.get_title()
    assert len(ax.lines) == 12
    assert len(ax.patches) == 1
    for line in ax.lines:
        if "model estimate" in line.get_label():
            assert list(line.get_xdata()) == [2024, 2025]
            assert line.get_linestyle() == "-."
            assert line.get_markerfacecolor() == plots.SUBSTACK_BG
        else:
            assert list(line.get_xdata()) == [2022, 2023]
            assert list(line.get_ydata()) == [29000., 30000.]
    assert len(history.lines) == 6
    assert all(list(line.get_xdata()) == [2022, 2023] for line in history.lines)
    assert "NOT observed OECD medians" in captured[0].texts[0].get_text()
    canvas = FigureCanvasAgg(captured[0])
    canvas.draw()
    renderer = canvas.get_renderer()
    assert captured[0].texts[0].get_window_extent(renderer).y1 + 5 < (
        ax.xaxis.label.get_window_extent(renderer).y0
    )
    steps = refresh_data.STEPS["gdp-income"]
    assert steps.index(("-m", "europe_data.fetch_data")) < (
        steps.index(("-m", "europe_data.income_estimates"))
    ) < steps.index(("-m", "europe_data.plot_uk_decline"))
