"""Offline unit tests for the europe_data pipeline (no network required).

Run directly:  python tests/test_pipeline.py
Or with pytest: pytest tests/ -q
"""

from __future__ import annotations

import csv
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from europe_data import combine, countries, eurostat  # noqa: E402


def test_pip_request_pins_ppp_vintage_and_labels_it(monkeypatch):
    from europe_data import pip

    calls = []

    def get_json(url, params=None, timeout=None):
        calls.append(params)
        return [{
            "country_code": "GBR",
            "reporting_level": "national", "welfare_type": "income",
            "reporting_year": 2021, "median": 54.5535,
        }]

    monkeypatch.setattr(pip, "get_json", get_json)
    monkeypatch.setattr(pip, "_valid_codes", {"GBR"})
    rows = pip.fetch(2021, 2021, iso3s=["GBR"])
    assert calls[0]["ppp_version"] == 2021
    assert rows[0]["unit"] == "2021 PPP $ per day"


def test_pip_selected_survey_metadata_survives_long_and_wide(monkeypatch, tmp_path):
    from europe_data import pip

    common = {"country_code": "GBR", "reporting_year": 2021}
    payload = [
        {**common, "reporting_level": "national", "welfare_type": "consumption",
         "median": 20, "survey_comparability": 9},
        {**common, "reporting_level": "urban", "welfare_type": "income",
         "median": 90, "survey_comparability": 8},
        {**common, "reporting_level": "national", "welfare_type": "income",
         "median": 50, "survey_comparability": 0},
        {**common, "reporting_year": 2022, "reporting_level": "national",
         "welfare_type": "income", "median": 55, "survey_comparability": 1},
    ]
    monkeypatch.setattr(pip, "get_json", lambda *args, **kwargs: payload)
    monkeypatch.setattr(pip, "_valid_codes", {"GBR"})
    rows = pip.fetch(2021, 2022, iso3s=["GBR"])
    assert [r["value"] for r in rows] == [50, 55]
    assert [r["survey_comparability"] for r in rows] == [0, 1]
    assert [r["welfare_type"] for r in rows] == ["income", "income"]
    long_path, wide_path = tmp_path / "long.csv", tmp_path / "wide.csv"
    combine.write_long(rows, str(long_path))
    combine.write_wide(rows, str(wide_path))
    with long_path.open() as fh:
        long = list(csv.DictReader(fh))
    with wide_path.open() as fh:
        wide = list(csv.DictReader(fh))
    assert [r["survey_comparability"] for r in long] == ["0", "1"]
    assert [r["median_income_pip__survey_comparability"] for r in wide] == ["0", "1"]
    assert [r["median_income_pip__welfare_type"] for r in wide] == ["income", "income"]
    assert [float(r["median_income_pip"]) for r in wide] == [50, 55]


def test_default_pip_income_scope_includes_poland_and_us_without_filling_gaps(monkeypatch):
    from europe_data import pip

    calls = []
    monkeypatch.setattr(pip, "_valid_codes", {"POL", "USA"})

    def download(url, params=None):
        calls.append(params)
        return [
            {"country_code": code, "reporting_year": 2023, "reporting_level": "national",
             "welfare_type": "income", "median": value, "survey_comparability": 1}
            for code, value in (("POL", 30.), ("USA", 70.))
        ]

    monkeypatch.setattr(pip, "get_json", download)
    rows = pip.fetch(2000, 2026)
    assert set(calls[0]["country"].split(",")) == {"POL", "USA"}
    assert calls[0]["fill_gaps"] == "false"
    assert {row["country"] for row in rows} == {"Poland", "United States"}


def test_empty_source_preserves_europe_outputs_after_another_source_succeeds(monkeypatch, tmp_path):
    import pytest
    from europe_data import fetch_data

    row = {"iso3": "GBR", "country": "United Kingdom", "year": 2021,
           "metric": "gdp_per_capita_real_maddison", "value": 40_000,
           "unit": "2011 international $", "source": "Maddison"}
    monkeypatch.setattr(fetch_data.maddison, "fetch", lambda *args: [row])
    monkeypatch.setattr(fetch_data.pip, "fetch", lambda *args: [])
    paths = [tmp_path / name for name in (
        "pip_median_income.csv", "europe_combined_long.csv",
        "europe_combined_wide.csv", "manifest.json",
    )]
    for path in paths:
        path.write_text("preserved source data\n")
    with pytest.raises(RuntimeError, match="pip: source returned no observations"):
        fetch_data.main([
            "--sources", "maddison", "pip", "--out", str(tmp_path),
            "--start", "2021", "--end", "2021",
        ])
    assert all(path.read_text() == "preserved source data\n" for path in paths)
    assert not (tmp_path / "gdp_per_capita_real_maddison.csv").exists()


