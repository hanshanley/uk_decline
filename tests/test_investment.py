from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
import pandas as pd
import pytest
import requests

from investment_data import charts, sources
from investment_data.__main__ import main
from scripts.chart_data import load_chart_data


def oecd_csv(name, records):
    flow, dimensions = sources.FLOWS[name]
    agency, dataset, version = flow.split(",")
    fields = [
        "DATAFLOW", *dimensions, "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT", "CURRENCY",
        "OBS_STATUS", "OBS_STATUS_2", "OBS_STATUS_3", "CONF_STATUS",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        code = record.get("REF_AREA", "GBR")
        row = {key: value.split("+")[0] for key, value in dimensions.items()}
        row.update(
            DATAFLOW=f"{agency}:{dataset}({version})", REF_AREA=code, TIME_PERIOD=2023,
            OBS_VALUE=1000 if name == "gdp" else 20_000, UNIT_MULT=9 if name == "gdp" else 6,
            CURRENCY=sources.CURRENCIES.get(code, ""), OBS_STATUS="A", CONF_STATUS="F",
        )
        if name in ("transport", "research"):
            row.update(OBS_VALUE=.8 if name == "transport" else 2.7, UNIT_MULT=0, CURRENCY="")
        row.update(record)
        writer.writerow(row)
    return output.getvalue()


def eu_budget_payload():
    years = list(range(2004, 2026))
    coordinates = dict(
        freq=["A"], nabs07=["TOTAL"], unit=["PC_GDP"], geo=["EU27_2020"],
        time=[str(year) for year in years],
    )
    return {
        "id": list(coordinates), "size": [len(values) for values in coordinates.values()],
        "dimension": {
            dim: {"category": {"index": {code: i for i, code in enumerate(values)}}}
            for dim, values in coordinates.items()
        },
        "value": {str(i): .7 for i in range(len(years))},
        "status": {str(i): "e" for i in range(len(years))},
    }


def military_payload():
    observations = [
        dict(countryiso3code=code, date=str(year), value=2.3, obs_status="",
             indicator={"id": sources.MILITARY_INDICATOR})
        for code in ("GBR", "USA", "POL", "EUU") for year in range(2000, 2026)
    ]
    return [dict(page=1, pages=1, sourceid="2", total=len(observations)), observations]


@pytest.fixture
def funding_frame(monkeypatch):
    for_name = {
        "transport": sources.TRANSPORT, "capital": sources.CAPITAL,
        "budget": sources.BUDGET, "research": sources.RESEARCH,
    }
    responses = {}
    for name in sources.FLOWS:
        if name == "gdp":
            records = [
                dict(REF_AREA=code, TIME_PERIOD=year)
                for code in sources.CURRENCIES for year in range(2000, 2026)
            ]
        else:
            records = []
            for code, (first, last, missing) in sources.BASELINES[for_name[name]].items():
                if name == "budget" and code == "EU27_2020":
                    continue
                for year in range(first, last + 1):
                    if year in missing:
                        continue
                    row = dict(REF_AREA=code, TIME_PERIOD=year)
                    if name == "research" and code == "GBR" and year == 2018:
                        row.update(OBS_STATUS="B", OBS_STATUS_2="E", OBS_STATUS_3="P")
                    records.append(row)
        responses[name] = oecd_csv(name, records)

    def get_text(url, **kwargs):
        name = next(name for name, (flow, _) in sources.FLOWS.items() if f"/{flow}/" in url)
        assert kwargs["params"]["format"] == "csvfile"
        return responses[name]

    monkeypatch.setattr(sources, "get_text", get_text)
    monkeypatch.setattr(
        sources, "get_json",
        lambda url, **kwargs: eu_budget_payload() if url == sources.EU_BUDGET_URL else military_payload(),
    )
    return sources.fetch()


def test_live_input_builder_scales_units_once_and_preserves_direct_source_percentages(funding_frame):
    row = funding_frame.loc[
        (funding_frame.metric == sources.CAPITAL) & (funding_frame.iso3 == "GBR")
    ].iloc[0]
    assert row.numerator == 20_000_000_000
    assert row.gdp == 1_000_000_000_000
    assert row.value == pytest.approx(2)
    assert row.currency == "GBP"
    assert "/A.GBR.S1.S1.B1GQ." in row.gdp_series_id
    assert all(funding_frame.loc[funding_frame.metric == sources.RESEARCH, "value"] == 2.7)
    assert all(funding_frame.loc[funding_frame.metric == sources.MILITARY, "value"] == 2.3)
    eu = funding_frame.loc[(funding_frame.metric == sources.BUDGET) & (funding_frame.iso3 == "EU27_2020")]
    assert eu.value.eq(.7).all() and eu.gdp.isna().all() and eu.status.eq("E").all()
    uk_break = funding_frame.loc[
        (funding_frame.metric == sources.RESEARCH) & (funding_frame.iso3 == "GBR")
        & (funding_frame.year == 2018)
    ].iloc[0]
    assert uk_break.status == "B;E;P"
    assert "F" not in set(funding_frame.status)


@pytest.mark.parametrize("change", [
    {"SECTOR": "S1"}, {"TRANSACTION": "P51N"}, {"PRICE_BASE": "Q"},
    {"UNIT_MEASURE": "USD_PPP"}, {"FREQ": "Q"}, {"CURRENCY": "USD"},
    {"OBS_VALUE": "nan"}, {"OBS_VALUE": "-1"}, {"UNIT_MULT": ""},
    {"TIME_PERIOD": 2026}, {"OBS_STATUS": "UNKNOWN"},
])
def test_parser_rejects_wrong_investment_definitions_and_invalid_values(change):
    with pytest.raises(ValueError):
        sources.parse_oecd(oecd_csv("capital", [change]), "capital", 2025)


def test_parser_rejects_duplicates_and_does_not_publish_forecasts_or_fill_missing_values():
    with pytest.raises(ValueError, match="Duplicate"):
        sources.parse_oecd(oecd_csv("capital", [{}, {}]), "capital", 2025)
    text = oecd_csv("capital", [
        dict(TIME_PERIOD=2022, OBS_VALUE=""),
        dict(TIME_PERIOD=2023, OBS_STATUS="F"),
        dict(TIME_PERIOD=2024, OBS_VALUE=0, OBS_STATUS="P"),
    ])
    result = sources.parse_oecd(text, "capital", 2025)
    assert list(result) == [("GBR", 2024)]
    assert result["GBR", 2024]["value"] == 0
    assert result["GBR", 2024]["status"] == "P"


def test_spending_ratios_require_same_year_and_currency():
    numerator = {("GBR", 2023): dict(value=20, currency="GBP")}
    for denominator in ({}, {("GBR", 2022): dict(value=100, currency="GBP")},
                        {("GBR", 2023): dict(value=100, currency="USD")}):
        with pytest.raises(ValueError, match="GDP"):
            sources.ratio_rows(sources.CAPITAL, numerator, denominator, "2026-10-15T00:00:00Z")


def test_eu_budget_parser_rejects_component_objectives_in_place_of_total():
    payload = eu_budget_payload()
    payload["dimension"]["nabs07"]["category"]["index"] = {"NABS14": 0}
    with pytest.raises(ValueError, match="definition"):
        sources.parse_eu_budget(payload, "2026-10-15T00:00:00Z", 2025)


@pytest.mark.parametrize("mutation", ["pagination", "indicator", "duplicates"])
def test_military_parser_rejects_incomplete_or_incompatible_data(mutation):
    payload = military_payload()
    if mutation == "pagination":
        payload[0]["pages"] = 2
    elif mutation == "indicator":
        payload[1][0]["indicator"]["id"] = "OTHER"
    else:
        payload[1][1] = payload[1][0]
    with pytest.raises(ValueError):
        rows = sources.parse_military(payload, datetime.now(timezone.utc).isoformat(), 2025)
        # Duplicate source years must not survive the combined validation.
        frame = pd.DataFrame(rows, columns=sources.FIELDS)
        sources.validate(frame)


def test_validation_rejects_lost_history_and_corrupted_ratio(funding_frame):
    with pytest.raises(ValueError, match="baseline coverage"):
        sources.validate(funding_frame.drop(index=0))
    changed = funding_frame.copy()
    index = changed.index[changed.metric == sources.CAPITAL][0]
    changed.loc[index, "value"] += .1
    with pytest.raises(ValueError, match="conversion"):
        sources.validate(changed)
    extra = funding_frame.loc[
        (funding_frame.metric == sources.RESEARCH) & (funding_frame.iso3 == "GBR")
    ].tail(1).copy()
    extra["year"] = 2025
    previous = pd.concat([funding_frame, extra], ignore_index=True)
    with pytest.raises(ValueError, match="previously published"):
        sources.validate(funding_frame, previous=previous)


def test_late_source_failure_keeps_saved_inputs_and_existing_images(funding_frame, monkeypatch, tmp_path):
    csv_path, output = tmp_path / "saved.csv", tmp_path / "charts"
    funding_frame.to_csv(csv_path, index=False)
    saved = csv_path.read_bytes()
    output.mkdir()
    existing = output / "military_expenditure.png"
    existing.write_bytes(b"previous chart")

    def fail(*args, **kwargs):
        raise requests.ConnectionError("government budget API unavailable")

    monkeypatch.setattr(sources, "get_json", fail)
    with pytest.raises(requests.ConnectionError, match="budget API"):
        main(["--csv", str(csv_path), "--out", str(output)])
    assert csv_path.read_bytes() == saved
    assert existing.read_bytes() == b"previous chart"
    assert list(output.iterdir()) == [existing]


def test_comparisons_use_complete_common_years_and_preserve_methods_and_requested_peers(
    funding_frame, monkeypatch, tmp_path,
):
    funding_frame.loc[
        (funding_frame.metric == sources.CAPITAL) & (funding_frame.iso3 == "EU27_2020")
        & (funding_frame.year == 2024), "status"
    ] = "P"
    funding_frame.loc[
        (funding_frame.metric == sources.RESEARCH) & (funding_frame.iso3 == "GBR")
        & (funding_frame.year == 2023), "status"
    ] = "B;D;P"
    captured = []
    original = charts.save_chart

    def save(fig, path, **kwargs):
        captured.append(fig)
        original(fig, path, **kwargs)

    monkeypatch.setattr(charts, "save_chart", save)
    outputs = charts.make_charts(funding_frame, tmp_path)
    assert len(outputs) == 4
    for (metric, *_), path, fig in zip(charts.CHARTS, outputs, captured):
        payload = load_chart_data(tmp_path, path.relative_to(tmp_path))
        actual = {
            (series["label"], int(point[2])): float(point[3].rstrip("%").replace(",", ""))
            for series in payload["series"] for point in series["points"]
        }
        selected = funding_frame.loc[funding_frame.metric == metric]
        if metric != sources.MILITARY:
            selected = selected.loc[selected.iso3 != "POL"]
        first = selected.groupby("iso3").year.min().max()
        last = selected.groupby("iso3").year.max().min()
        selected = selected.loc[selected.year.between(first, last)]
        expected = {
            (row.country, row.year): row.value
            for row in selected.itertuples()
        }
        assert actual == pytest.approx(expected)
        ax = fig.axes[0]
        labels = {text.get_text().lstrip() for text in ax.texts}
        footnote = " ".join(fig.texts[-1].get_text().split())
        if metric == sources.CAPITAL:
            assert f"EU-27 2.00%\n  {last}" in labels
            assert f"EU-27 ({last}): P" in footnote
            assert "P = provisional" in footnote
        elif metric == sources.RESEARCH:
            assert f"United Kingdom 2.70%\n  {last}" in labels
            assert f"United Kingdom ({last}): B,D,P" in footnote
        for country, group in selected.groupby("country"):
            assert set(group.year) == set(range(first, last + 1))
            assert last - first + 1 >= 10
        assert any(line.get_label() == "Poland" for line in ax.lines) == (metric == sources.MILITARY)
        if metric == sources.RESEARCH:
            uk = next(line for line in ax.lines if line.get_label() == "United Kingdom")
            assert np.isnan(uk.get_ydata()[list(uk.get_xdata()).index(2017.5)])
            assert uk.get_ydata()[list(uk.get_xdata()).index(2018)] == 2.7
            assert any(np.allclose(segment, [[2017, 2.7], [2018, 2.7]])
                       for collection in ax.collections for segment in collection.get_segments())
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        assert not fig.texts[-1].get_window_extent(canvas.get_renderer()).overlaps(
            ax.xaxis.label.get_window_extent(canvas.get_renderer())
        )


def test_comparison_refuses_an_uninformative_short_or_spotty_latest_window(funding_frame):
    missing = (
        (funding_frame.metric == sources.BUDGET) & (funding_frame.iso3 == "GBR")
        & (funding_frame.year == 2022)
    )
    with pytest.raises(ValueError, match="Insufficient complete common history"):
        charts.common_period(funding_frame.loc[~missing], sources.BUDGET)


def test_infrastructure_download_failure_preserves_both_saved_inputs(funding_frame, monkeypatch, tmp_path):
    from investment_data import infrastructure

    csv_path = tmp_path / "funding.csv"
    infra_path = tmp_path / "infrastructure.csv"
    funding_frame.to_csv(csv_path, index=False)
    infra_path.write_text("previous infrastructure observations")
    before = csv_path.read_bytes(), infra_path.read_bytes()

    def fail():
        raise requests.ConnectionError("ONS workbook unavailable")

    monkeypatch.setattr(infrastructure, "fetch", fail)
    with pytest.raises(requests.ConnectionError, match="ONS workbook"):
        main(["--csv", str(csv_path), "--infrastructure-csv", str(infra_path),
              "--out", str(tmp_path / "charts")])
    assert before == (csv_path.read_bytes(), infra_path.read_bytes())
    assert not (tmp_path / "charts").exists()
