"""Regression tests for nonempty but incomplete live source responses."""

import csv
from importlib import import_module

import pytest


def example_rows(source):
    if source == "trade":
        from trade_data.worldbank import ROW_FIELDS
        fields = ROW_FIELDS
    elif source == "markets":
        from markets_data.markets import ROW_FIELDS
        fields = ROW_FIELDS
    else:
        module = import_module("crime_data.__main__")
        fields = getattr(module, f"_{source.upper()}_FIELDS")
    rows = []
    for year in (1999, 2000, 2001):
        row = dict.fromkeys(fields, "fixture")
        row.update(year=year, value=100.0)
        if "date" in row:
            row["date"] = f"{year}-12-31"
        if "metric" in row:
            row["metric"] = "market_cap_usd" if source == "markets" else "count"
        rows.append(row)
    return fields, rows


def save_rows(path, fields, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("source,keys", [
    ("trade", ("country_code", "year")),
    ("csew", ("region", "offence_group", "level", "date", "metric")),
    ("homicide", ("iso3", "year", "metric")),
    ("nations", ("jurisdiction", "year", "metric")),
    ("markets", ("region_code", "year", "metric")),
])
@pytest.mark.parametrize("defect", ["missing", "duplicate", "nonfinite", "revision"])
def test_source_writers_preserve_published_coverage(
    tmp_path, monkeypatch, source, keys, defect,
):
    fields, rows = example_rows(source)
    target = tmp_path / "source.csv"
    save_rows(target, fields, rows)
    original = target.read_bytes()
    if defect == "missing":
        rows.pop()
    elif defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "nonfinite":
        rows[0]["value"] = "nan"
    else:
        rows[0]["value"] += 1

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
        assert revised[tuple(str(rows[0][key]) for key in keys)] == float(rows[0]["value"])
    else:
        with pytest.raises((RuntimeError, ValueError), match="lose|duplicate|nonfinite"):
            write()
        assert target.read_bytes() == original
        assert not (tmp_path / "wide.csv").exists()
        assert not (tmp_path / "manifest.json").exists()


def test_explicit_market_window_retains_its_intentional_range(tmp_path, monkeypatch):
    from markets_data import combine
    fields, previous = example_rows("markets")
    rows = [row for row in previous if 2000 <= int(row["year"]) <= 2001]
    target = tmp_path / "source.csv"
    save_rows(target, fields, previous)
    monkeypatch.setattr(combine, "fetch_all", lambda *a: (rows, 2025))
    result = combine.build(
        2000, 2001, target, tmp_path / "wide.csv", tmp_path / "manifest.json",
    )
    assert set(result["year"].astype(int)) == {2000, 2001}
