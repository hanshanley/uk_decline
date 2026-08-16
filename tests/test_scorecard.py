"""Regression tests for scorecard input validation and derived indicators."""

from __future__ import annotations

import csv

import scorecard


def test_fraud_share_uses_matching_headline_totals(tmp_path, monkeypatch):
    path = tmp_path / "crime_csew_long.csv"
    fields = ["offence_group", "year", "value"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for year, excl, incl in ((2017, 60, 100), (2018, 50, 100)):
            writer.writerow({
                "offence_group":
                    "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE",
                "year": year,
                "value": excl,
            })
            writer.writerow({
                "offence_group": "ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE",
                "year": year,
                "value": incl,
            })
    monkeypatch.setattr(scorecard, "DATA", tmp_path)
    assert scorecard.fraud_share() == ([2017, 2018], [40.0, 50.0])


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