def test_country_mappings() -> None:
    # Eurostat quirks: Greece is EL (not GR), UK is UK (not GB).
    assert countries.BY_ISO3["GRC"].eurostat == "EL"
    assert countries.BY_ISO3["GBR"].eurostat == "UK"
    assert countries.iso3_for_eurostat("EL") == "GRC"
    assert countries.iso3_for_eurostat("UK") == "GBR"
    assert countries.name_for_iso3("DEU") == "Germany"
    # Aggregates are reachable via the Eurostat lookup but not the country list.
    geos = countries.eurostat_geos(include_aggregates=True)
    assert "EU27_2020" in geos and "UK" in geos
    assert "EU27_2020" not in countries.eurostat_geos(include_aggregates=False)
    # No duplicate ISO3 codes.
    iso3s = countries.iso3_codes()
    assert len(iso3s) == len(set(iso3s))
    # United States is a GDP peer but NOT part of the European allow-list, so it must not
    # leak into the Eurostat geos or the PIP/European country set.
    assert countries.name_for_iso3("USA") == "United States"
    assert "USA" in countries.gdp_iso3_codes(include_aggregates=False)
    assert "USA" not in countries.iso3_codes()
    assert "US" not in countries.eurostat_geos(include_aggregates=True)


def test_maddison_metric_in_wide_order() -> None:
    # The real (inflation-adjusted) Maddison GDP series must flow into the wide table.
    from europe_data import combine, maddison
    assert maddison.METRIC == "gdp_per_capita_real_maddison"
    assert maddison.METRIC in combine.METRIC_ORDER
    # It is a REAL series (constant-price / inflation-adjusted).
    assert "2011" in maddison.UNIT and "real" in maddison.UNIT.lower()


def test_headline_gdp_is_national_accounts_volume_and_legacy_cpi_is_retained() -> None:
    from europe_data import plot_uk_decline
    from europe_data import combine, worldbank
    assert plot_uk_decline.GDP_METRIC == "gdp_per_capita_constant_usd"
    assert "PPP" not in plot_uk_decline.GDP_METRIC.upper()
    assert "gdp_per_capita_real_usd" in combine.METRIC_ORDER
    # US-CPI deflation retains market FX and is not national-accounts real output.
    nominal = [{"iso3": "GBR", "country": "United Kingdom", "year": 2000,
                "metric": "gdp_per_capita_nominal_usd", "value": 100.0,
                "unit": "nominal, current US$", "source": "x"}]
    real = worldbank.deflate_to_real_usd(nominal, {2000: 80.0, 2015: 100.0}, base_year=2015)
    assert real and real[0]["metric"] == "gdp_per_capita_real_usd"
    assert abs(real[0]["value"] - 125.0) < 1e-9  # 100 * (100/80)
    assert "2015 US$" in real[0]["unit"]


