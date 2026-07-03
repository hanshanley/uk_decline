"""Offline tests for the spreadsheet reader and the combine/CSV writer."""

from __future__ import annotations

import csv
import io

from uk_migration import combine, schema
from uk_migration._spreadsheet import read_rows


def _make_xlsx(rows: list[tuple], sheet_name: str = "Data") -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_read_rows_xlsx_by_sheet():
    content = _make_xlsx([("Year", "Value"), (2020, 5), (2021, 7)], sheet_name="Data")
    out = list(read_rows(content, "file.xlsx", sheet="Data"))
    assert out[0] == ("Year", "Value")
    assert out[1] == (2020, 5)


def test_read_rows_csv():
    content = b"a,b\n1,2\n3,4\n"
    out = list(read_rows(content, "file.csv"))
    assert out == [("a", "b"), ("1", "2"), ("3", "4")]


def test_combine_writes_raw_and_long_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    rows_a = [schema.row(2020, "immigration", 100, unit="people", legality=schema.LEGAL, flow_type=schema.INFLOW, source="a")]
    rows_b = [schema.row(2020, "irregular_arrivals", 5, unit="detections", legality=schema.IRREGULAR, flow_type=schema.COUNT, source="b")]
    monkeypatch.setattr(combine, "SOURCES", {"a": lambda: rows_a, "b": lambda: rows_b})

    result = combine.run()
    assert len(result) == 2

    assert (tmp_path / "data/raw/a.csv").exists()
    assert (tmp_path / "data/raw/b.csv").exists()

    with (tmp_path / "data/processed/uk_migration_long.csv").open() as fh:
        reader = list(csv.DictReader(fh))
    assert len(reader) == 2
    metrics = {r["metric"] for r in reader}
    assert metrics == {"immigration", "irregular_arrivals"}
    assert list(reader[0].keys()) == list(schema.FIELDS)
