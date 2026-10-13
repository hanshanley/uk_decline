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
        assert list(ax.lines[0].get_xdata()) == [2007]
        assert list(ax.lines[0].get_ydata()) == [11_182_000]
        assert list(ax.lines[1].get_xdata()) == [2026]
        assert list(ax.lines[1].get_ydata()) == [4_333_000]
        assert ax.lines[0].get_color() == scorecard.BETTER
        text = " ".join(t.get_text() for t in ax.texts)
        assert "11.2M in 2007  to  4.3M in 2026" in text
        assert [t.get_text() for t in ax.get_xticklabels()] == ["2007", "2026"]
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


def test_nhs_annual_snapshot_uses_latest_date_not_input_order(monkeypatch):
    monkeypatch.setattr(scorecard, "_rows", lambda path: [
        {"nation_code": nation, "metric": "rtt_waiting_list_total", "date": date, "value": value}
        for nation, date, value in (
            ("ENG", "2025-12-31", "7000000"),
            ("ENG", "2025-01-31", "7500000"),
            ("WLS", "2025-12-31", "800000"),
        )
    ])
    assert scorecard.nhs_england() == ([2025], [7_000_000])


def test_nhs_scorecard_neither_bridges_scope_changes_nor_labels_them_worse(monkeypatch):
    monkeypatch.setattr(scorecard, "_rows", lambda path: [
        {"nation_code": "ENG", "metric": "rtt_waiting_list_total",
         "date": f"{year}-{month}", "value": value}
        for year, month, value in [
            (2007, "12-31", 2_000_000), (2012, "12-31", 3_000_000),
            (2013, "12-31", 3_100_000), (2023, "12-31", 7_500_000),
            (2024, "12-31", 7_400_000), (2026, "08-31", 7_158_164),
        ]
    ])
    fig, ax = scorecard.plt.subplots()
    try:
        panel = next(p for p in scorecard.PANELS if p[1] is scorecard.nhs_england)
        scorecard._panel(ax, *panel)
        for line in ax.lines:
            assert line.get_color() == scorecard.NEUTRAL
            xs = line.get_xdata()
            assert not any(min(xs) < year <= max(xs) for year in [2013, 2024])
            assert all(b - a == 1 for a, b in zip(xs, xs[1:]))
        assert list(ax.lines[-1].get_ydata()) == [7_158_164]
        text = " ".join(t.get_text() for t in ax.texts)
        assert "in 2026" in text
        assert "Aug" not in text
        assert "treatment entries, not unique patients" in text
        assert "endpoints not like-for-like" in text
    finally:
        scorecard.plt.close(fig)


def test_scorecard_crime_line_breaks_at_missing_annual_observations():
    fig, ax = scorecard.plt.subplots()
    try:
        scorecard._panel(
            ax, "Crime", lambda: ([2019, 2020, 2023, 2024], [6, 5.5, 4.4, 4.5]),
            str, -1, "ONS", 2007,
        )
        assert [list(line.get_xdata()) for line in ax.lines[:-1]] == [
            [2019, 2020], [2023, 2024],
        ]
    finally:
        scorecard.plt.close(fig)


def test_scorecard_trust_preserves_pooled_cadence_and_explains_period_end(monkeypatch):
    monkeypatch.setattr(scorecard, "_rows", lambda path: [
        {"iso3": "GBR", "metric": "trust_national_govt_pct", "year": year, "value": value}
        for year, value in [
            (2007, 42.5), (2010, 40), (2013, 42.3),
            (2019, 40), (2022, 35.7), (2024, 34.5),
        ]
    ])
    fig, ax = scorecard.plt.subplots()
    try:
        panel = next(p for p in scorecard.PANELS if p[1] is scorecard.trust_govt)
        scorecard._panel(ax, *panel)
        assert [list(line.get_xdata()) for line in ax.lines[:-1]] == [
            [2007, 2010, 2013], [2019, 2022, 2024],
        ]
        text = " ".join(t.get_text() for t in ax.texts)
        assert "pooled averages" in text
        assert "Years label the end of each survey period" in text
        assert [t.get_text() for t in ax.get_xticklabels()] == ["2007", "2024"]
    finally:
        scorecard.plt.close(fig)