def test_gdp_figures_plot_distinct_volume_and_nominal_series(monkeypatch, tmp_path):
    import pandas as pd
    import pytest
    from europe_data import plot_uk_decline as plots

    rows = []
    for country, volumes, nominal in [
        ("United Kingdom", [40_000, 44_000], [50_000, 100_000]),
        ("United States", [80_000, 96_000], [60_000, 120_000]),
        ("European Union", [60_000, 70_000], [55_000, 110_000]),
        ("Poland", [20_000, 30_000], [25_000, 50_000]),
    ]:
        for i, year in enumerate([2007, 2025]):
            row = {metric: None for metric in combine.METRIC_ORDER}
            row.update(country=country, year=year,
                       gdp_per_capita_constant_usd=volumes[i],
                       gdp_per_capita_nominal_usd=nominal[i],
                       gdp_per_capita_ppp_constant=volumes[i] * 1.1,
                       gdp_per_capita_ppp_current=nominal[i] * 1.3,
                       gdp_per_capita_real_usd=999_000 + i)
            rows.append(row)
    data = pd.DataFrame(rows)
    monkeypatch.setattr(plots.pd, "read_csv", lambda _: data)
    monkeypatch.setattr(plots, "fig_median_income_oecd", lambda *args: None)
    monkeypatch.setattr(plots.gdp_comparisons, "make_chart", lambda *args: None)
    captured = {}
    def save(fig, path, **kwargs):
        captured[Path(path).name] = plots.plt.gcf()
    monkeypatch.setattr(plots, "save_chart", save)
    assert plots.main(["--out", str(tmp_path)]) == 0
    real = captured["gdp_per_capita_real_over_time.png"].axes[0]
    nominal = captured["gdp_per_capita_nominal_over_time.png"].axes[0]
    assert list(real.lines[0].get_ydata()[pd.notna(real.lines[0].get_ydata())]) == pytest.approx([100, 110])
    assert list(real.lines[1].get_ydata()[pd.notna(real.lines[1].get_ydata())]) == pytest.approx([100, 120])
    assert list(nominal.lines[0].get_ydata()[pd.notna(nominal.lines[0].get_ydata())]) == pytest.approx([50, 100])
    ratio = captured["uk_gdp_relative_to_peers.png"].axes[0]
    assert list(ratio.lines[0].get_ydata()[pd.notna(ratio.lines[0].get_ydata())]) == pytest.approx([120, 120])
    for line in [real.lines[0], nominal.lines[0], ratio.lines[0]]:
        assert list(line.get_xdata()) == list(range(2007, 2026))
        assert pd.isna(line.get_ydata()[1:-1]).all()
    assert "2007\u20132025" in ratio.get_title()
    assert "2025" in " ".join(t.get_text() for t in ratio.texts)


def _income_csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _oecd_income_tables():
    income = []
    ppps = []
    for country, currency, factor in (("GBR", "GBP", 0.5), ("FRA", "EUR", 0.8)):
        for year in (2019, 2020):
            income.append({
                "REF_AREA": country, "TIME_PERIOD": str(year), "OBS_VALUE": "20000",
                "OBS_STATUS": "A", "UNIT_MULT": "", "CURRENCY": currency,
                "FREQ": "A", "MEASURE": "INC_DISP", "STATISTICAL_OPERATION": "MEDIAN",
                "UNIT_MEASURE": "XDC_HH_EQ", "AGE": "_T", "METHODOLOGY": "METH2012",
                "PRICE_BASE": "V", "POVERTY_LINE": "_Z",
                "DEFINITION": "D_PREV" if country == "FRA" and year == 2019 else "D_CUR",
            })
            ppps.append({
                "REF_AREA": country, "TIME_PERIOD": str(year), "OBS_VALUE": str(factor),
                "OBS_STATUS": "A", "UNIT_MULT": "0", "CURRENCY": currency,
                "FREQ": "A", "SECTOR": "S1", "COUNTERPART_SECTOR": "S1",
                "TRANSACTION": "PPP_P31S14", "INSTR_ASSET": "F21", "ACTIVITY": "_Z",
                "EXPENDITURE": "_Z", "UNIT_MEASURE": "XDC_USD",
                "PRICE_BASE": "_Z", "TRANSFORMATION": "N",
                "TABLE_IDENTIFIER": "T001",
            })
    income.append({**income[-1], "DEFINITION": "D_PREV", "OBS_VALUE": "19000"})
    return income, ppps


def test_oecd_median_income_uses_consumption_ppps_and_keeps_definition_metadata(monkeypatch, tmp_path):
    from europe_data import oecd_income

    incomes, ppps = _oecd_income_tables()
    calls = []

    def get_text(url, **kwargs):
        calls.append(url)
        return _income_csv(incomes if oecd_income.INCOME_FLOW in url else ppps)

    monkeypatch.setattr(oecd_income, "get_text", get_text)
    rows = oecd_income.fetch(2019, 2020, iso3s=["GBR", "FRA"])
    assert "INC_DISP.MEDIAN.XDC_HH_EQ._T.METH2012.D_CUR+D_PREV" in calls[0]
    assert "PPP_P31S14" in calls[1]
    assert len(rows) == 4
    assert [row["value"] for row in rows if row["iso3"] == "GBR"] == [40000, 40000]
    france = [row for row in rows if row["iso3"] == "FRA"]
    assert [row["value"] for row in france] == [25000, 25000]
    assert [row["income_definition"] for row in france] == ["METH2012/D_PREV", "METH2012/D_CUR"]
    long_path, wide_path = tmp_path / "long.csv", tmp_path / "wide.csv"
    combine.write_long(rows, str(long_path))
    combine.write_wide(rows, str(wide_path))
    with long_path.open() as handle:
        saved = list(csv.DictReader(handle))
    assert saved[0]["national_currency_income"] == "20000.0"
    assert saved[0]["consumption_ppp"] == "0.8"
    with wide_path.open() as handle:
        wide = list(csv.DictReader(handle))
    assert wide[0][f"{oecd_income.METRIC}__income_definition"] == "METH2012/D_PREV"


