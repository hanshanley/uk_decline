"""Regression tests for scorecard input validation and annual completeness."""

from __future__ import annotations

import csv

import scorecard


def test_rail_delays_excludes_incomplete_year(tmp_path, monkeypatch):
    path = tmp_path / "rail_performance.csv"
    fields = ["region", "year", "quarter", "metric", "value"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for quarter, value in zip(("Q1", "Q2", "Q3", "Q4"), (2.0, 3.0, 4.0, 5.0)):
            writer.writerow({
                "region": "London and South East",
                "year": 2025,
                "quarter": quarter,
                "metric": "casl_pct",
                "value": value,
            })
        writer.writerow({
            "region": "London and South East",
            "year": 2026,
            "quarter": "Q1",
            "metric": "casl_pct",
            "value": 9.0,
        })
    monkeypatch.setattr(scorecard, "DATA", tmp_path)
    assert scorecard.rail_delays() == ([2025], [3.5])


def test_main_reports_all_missing_inputs(tmp_path, monkeypatch, capsys):
    missing_a = tmp_path / "a.csv"
    missing_b = tmp_path / "b.csv"
    monkeypatch.setattr(
        scorecard,
        "REQUIRED_INPUTS",
        {missing_a: "build-a", missing_b: "build-b"},
    )
    assert scorecard.main() == 2
    stderr = capsys.readouterr().err
    assert "a.csv" in stderr and "build-a" in stderr
    assert "b.csv" in stderr and "build-b" in stderr
