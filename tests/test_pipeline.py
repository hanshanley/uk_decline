"""Offline unit tests for the europe_data pipeline (no network required).

Run directly:  python tests/test_pipeline.py
Or with pytest: pytest tests/ -q
"""

from __future__ import annotations

import csv
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
    # The deflation helper produces a real, constant-2015-US$ series from nominal + US CPI.
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
    ]:
        for i, year in enumerate([2007, 2025]):
            row = {metric: None for metric in combine.METRIC_ORDER}
            row.update(country=country, year=year,
                       gdp_per_capita_constant_usd=volumes[i],
                       gdp_per_capita_nominal_usd=nominal[i],
                       gdp_per_capita_real_usd=999_000 + i)
            rows.append(row)
    data = pd.DataFrame(rows)
    monkeypatch.setattr(plots.pd, "read_csv", lambda _: data)
    captured = {}
    def save(path, **kwargs):
        captured[Path(path).name] = plots.plt.gcf()
    monkeypatch.setattr(plots.plt, "savefig", save)
    assert plots.main(["--out", str(tmp_path)]) == 0
    real = captured["gdp_per_capita_real_over_time.png"].axes[0]
    nominal = captured["gdp_per_capita_nominal_over_time.png"].axes[0]
    assert list(real.lines[0].get_ydata()[pd.notna(real.lines[0].get_ydata())]) == pytest.approx([40, 44])
    assert list(nominal.lines[0].get_ydata()[pd.notna(nominal.lines[0].get_ydata())]) == pytest.approx([50, 100])
    ratio = captured["uk_gdp_relative_to_peers.png"].axes[0]
    assert list(ratio.lines[0].get_ydata()[pd.notna(ratio.lines[0].get_ydata())]) == pytest.approx([120, 120])
    for line in [real.lines[0], nominal.lines[0], ratio.lines[0]]:
        assert list(line.get_xdata()) == list(range(2007, 2026))
        assert pd.isna(line.get_ydata()[1:-1]).all()
    assert "2007\u20132025" in ratio.get_title()
    assert "2025" in " ".join(t.get_text() for t in ratio.texts)


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
    monkeypatch.setattr(plots.plt, "savefig", lambda *args, **kwargs:
                        captured.append(plots.plt.gcf()))
    plots.fig_uk_relative(data, tmp_path)
    ax = captured[0].axes[0]
    assert list(ax.lines[0].get_xdata()) == [2025]
    assert list(ax.lines[1].get_xdata()) == [2023]
    assert ax.lines[1].get_marker() == "o"
    text = " ".join(t.get_text() for t in ax.texts)
    assert "United States (2025)" in text and "Poland (2023)" in text
    assert "2023\u20132025" in ax.get_title()


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
    monkeypatch.setattr(plots.plt, "savefig", lambda *args, **kwargs:
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