def test_oecd_median_income_rejects_incomplete_or_incompatible_inputs():
    import pytest
    from europe_data import oecd_income

    for invalid in ("missing-ppp", "zero-ppp", "wrong-currency", "duplicate-income",
                    "duplicate-ppp", "wrong-measure", "missing-income-year"):
        income, ppps = _oecd_income_tables()
        if invalid == "missing-ppp":
            ppps.pop()
        elif invalid == "zero-ppp":
            ppps[0]["OBS_VALUE"] = "0"
        elif invalid == "wrong-currency":
            ppps[0]["CURRENCY"] = "EUR"
        elif invalid == "duplicate-income":
            income.append(income[0])
        elif invalid == "duplicate-ppp":
            ppps.append(ppps[0])
        elif invalid == "wrong-measure":
            income[0]["STATISTICAL_OPERATION"] = "MEAN"
        else:
            income.pop(0)
        with pytest.raises(ValueError):
            oecd_income.build_rows(_income_csv(income), _income_csv(ppps), 2019, 2020, ["GBR", "FRA"])


def test_oecd_income_chart_has_recent_annual_observations_without_bridging_definition_breaks(
    monkeypatch, tmp_path,
):
    import pandas as pd
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from europe_data import oecd_income, plot_uk_decline as plots

    metric = oecd_income.METRIC
    rows = [{
        "country": country, "year": year, metric: 30000 + year,
        f"{metric}__income_definition": (
            "METH2012/D_PREV" if country == "France" and year < 2020 else "METH2012/D_CUR"
        ),
    } for country, *_ in plots.INCOME_PEERS for year in range(2013, 2024)]
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda *args, **kwargs: captured.append(plots.plt.gcf()))
    plots.fig_median_income_oecd(pd.DataFrame(rows), tmp_path)
    fig = captured[0]
    ax = fig.axes[0]
    assert "2013\u20132023" in ax.get_title()
    assert ax.get_xlabel() == "Income year (OECD labels)"
    assert {line.get_label() for line in ax.lines} >= {"United States", "Poland"}
    assert len(ax.lines) == 6
    for line in ax.lines:
        assert sum(pd.notna(line.get_ydata())) == 11
    france = next(line for line in ax.lines if line.get_label() == "France")
    assert pd.isna(france.get_ydata()).any()
    uk = next(line for line in ax.lines if line.get_label() == "United Kingdom")
    assert pd.notna(uk.get_ydata()).all()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[0].get_window_extent(renderer).y1 + 5 < ax.xaxis.label.get_window_extent(renderer).y0


def test_nominal_gdp_ratio_uses_only_shared_years_and_dates_each_peer(monkeypatch, tmp_path):
    import pandas as pd
    from europe_data import plot_uk_decline as plots

    data = pd.DataFrame([
        {"country": "United Kingdom", "year": y, plots.NOMINAL_GDP_METRIC: 50_000}
        for y in [2023, 2025]
    ] + [
        {"country": "United States", "year": 2024, plots.NOMINAL_GDP_METRIC: 90_000},
        {"country": "United States", "year": 2025, plots.NOMINAL_GDP_METRIC: 100_000},
        {"country": "Poland", "year": 2023, plots.NOMINAL_GDP_METRIC: 25_000},
    ])
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda *args, **kwargs:
                        captured.append(plots.plt.gcf()))
    plots.fig_uk_relative(data, tmp_path)
    ax = captured[0].axes[0]
    assert list(ax.lines[0].get_xdata()) == [2025]
    assert list(ax.lines[1].get_xdata()) == [2023]
    assert ax.lines[1].get_marker() == "o"
    text = " ".join(t.get_text() for t in ax.texts)
    assert "United States (2025)" in text and "Poland (2023)" in text
    assert "2023\u20132025" in ax.get_title()


