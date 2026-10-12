"""Regression tests for scorecard input validation and derived indicators."""

from __future__ import annotations

import csv

import scorecard


def test_crime_incidents_uses_excluding_series_and_converts_thousands(tmp_path, monkeypatch):
    path = tmp_path / "crime_csew_long.csv"
    fields = ["offence_group", "year", "date", "value"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for year, excl, incl in ((2026, 4333, 9615), (2007, 11182, "")):
            writer.writerow({
                "offence_group":
                    "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE",
                "year": year,
                "date": f"{year}-03-31",
                "value": excl,
            })
            writer.writerow({
                "offence_group": "ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE",
                "year": year,
                "date": f"{year}-03-31",
                "value": incl,
            })
        writer.writerow({
            "offence_group":
                "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE",
            "year": 2026,
            "date": "2026-01-31",
            "value": 5000,
        })
        writer.writerow({
            "offence_group":
                "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE",
            "year": 2025,
            "date": "2025-03-31",
            "value": "",
        })
    monkeypatch.setattr(scorecard, "DATA", tmp_path)
    assert scorecard.crime_incidents() == ([2007, 2026], [11_182_000, 4_333_000])


def test_crime_panel_shows_counts_and_marks_falling_crime_as_improvement(monkeypatch):
    monkeypatch.setattr(scorecard, "_rows", lambda path: [
        {
            "offence_group":
                "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE",
            "year": year,
            "date": f"{year}-03-31",
            "value": value,
        }
        for year, value in ((2006, 10863), (2007, 11182), (2026, 4333))
    ])
    fig, ax = scorecard.plt.subplots()
    try:
        scorecard._panel(ax, *scorecard.PANELS[-1])
        assert list(ax.lines[0].get_xdata()) == [2007, 2026]
        assert list(ax.lines[0].get_ydata()) == [11_182_000, 4_333_000]
        assert ax.lines[0].get_color() == scorecard.BETTER
        text = " ".join(t.get_text() for t in ax.texts)
        assert "11.2M in 2007  to  4.3M in 2026" in text
        assert "excludes fraud & computer misuse" in text
    finally:
        scorecard.plt.close(fig)


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
