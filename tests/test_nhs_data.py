"""Offline unit tests for the nhs_data pipeline (no network required).

Run directly:  python tests/test_nhs_data.py
Or with pytest: pytest tests/test_nhs_data.py -q
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import pytest

from nhs_data import charts, combine, metrics, nations, population, summary  # noqa: E402


def _synthetic_rows() -> list[dict]:
    rows: list[dict] = []
    dates = pd.date_range("2016-03-31", "2024-12-31", freq="6ME")
    seeds = {
        "rtt_waiting_list_total": 3_000_000.0,
        "rtt_waiting_list_per_1000": 55.0,
        "rtt_median_wait_weeks": 8.0,
        "ae_4hr_pct": 92.0,
        "cancer_62day_pct": 82.0,
        "diagnostics_6week_breach_pct": 4.0,
        "diagnostics_8week_breach_pct": 4.0,
    }
    for code in nations.codes():
        name = nations.name_for_code(code)
        for metric_id, base in seeds.items():
            v = base
            for d in dates:
                v *= 1.03 if metrics.METRICS[metric_id].higher_is_better is False else 0.99
                rows.append(
                    metrics.make_row(
                        name, code, d.strftime("%Y-%m"), d.strftime("%Y-%m-%d"),
                        metric_id, v, "synthetic",
                    )
                )
    return rows


def test_make_row_valid_and_invalid() -> None:
    r = metrics.make_row("England", "ENG", "2024-03", "2024-03-31",
                         "rtt_waiting_list_total", 7_600_000, "NHS England")
    assert tuple(r) == metrics.ROW_FIELDS
    assert r["unit"] == "pathways / waits"
    assert isinstance(r["value"], float)
    try:
        metrics.make_row("England", "ENG", "2024-03", "2024-03-31", "not_a_metric", 1, "x")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown metric id should raise KeyError")


def test_metrics_have_caveats() -> None:
    # Every metric must document a comparability caveat.
    for metric_id in metrics.METRICS:
        assert metric_id in metrics.CAVEATS and metrics.CAVEATS[metric_id]


def test_to_frame_column_order_and_sort() -> None:
    df = combine.to_frame(_synthetic_rows())
    assert list(df.columns) == list(metrics.ROW_FIELDS)
    # Sorted by metric, nation_code, date.
    assert df.equals(df.sort_values(["metric", "nation_code", "date"]).reset_index(drop=True))


def test_fetch_all_is_resilient(monkeypatch) -> None:
    good = _synthetic_rows()[:5]

    def ok(start=None, end=None):
        return good

    def boom(start=None, end=None):
        raise RuntimeError("source down")

    monkeypatch.setitem(combine.SOURCES, "ENG", ok)
    monkeypatch.setitem(combine.SOURCES, "SCO", boom)
    monkeypatch.setitem(combine.SOURCES, "WAL", ok)
    monkeypatch.setitem(combine.SOURCES, "NIR", boom)
    rows = combine.fetch_all()
    # Two good sources contribute; two failing ones are skipped, not fatal.
    assert len(rows) == len(good) * 2


def test_write_csv_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "nhs.csv"
        combine.write_csv(_synthetic_rows(), path)
        back = pd.read_csv(path)
        assert list(back.columns) == list(metrics.ROW_FIELDS)
        assert not back.empty


def test_charts_written_per_metric() -> None:
    df = combine.to_frame(_synthetic_rows())
    with tempfile.TemporaryDirectory() as d:
        written = charts.make_charts(df, out_dir=d)
        names = {p.name for p in written}
        for metric_id in metrics.METRICS:
            assert f"{metric_id}.png" in names


def test_indexed_charts_use_exact_shared_baseline_date() -> None:
    df = pd.DataFrame({
        "nation_code": ["ENG", "ENG", "SCO", "SCO"],
        "date": pd.to_datetime(["2020-01-31", "2020-03-31", "2020-02-29", "2020-03-31"]),
    })
    assert charts._shared_baseline_date(df) == pd.Timestamp("2020-03-31")


def test_summary_content() -> None:
    df = combine.to_frame(_synthetic_rows())
    with tempfile.TemporaryDirectory() as d:
        path = summary.build_summary(df, path=Path(d) / "s.md")
        text = path.read_text()
        assert "trend summary" in text
        # Each metric label and its caveat appear.
        for metric_id, meta in metrics.METRICS.items():
            assert meta.label in text
        assert "Caveat:" in text
        # A rising bad metric is flagged worse.
        assert "worse" in text
        # Proper organisational citations are rendered.
        assert "Data sources & citations" in text
        assert "NHS England" in text and "Public Health Scotland" in text
        assert "Office for National Statistics" in text


def test_add_per_capita_uses_real_population(monkeypatch) -> None:
    from nhs_data import population

    # Stub the ONS fetch so the test stays offline; values mimic real estimates.
    pops = {("ENG", 2020): 56_000_000.0, ("ENG", 2021): 56_500_000.0}
    monkeypatch.setattr(population, "fetch", lambda *a, **k: pops)

    rows = [
        metrics.make_row("England", "ENG", "2020-03", "2020-03-31",
                         "rtt_waiting_list_total", 4_200_000, "NHS England"),
        # 2019 has no stub population -> must NOT get a per-capita row (no fabrication)
        metrics.make_row("England", "ENG", "2019-03", "2019-03-31",
                         "rtt_waiting_list_total", 4_000_000, "NHS England"),
    ]
    out = combine.add_per_capita(rows)
    per_cap = [r for r in out if r["metric"] == "rtt_waiting_list_per_1000"]
    assert len(per_cap) == 1  # only the year with a real population
    r = per_cap[0]
    assert r["period"] == "2020-03"
    assert abs(r["value"] - 4_200_000 / 56_000_000 * 1000) < 1e-6
    assert "mid-year population" in r["source"]


def test_add_per_capita_resilient_to_population_failure(monkeypatch) -> None:
    from nhs_data import population

    def boom(*a, **k):
        raise RuntimeError("nomis down")

    monkeypatch.setattr(population, "fetch", boom)
    rows = [
        metrics.make_row("Wales", "WAL", "2020-03", "2020-03-31",
                         "rtt_waiting_list_total", 500_000, "StatsWales"),
    ]
    out = combine.add_per_capita(rows)
    assert out == rows  # raw rows preserved, no crash


def test_population_fetch_skips_blank_observations(monkeypatch) -> None:
    payload = {
        "obs": [
            {
                "geography": {"geogcode": "E92000001"},
                "time": {"value": 2024},
                "obs_value": {"value": 57_000_000},
            },
            {
                "geography": {"geogcode": "S92000003"},
                "time": {"value": 2024},
                "obs_value": {"value": ""},
            },
        ]
    }
    monkeypatch.setattr(population, "get_json", lambda *a, **k: payload)
    assert population.fetch() == {("ENG", 2024): 57_000_000.0}


def test_scottish_stage_medians_are_not_a_pooled_median(monkeypatch) -> None:
    from nhs_data import scotland

    records = [
        {"MonthEnding": "20240331", "PatientType": "New Outpatient",
         "NumberWaiting": 100, "Median": 7},
        {"MonthEnding": "20240331", "PatientType": "Inpatient/Day case",
         "NumberWaiting": 100, "Median": 700},
        {"MonthEnding": "20240331", "PatientType": "Other",
         "NumberWaiting": 900, "Median": 1},
        {"MonthEnding": "20240430", "PatientType": "New Outpatient",
         "NumberWaiting": 100, "Median": 7},
    ]
    monkeypatch.setattr(scotland, "_datastore_records", lambda *a, **k: iter(records))
    rows = scotland._fetch_rtt()
    assert [(r["metric"], r["value"]) for r in rows] == [
        ("rtt_waiting_list_total", 200)
    ]


def test_scottish_diagnostics_do_not_double_count_total_or_drop_open_band(monkeypatch) -> None:
    from nhs_data import scotland

    records = [
        {"MonthEnding": "20240331", "DiagnosticTestDescription": "All Imaging",
         "WaitingTime": band, "NumberOnList": count}
        for band, count in [
            ("Total Number Waiting", 100), ("0-7 days", 60),
            ("43-49 days", 20), ("92 days and over", 20)
        ]
    ]
    records += [
        {"MonthEnding": "20240430", "DiagnosticTestDescription": "All Imaging",
         "WaitingTime": band, "NumberOnList": count}
        for band, count in [
            ("0-7 days", 60), ("43-49 days", 20), ("92-182 days", 20)
        ]
    ]
    monkeypatch.setattr(scotland, "_datastore_records", lambda *a, **k: iter(records))
    assert scotland._fetch_diagnostics_current() == {
        scotland._month_end("20240331"): (100, 40),
        scotland._month_end("20240430"): (100, 40),
    }
    assert scotland._is_six_week_breach_band("365 days and over")
    assert not scotland._is_six_week_breach_band("36-42 days")


def test_welsh_diagnostic_thresholds_remain_separate(monkeypatch) -> None:
    from nhs_data import wales

    def records(dataset, filters):
        if dataset == wales.DATASETS["diagnostics_current"]:
            return iter([
                {"Date": "Aug-2024", "Weeks waiting": band, "Data values": value}
                for band, value in [
                    ("Total Waiting", 100), ("Over 6 weeks and up to 7 weeks", 20),
                    ("Over 8 Weeks", 10), ("Forty weeks and over", 10)
                ]
            ])
        return iter([
            {"Date": "Jul-2024", "Grouped weeks waiting": band, "Data values": value}
            for band, value in [("Total Waiting", 100), ("Over 8 Weeks", 10)]
        ])

    monkeypatch.setattr(wales, "_view_rows", records)
    rows = list(wales._fetch_diagnostics_6week_breach_pct())
    assert [(r["period"], r["metric"], r["value"]) for r in rows] == [
        ("2024-08", "diagnostics_6week_breach_pct", 30),
        ("2024-07", "diagnostics_8week_breach_pct", 10),
    ]


def test_english_ae_excludes_decision_to_admission_delays(monkeypatch) -> None:
    from nhs_data import england

    monkeypatch.setattr(england, "_discover_pages", lambda *a: [])
    monkeypatch.setattr(england, "_select_month_links", lambda *a: [(2024, 1, "x")])
    monkeypatch.setattr(england, "get_csv", lambda *a: pd.DataFrame({
        "Org Code": ["TOTAL"],
        "A&E attendances Type 1": [100],
        "A&E attendances over 4 hours Type 1": [20],
        "Emergency admissions over 4 hours from decision to admission": [10],
    }))
    assert england._fetch_ae(2024, 2024)[0]["value"] == 80


def test_diagnostic_schema_change_cannot_become_zero_breaches(monkeypatch) -> None:
    from nhs_data import england

    monkeypatch.setattr(england, "_csv_text_from_zip",
                        lambda *a: "Diagnostic Tests,Total WL\nTOTAL,100")
    with pytest.raises(ValueError, match="breach columns"):
        england._diagnostics_rows_from_zip("x", 2024, 1)


def test_indexed_plot_starts_at_shared_baseline(monkeypatch, tmp_path) -> None:
    rows = [
        metrics.make_row(name, code, date[:7], date, "rtt_waiting_list_total", value, "x")
        for name, code, date, value in [
            ("England", "ENG", "2020-01-31", 10),
            ("England", "ENG", "2020-03-31", 20),
            ("Scotland", "SCO", "2020-03-31", 30),
        ]
    ]
    captured = []
    original = charts.plt.subplots

    def capture(*args, **kwargs):
        fig, ax = original(*args, **kwargs)
        captured.append(ax)
        return fig, ax

    monkeypatch.setattr(charts.plt, "subplots", capture)
    charts.chart_metric(combine.to_frame(rows), "rtt_waiting_list_total",
                        tmp_path, indexed=True)
    for line in captured[0].lines[:2]:
        assert pd.Timestamp(min(line.get_xdata())) == pd.Timestamp("2020-03-31")
        assert list(line.get_ydata()) == [100]


def test_summary_does_not_infer_improvement_across_ni_encompass_break(tmp_path):
    rows = [
        metrics.make_row("Northern Ireland", "NIR", date[:7], date,
                         "rtt_waiting_list_total", value, "DoH")
        for date, value in [("2020-03-31", 100), ("2024-03-31", 200)]
    ]
    path = summary.build_summary(combine.to_frame(rows), tmp_path / "summary.md")
    text = path.read_text()
    assert "Not like-for-like (encompass break)" in text
    assert "(worse)" not in text


def _run() -> int:
    import inspect

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            if "monkeypatch" in inspect.signature(t).parameters:
                continue  # requires pytest fixture; skip in direct mode
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed - 1} passed (monkeypatch test needs pytest)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