def test_income_chart_preserves_early_history_and_latest_country_observations(monkeypatch, tmp_path):
    import pandas as pd
    from europe_data import oecd_income, plot_uk_decline as plots

    rows = [
        {"country": country, "year": year, oecd_income.METRIC: value}
        for country, *_ in plots.INCOME_PEERS
        for year, value in ((2013, 20000.), (2023, 30000.))
    ]
    rows.extend([
        {"country": "United Kingdom", "year": 2002, oecd_income.METRIC: 12000.},
        {"country": "United States", "year": 2024, oecd_income.METRIC: 45000.},
    ])
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda fig, *a, **k: captured.append(fig))
    plots.fig_median_income_oecd(pd.DataFrame(rows), tmp_path)
    ax = captured[0].axes[0]
    assert "2002\u20132024" in ax.get_title()
    uk, us = ax.lines[:2]
    assert uk.get_xdata()[0] == 2002
    assert uk.get_ydata()[0] == 12000.
    assert us.get_xdata()[-1] == 2024 and us.get_ydata()[-1] == 45000.
    assert pd.isna(uk.get_ydata()[1:11]).all()


def test_simplified_gdp_ratio_shows_us_eu_and_poland(monkeypatch, tmp_path):
    import pandas as pd
    from europe_data import plot_uk_decline as plots

    data = pd.DataFrame([
        {"country": country, "year": 2025, plots.NOMINAL_GDP_METRIC: value}
        for country, value in (
            ("United Kingdom", 50000), ("United States", 80000),
            ("Germany", 52000), ("France", 44000),
            ("European Union", 41000), ("Poland", 25000),
        )
    ])
    saved = []
    monkeypatch.setattr(plots, "save_chart", lambda fig, path, **kwargs:
                        saved.append((path.name, plots.plt.gcf())))
    plots.fig_uk_relative(data, tmp_path)
    plots.fig_uk_relative(data, tmp_path, simplified=True)
    assert [name for name, _ in saved] == [
        "uk_gdp_relative_to_peers.png", "uk_gdp_relative_to_peers_simple.png",
    ]
    original, simplified = [figure.axes[0] for _, figure in saved]
    assert len(original.lines) == 6
    assert len(simplified.lines) == 4
    assert [line.get_ydata()[0] for line in simplified.lines[:-1]] == [160, 82, 50]
    labels = " ".join(text.get_text() for text in simplified.texts)
    assert "United States (2025)" in labels
    assert "EU average (2025)" in labels and "Poland (2025)" in labels
    assert "Germany" not in labels and "France" not in labels
    assert simplified.get_title() == original.get_title()


def test_eurostat_decoder() -> None:
    # Minimal JSON-stat: 1 statinfo x 2 geo x 2 time = 4 obs (row-major).
    payload = {
        "id": ["statinfo", "geo", "time"],
        "size": [1, 2, 2],
        "dimension": {
            "statinfo": {"category": {"index": {"MED_EI": 0}}},
            "geo": {"category": {"index": {"DE": 0, "UK": 1}}},
            "time": {"category": {"index": {"2017": 0, "2018": 1}}},
        },
        # linear index = geo*2 + time
        "value": {"0": 100.0, "1": 110.0, "2": 200.0, "3": 210.0},
    }
    decoded = {
        (c["geo"], c["time"]): v for c, v, _ in eurostat._iter_values(payload)
    }
    assert decoded[("DE", "2017")] == 100.0
    assert decoded[("DE", "2018")] == 110.0
    assert decoded[("UK", "2017")] == 200.0
    assert decoded[("UK", "2018")] == 210.0


def test_eurostat_source_flags_survive_long_and_wide_tables(monkeypatch, tmp_path):
    payload = {
        "id": ["statinfo", "geo", "time"], "size": [1, 1, 2],
        "dimension": {
            "statinfo": {"category": {"index": {"MED_EI": 0}}},
            "geo": {"category": {"index": {"UK": 0}}},
            "time": {"category": {"index": {"2017": 0, "2018": 1}}},
        },
        "value": {"0": 20_000, "1": 21_000},
        "status": {"0": "b", "1": "p"},
    }
    monkeypatch.setattr(eurostat, "get_json", lambda *args, **kwargs: payload)
    rows = eurostat.fetch(2017, 2018, geos=["UK"])
    assert [row["status"] for row in rows] == ["b", "p"]
    long_path, wide_path = tmp_path / "long.csv", tmp_path / "wide.csv"
    combine.write_long(rows, str(long_path))
    combine.write_wide(rows, str(wide_path))
    with long_path.open() as fh:
        long = list(csv.DictReader(fh))
    with wide_path.open() as fh:
        wide = list(csv.DictReader(fh))
    assert [row["status"] for row in long] == ["b", "p"]
    assert [row["median_disposable_income__status"] for row in wide] == ["b", "p"]
    assert [float(row["median_disposable_income"]) for row in wide] == [20_000, 21_000]