def test_overview_panels_use_year_only_labels_without_changing_period_selection(monkeypatch):
    import pytest

    for loader in (scorecard.culture_spending, scorecard.tuition_real):
        panel = next(p for p in scorecard.PANELS if p[1] is loader)
        monkeypatch.setattr(scorecard, "_rows", lambda path: [
            {"year": "2007", "metric": "functional_spending_real", "category": "recreation_culture",
             "value": "19.1", "country": "United Kingdom", "real_2022_usd": "8000"},
            {"year": "2025", "metric": "functional_spending_real", "category": "recreation_culture",
             "value": "15.1", "country": "United Kingdom", "real_2022_usd": "11000"},
        ])
        fig, ax = scorecard.plt.subplots()
        try:
            scorecard._panel(ax, *panel)
            assert [t.get_text() for t in ax.get_xticklabels()] == ["2007", "2025"]
            expected = [19.1, 15.1] if loader is scorecard.culture_spending else [8000, 11000]
            assert [line.get_ydata()[0] for line in ax.lines[:-1]] == pytest.approx(expected)
            text = " ".join(t.get_text() for t in ax.texts)
            assert "in 2007" in text and "in 2025" in text
            assert "years" in text
        finally:
            scorecard.plt.close(fig)


def test_gdp_comparison_uses_constant_ppp_and_shared_years(monkeypatch):
    monkeypatch.setattr(scorecard, "_rows", lambda path: [
        {"country": country, "year": year, "gdp_per_capita_ppp_constant": ppp,
         "gdp_per_capita_real_usd": market}
        for country, year, ppp, market in (
            ("United Kingdom", 2025, "60", "100"),
            ("United States", 2024, "80", "100"),
            ("United Kingdom", 2024, "60", "50"),
            ("United States", 2007, "60", "50"),
            ("United Kingdom", 2007, "48", "100"),
        )
    ])
    assert scorecard.gdp_vs_us() == ([2007, 2024], [80.0, 75.0])


def test_listed_company_count_does_not_splice_in_a_different_definition(tmp_path, monkeypatch):
    (tmp_path / "uk_listed_companies_lse.csv").touch()
    monkeypatch.setattr(scorecard, "DATA", tmp_path)
    monkeypatch.setattr(scorecard, "_rows", lambda path: (
        [{"region": "United Kingdom", "year": year, "listed_domestic_companies": value}
         for year, value in ((2007, "2588"), (2022, "1606"))]
        if path.name == "stock_market_size_wide.csv"
        else [
            {"region": "United Kingdom", "year": year, "date": date, "metric": metric, "value": value}
            for year, date, metric, value in (
                ("2026", "2026-07-31", "lse_companies_uk", "1268"),
                ("2018", "2018-12-31", "lse_companies_uk", "1719"),
                ("2025", "2025-12-31", "lse_companies_total", "1545"),
                ("2026", "2026-01-31", "lse_companies_uk", "1290"),
            )
        ]
    ))
    assert scorecard.uk_listed_companies() == ([2018, 2026], [1719.0, 1268.0])


def test_main_rejects_empty_panel_instead_of_saving_incomplete_scorecard(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scorecard, "REQUIRED_INPUTS", {})
    monkeypatch.setattr(scorecard, "OUT", tmp_path)
    monkeypatch.setattr(scorecard, "PANELS", [
        ("Missing metric", lambda: ([], []), str, 0, "Source", 2007),
    ])
    assert scorecard.main() == 2
    assert "Missing metric: no observations from 2007 onward" in capsys.readouterr().err
    assert not (tmp_path / "uk_decline_scorecard.png").exists()
