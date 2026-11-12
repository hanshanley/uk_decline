"""Regression tests for nonempty but incomplete live source responses."""

import csv
from importlib import import_module
from pathlib import Path

import pytest


@pytest.mark.parametrize("source,path,keys", [
    ("trade", "data/trade_share_gdp.csv", ("country_code", "year")),
    ("csew", "data/crime_csew_long.csv", ("region", "offence_group", "level", "date", "metric")),
    ("homicide", "data/crime_homicide_long.csv", ("iso3", "year", "metric")),
    ("nations", "data/crime_homicide_nations_long.csv", ("jurisdiction", "year", "metric")),
    ("markets", "data/stock_market_size.csv", ("region_code", "year", "metric")),
])
@pytest.mark.parametrize("defect", ["missing", "duplicate", "nonfinite", "revision"])
def test_source_writers_preserve_published_coverage(
    tmp_path, monkeypatch, source, path, keys, defect,
):
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    target = tmp_path / "source.csv"
    target.write_bytes(Path(path).read_bytes())
    original = target.read_bytes()
    if defect == "missing":
        rows.pop()
    elif defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "nonfinite":
        rows[0]["value"] = "nan"
    else:
        rows[0]["value"] = str(float(rows[0]["value"]) + 1)

    def write():
        if source == "trade":
            import_module("trade_data.__main__")._write(rows, target)
        elif source == "markets":
            from markets_data import combine
            monkeypatch.setattr(combine, "fetch_all", lambda *a: (rows, 2025))
            combine.build(
                path=target, wide_path=tmp_path / "wide.csv",
                manifest_path=tmp_path / "manifest.json",
            )
        else:
            import_module("crime_data.__main__")._write_csv(rows, target, fields)

    if defect == "revision":
        write()
        with target.open(newline="") as handle:
            revised = {
                tuple(row[key] for key in keys): float(row["value"])
                for row in csv.DictReader(handle)
            }
        assert revised[tuple(rows[0][key] for key in keys)] == float(rows[0]["value"])
    else:
        with pytest.raises((RuntimeError, ValueError), match="lose|duplicate|nonfinite"):
            write()
        assert target.read_bytes() == original
        assert not (tmp_path / "wide.csv").exists()
        assert not (tmp_path / "manifest.json").exists()


def test_explicit_market_window_retains_its_intentional_range(tmp_path, monkeypatch):
    from markets_data import combine
    with Path("data/stock_market_size.csv").open(newline="") as handle:
        previous = list(csv.DictReader(handle))
    rows = [row for row in previous if 2000 <= int(row["year"]) <= 2001]
    target = tmp_path / "source.csv"
    target.write_bytes(Path("data/stock_market_size.csv").read_bytes())
    monkeypatch.setattr(combine, "fetch_all", lambda *a: (rows, 2025))
    result = combine.build(
        2000, 2001, target, tmp_path / "wide.csv", tmp_path / "manifest.json",
    )
    assert set(result["year"].astype(int)) == {2000, 2001}