def test_income_chart_preserves_sparse_points_and_source_breaks(monkeypatch, tmp_path):
    import pandas as pd
    from europe_data import plot_uk_decline as plots

    metric = "median_disposable_income"
    data = pd.DataFrame([
        {"country": "Germany", "year": year, metric: value, f"{metric}__status": status}
        for year, value, status in [(1999, 100, "e"), (2001, 120, ""), (2002, 130, "bp")]
    ])
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda *args, **kwargs:
                        captured.append(plots.plt.gcf()))
    plots._line_chart(
        data, metric, "Income", "PPS", lambda value, _: str(value),
        plots.SOURCE_EUROSTAT, "income.png", tmp_path,
    )
    ax = captured[0].axes[0]
    line = ax.lines[0]
    xs, ys = line.get_xdata(), line.get_ydata()
    assert list(xs) == [1999, 2000, 2001, 2001.5, 2002]
    assert pd.isna(ys[1]) and pd.isna(ys[3])
    assert list(ys[pd.notna(ys)]) == [100, 120, 130]
    assert line.get_marker() == "o"
    assert ax.get_xlabel() == "Survey year"


def test_pip_chart_breaks_at_known_survey_and_welfare_changes(monkeypatch, tmp_path):
    import pandas as pd
    from europe_data import plot_uk_decline as plots

    metric = "median_income_pip"
    data = pd.DataFrame([
        {"country": "United Kingdom", "year": year, metric: value,
         f"{metric}__survey_comparability": group,
         f"{metric}__welfare_type": welfare}
        for year, value, group, welfare in [
            (2000, 100, 0, "income"), (2001, 110, 0, "income"),
            (2002, 120, 1, "income"), (2003, 130, None, "income"),
            (2004, 140, None, "consumption"), (2005, 150, "", ""),
            (2006, 160, 2, "consumption"),
        ]
    ])
    captured = []
    monkeypatch.setattr(plots, "save_chart", lambda *args, **kwargs:
                        captured.append(plots.plt.gcf()))
    plots._line_chart(
        data, metric, "Income", "PPP $/day", lambda value, _: str(value),
        plots.SOURCE_PIP, "pip.png", tmp_path,
    )
    line = captured[0].axes[0].lines[0]
    xs, ys = line.get_xdata(), line.get_ydata()
    assert list(xs[pd.isna(ys)]) == [2001.5, 2003.5]
    assert list(xs[pd.notna(ys)]) == list(range(2000, 2007))
    assert list(ys[pd.notna(ys)]) == [100, 110, 120, 130, 140, 150, 160]
    assert line.get_marker() == "o"


def test_combine_long_and_wide() -> None:
    rows = [
        {"iso3": "GBR", "country": "United Kingdom", "year": 2020,
         "metric": "gdp_per_capita_ppp_current", "value": 50000.0,
         "unit": "current international $", "source": "World Bank WDI"},
        {"iso3": "GBR", "country": "United Kingdom", "year": 2020,
         "metric": "median_income_pip", "value": 53.4,
         "unit": "2017 PPP $ per day", "source": "World Bank PIP"},
        {"iso3": "DEU", "country": "Germany", "year": 2020,
         "metric": "gdp_per_capita_ppp_current", "value": 56000.0,
         "unit": "current international $", "source": "World Bank WDI"},
    ]
    with tempfile.TemporaryDirectory() as d:
        long_path = Path(d) / "long.csv"
        wide_path = Path(d) / "wide.csv"
        combine.write_long(rows, str(long_path))
        combine.write_wide(rows, str(wide_path))

        long_rows = list(csv.DictReader(open(long_path)))
        assert len(long_rows) == 3
        assert set(long_rows[0]) == set(combine.LONG_FIELDS)

        wide_rows = {r["country"]: r for r in csv.DictReader(open(wide_path))}
        uk = wide_rows["United Kingdom"]
        assert uk["gdp_per_capita_ppp_current"] == "50000.0"
        assert uk["median_income_pip"] == "53.4"
        # Missing metric for the UK row is blank, not an error.
        assert uk["mean_disposable_income"] == ""
        assert wide_rows["Germany"]["median_income_pip"] == ""


def _run() -> int:
    import pytest

    return pytest.main([str(Path(__file__).resolve()), "-q"])


if __name__ == "__main__":
    raise SystemExit(_run())
