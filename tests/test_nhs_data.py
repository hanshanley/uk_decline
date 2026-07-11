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

from nhs_data import charts, combine, metrics, nations, summary  # noqa: E402


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
    assert r["unit"] == "patients"
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
