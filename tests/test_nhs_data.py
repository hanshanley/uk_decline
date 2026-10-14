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


@pytest.mark.parametrize("kind,slug", [
    ("cancer", "cancer"), ("outpatient", "outpatient"),
    ("diagnostics", "diagnostic"), ("emergency", "emergency-care"),
])
def test_ni_discovers_current_publication_before_pinned(monkeypatch, kind, slug) -> None:
    from nhs_data import northern_ireland as ni

    current = (
        "https://www.health-ni.gov.uk/publications/"
        f"northern-ireland-waiting-time-statistics-{slug}-waiting-times-june-2026"
    )
    monkeypatch.setattr(ni, "_html", lambda url:
        f'<a href="{current}">Current publication</a>'
        f'<a href="{current.replace("june", "march")}">Previous publication</a>'
    )
    assert ni._current_publication(kind, "older-pinned-page") == current


def test_ni_discovery_failure_warns_before_pinned_fallback(monkeypatch, capsys) -> None:
    from nhs_data import northern_ireland as ni

    monkeypatch.setattr(ni, "_html", lambda url: "")
    assert ni._current_publication("cancer", "pinned-page") == "pinned-page"
    assert "using pinned release" in capsys.readouterr().err


@pytest.mark.parametrize("sheet", ["Table 4", "62 Day Wait by HSC Trust"])
def test_ni_cancer_uses_trust_counts_and_omits_incomplete_months(
    monkeypatch, capsys, sheet,
) -> None:
    from nhs_data import northern_ireland as ni

    records = [
        {"Treatment Month": month, "HSC Trust": trust,
         "Patients Treated Within 62 Days": within,
         "Total Patients Treated": total}
        for month in ["May 2026", "June 2026"]
        for trust, within, total in [
            ("Belfast", 10, 100), ("Northern", 20, 50),
            ("South Eastern", 5, 10), ("Southern", 5, 10), ("Western", 10, 30),
        ]
    ]
    records[0]["Patients Treated Within 62 Days"] = None
    frame = pd.DataFrame(records)
    monkeypatch.setattr(ni, "_current_publication", lambda *args: "current-page")
    monkeypatch.setattr(ni, "_find_attachment_on_pages", lambda *args, **kwargs:
        ("current-workbook", "current-page"))
    monkeypatch.setattr(ni, "_workbook", lambda url: {
        sheet: frame,
        "Table 5": frame.rename(columns={"HSC Trust": "Tumour Site"}),
    })
    rows = ni._fetch_cancer_62day()
    assert [(r["period"], r["value"]) for r in rows] == [("2026-06", 25.0)]
    assert "omitting 1 months" in capsys.readouterr().err
    assert "date" not in frame.columns

    duplicate = pd.concat([frame, frame.iloc[-1:]], ignore_index=True)
    monkeypatch.setattr(ni, "_workbook", lambda url: {sheet: duplicate})
    with pytest.raises(ValueError, match="duplicate"):
        ni._fetch_cancer_62day()

    for within, total in [(31, 30), (-1, 30), (float("inf"), float("inf"))]:
        invalid = frame.astype({
            "Patients Treated Within 62 Days": float, "Total Patients Treated": float,
        })
        invalid.loc[invalid.index[-1], [
            "Patients Treated Within 62 Days", "Total Patients Treated",
        ]] = [within, total]
        monkeypatch.setattr(ni, "_workbook", lambda url: {sheet: invalid})
        with pytest.raises(ValueError, match="numerator/denominator"):
            ni._fetch_cancer_62day()


def test_ni_cancer_summary_does_not_compare_across_encompass(tmp_path) -> None:
    rows = [
        metrics.make_row("Northern Ireland", "NIR", date[:7], date,
                         "cancer_62day_pct", value, "fixture")
        for date, value in [("2023-10-31", 60), ("2026-06-30", 30)]
    ]
    path = summary.build_summary(combine.to_frame(rows), path=tmp_path / "summary.md")
    text = path.read_text()
    assert "encompass" in text
    assert "worse" not in text


def test_ni_emergency_reads_complete_count_table_not_rounded_rates(monkeypatch, capsys):
    import json
    from nhs_data import northern_ireland as ni

    records = [
        {"Date": month, "Trust": trust, "Dept": trust + " hospital", "Type": "Type 1",
         "Under4hrs": within, "Between4to12hrs": total - within, "Over12hrs": 0,
         "TotalAttendances": total + 10, "PercentUnder4hrs": within / total * 100}
        for month in ["2026-05-01", "2026-06-01"]
        for trust, within, total in [
            ("Belfast", 10, 100), ("Northern", 20, 50),
            ("South Eastern", 5, 10), ("Southern", 5, 10), ("Western", 10, 30),
        ]
    ]
    records[0]["Under4hrs"] = None
    # Another Belfast department must not conceal the missing hospital's counts.
    records.append({
        **records[0], "Dept": "Belfast minor injuries", "Type": "Type 3",
        "Under4hrs": 1, "Between4to12hrs": 0, "Over12hrs": 0,
        "TotalAttendances": 1, "PercentUnder4hrs": 100,
    })

    def document(rows):
        names = list(rows[0])
        payload = {"x": {
            "options": {"columnDefs": [
                {"name": name, "targets": i} for i, name in enumerate(names)
            ]},
            "data": [[row[name] for row in rows] for name in names],
        }}
        return ('<script type="application/json">' + json.dumps(payload) + '</script>').encode()

    monkeypatch.setattr(ni, "_current_publication", lambda *args: "current-page")
    monkeypatch.setattr(ni, "_html", lambda url:
        '<a href="https://datavis.nisra.gov.uk/health/'
        'ni-emergency-care-waiting-times-data-apr-jun-26.html">Interactive data</a>')
    monkeypatch.setattr(ni._http, "get_bytes", lambda url: document(records))
    rows = ni._fetch_emergency_4hr()
    assert [(row["period"], row["value"]) for row in rows] == [("2026-06", 25)]
    assert "omitting 1 months" in capsys.readouterr().err

    for field, value, message in [
        ("TotalAttendances", 1, "bands exceed"),
        ("PercentUnder4hrs", 1, "disagree"),
        ("Under4hrs", -1, "invalid"),
        ("TotalAttendances", 30.5, "invalid"),
        ("Trust", "Unknown", "unrecognised"),
        ("Dept", "", "identifier"),
    ]:
        invalid = [row.copy() for row in records]
        invalid[-2][field] = value
        monkeypatch.setattr(ni._http, "get_bytes", lambda url: document(invalid))
        with pytest.raises(ValueError, match=message):
            ni._fetch_emergency_4hr()

    duplicate = records + [records[-2]]
    monkeypatch.setattr(ni._http, "get_bytes", lambda url: document(duplicate))
    with pytest.raises(ValueError, match="duplicate"):
        ni._fetch_emergency_4hr()
    with pytest.raises(ValueError, match="expected one"):
        ni._emergency_frame("<html>No underlying count table</html>")


def test_summary_distinguishes_percentage_point_changes_from_relative_percent(tmp_path):
    rows = [
        metrics.make_row("England", "ENG", date[:7], date,
                         "ae_4hr_pct", value, "NHS England")
        for date, value in [("2026-08-31", 80), ("2026-09-30", 70)]
    ]
    text = summary.build_summary(combine.to_frame(rows), tmp_path / "summary.md").read_text()
    assert "80.0%" in text and "70.0%" in text
    assert "10.0 pp (worse)" in text
    assert "10.0% (worse)" not in text


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
        assert "(accessed " not in text


def test_source_citations_only_use_explicit_access_dates() -> None:
    from datetime import date
    from nhs_data import sources

    text = sources.render_markdown(accessed=date(2020, 2, 29))
    assert text.count("(accessed 2020-02-29)") == len(sources.CITATIONS)


def test_empty_fetch_preserves_saved_nhs_data(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(combine, "fetch_all", lambda *args: [])
    path = tmp_path / "nhs.csv"
    path.write_text("preserved source data\n")
    with pytest.raises(RuntimeError, match="NHS sources returned no observations"):
        combine.build(path=path)
    assert path.read_text() == "preserved source data\n"


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


def test_scottish_rtt_prefers_complete_monthly_revisions_and_excludes_completed_waits(
    monkeypatch
):
    from nhs_data import scotland

    old = [
        {"MonthEnding": day, "PatientType": stage, "NumberWaiting": count}
        for day in ["20260331", "20260430"]
        for stage, count in [("New Outpatient", 100), ("Inpatient/Day case", 200)]
    ]
    monthly = [
        {"MonthEnding": day, "PatientType": stage, "WaitType": wait_type, "Waits": count}
        for day, stage, wait_type, count in [
            ("20260331", "New Outpatient", "Ongoing", 110),
            ("20260331", "Inpatient/Day case", "Ongoing", 210),
            ("20260331", "New Outpatient", "Completed", 1000),
            ("20260430", "New Outpatient", "Ongoing", 120),
            ("20260430", "Inpatient/Day case", "Ongoing", None),
            ("20260531", "New Outpatient", "Ongoing", 130),
            ("20260531", "Inpatient/Day case", "Ongoing", 230),
        ]
    ]

    def records(resource_id, **kwargs):
        if resource_id == scotland.RTT_MONTHLY_RESOURCE:
            assert kwargs["filters"]["WaitType"] == "Ongoing"
            assert "WaitType" in kwargs["required_fields"]
            return iter(monthly)
        return iter(old)

    monkeypatch.setattr(scotland, "_datastore_records", records)
    rows = scotland._fetch_rtt()
    assert [(r["date"], r["value"]) for r in rows] == [
        ("2026-03-31", 320), ("2026-05-31", 360),
    ]


def test_scottish_rtt_rejects_duplicate_stage_counts(monkeypatch):
    from nhs_data import scotland

    record = {"MonthEnding": "20260831", "PatientType": "New Outpatient",
              "WaitType": "Ongoing", "Waits": 100}
    monkeypatch.setattr(scotland, "_datastore_records", lambda *a, **k: iter([record, record]))
    with pytest.raises(ValueError, match="duplicate Scottish ongoing wait count"):
        scotland._rtt_totals(scotland.RTT_MONTHLY_RESOURCE, "Waits", monthly=True)


def test_england_rtt_excludes_non_english_commissioned_paths_from_count_and_median(monkeypatch):
    from nhs_data import england

    text = (
        "RTT Part Type,Treatment Function Name,Commissioner Org Code,Total All,"
        "Gt 00 To 01 Weeks SUM 1,Gt 10 To 11 Weeks SUM 1\n"
        "Part_2,Total,01A,100,100,0\n"
        "Part_2,Total, nonc ,900,0,900\n"
        "Part_2,Cardiology,01A,100,100,0\n"
        "Part_1A,Total,01A,500,0,500\n"
    )
    monkeypatch.setattr(england, "_csv_text_from_zip", lambda url: text)
    rows = england._rtt_rows_from_zip("fixture", 2026, 8)
    assert {row["metric"]: row["value"] for row in rows} == {
        "rtt_waiting_list_total": 100,
        "rtt_median_wait_weeks": 0.5,
    }


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


@pytest.mark.parametrize(
    "metric_id,nation_codes,expected",
    [
        ("diagnostics_8week_breach_pct", ["WAL"], "Sources: StatsWales."),
        (
            "rtt_median_wait_weeks", ["ENG", "WAL", "NIR"],
            "Sources: NHS England, StatsWales, DoH Northern Ireland.",
        ),
    ],
)
def test_chart_sources_include_only_plotted_nations(
    monkeypatch, tmp_path, metric_id, nation_codes, expected
):
    rows = [
        metrics.make_row(nations.name_for_code(code), code, "2024-03", "2024-03-31",
                         metric_id, 10, "x")
        for code in nation_codes
    ]
    notes = []
    monkeypatch.setattr(
        charts.plt.Figure, "savefig",
        lambda fig, *args, **kwargs: notes.extend(t.get_text() for t in fig.texts),
    )
    charts.chart_metric(combine.to_frame(rows), metric_id, tmp_path)
    assert notes[0].split("\n", 1)[0] == expected


@pytest.mark.parametrize("nation,code,metric_id,dates,label", [
    ("Northern Ireland", "NIR", "rtt_waiting_list_total",
     ["2020-03-31", "2024-03-31"], "encompass"),
    ("Northern Ireland", "NIR", "ae_4hr_pct",
     ["2023-10-31", "2023-11-30"], "encompass"),
    ("England", "ENG", "rtt_waiting_list_total",
     ["2024-01-31", "2024-02-29"], "community-service scope"),
    ("England", "ENG", "rtt_waiting_list_total",
     ["2013-03-31", "2013-04-30"], "sexual-health scope"),
])
def test_summary_does_not_infer_improvement_across_scope_or_recording_break(
    tmp_path, nation, code, metric_id, dates, label
):
    rows = [
        metrics.make_row(nation, code, date[:7], date, metric_id, value, "Official source")
        for date, value in zip(dates, [80, 40])
    ]
    path = summary.build_summary(combine.to_frame(rows), tmp_path / "summary.md")
    text = path.read_text()
    assert f"Not like-for-like ({label} break)" in text
    assert "(worse)" not in text
    assert "(better)" not in text


@pytest.mark.parametrize(
    "code,metric_id,dates",
    [
        ("NIR", "rtt_waiting_list_total",
         ["2023-09-30", "2023-12-31", "2024-03-31", "2024-06-30",
          "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30"]),
        ("NIR", "cancer_62day_pct",
         ["2023-10-31", "2023-11-30", "2024-05-31", "2024-07-31",
          "2024-10-31", "2024-11-30", "2025-04-30", "2025-05-31"]),
        ("NIR", "ae_4hr_pct",
         ["2023-10-31", "2023-11-30", "2024-05-31", "2024-07-31",
          "2024-10-31", "2024-11-30", "2025-04-30", "2025-05-31"]),
        ("ENG", "cancer_62day_pct",
         ["2023-08-31", "2023-09-30", "2023-10-31", "2023-11-30"]),
        ("ENG", "rtt_waiting_list_total",
         ["2013-03-31", "2013-04-30", "2024-01-31", "2024-02-29"]),
        ("WAL", "cancer_62day_pct",
         ["2019-04-30", "2019-05-31", "2019-06-30", "2019-07-31"]),
    ],
)
def test_nhs_lines_do_not_bridge_definition_changes(monkeypatch, tmp_path, code, metric_id, dates):
    rows = [
        metrics.make_row(nations.name_for_code(code), code, date[:7], date,
                         metric_id, 80, "x")
        for date in dates
    ]
    figures = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: figures.append(fig))
    charts.chart_metric(combine.to_frame(rows), metric_id, tmp_path)
    ax = figures[0].axes[0]
    assert len(ax.lines) > 1
    for date, _ in metrics.series_breaks(metric_id, code):
        boundary = pd.Timestamp(date)
        for line in ax.lines:
            xs = pd.to_datetime(line.get_xdata())
            assert not (xs.min() < boundary <= xs.max())
    assert len(ax.get_legend_handles_labels()[0]) == 1
    fig = figures[0]
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    assert fig.texts[0].get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0


def test_indexed_nhs_growth_uses_baseline_after_last_observed_rollout(monkeypatch, tmp_path):
    rows = [
        metrics.make_row(nations.name_for_code(code), code, date[:7], date,
                         "rtt_waiting_list_total", value * scale, "x")
        for code, scale in [("ENG", 2), ("NIR", 1)]
        for date, value in [("2023-03-31", 10), ("2025-03-31", 20),
                            ("2025-06-30", 50), ("2026-03-31", 55)]
    ]
    figures = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: figures.append(fig))
    charts.chart_metric(combine.to_frame(rows), "rtt_waiting_list_total", tmp_path, indexed=True)
    ax = figures[0].axes[0]
    labelled = [line for line in ax.lines
                if line.get_label().startswith(("England", "Northern Ireland"))]
    assert len(labelled) == 2
    for line in labelled:
        assert pd.Timestamp(line.get_xdata()[0]) == pd.Timestamp("2025-06-30")
        assert line.get_ydata()[0] == pytest.approx(100)
        assert "\u00d71.10" in line.get_label()
    for code in ["ENG", "NIR"]:
        values = [v for line in ax.lines if line.get_color() == charts.NATION_COLOURS[code]
                  for v in line.get_ydata()]
        assert values == pytest.approx([100, 110])
    assert "Jun 2025" in ax.get_title()


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("code,metric_id,periods,dates", [
    ("SCO", "rtt_waiting_list_total",
     ["2017-02", "2017-03", "2019-01", "2019-02"],
     ["2017-02-28", "2017-03-31", "2019-01-31", "2019-02-28"]),
    ("SCO", "cancer_62day_pct",
     ["2024-Q1", "2024-Q2", "2024-Q4", "2025-Q1"],
     ["2024-03-31", "2024-06-30", "2024-12-31", "2025-03-31"]),
])
def test_nhs_chart_breaks_at_missing_periods_without_breaking_quarterly_cadence(
    monkeypatch, tmp_path, indexed, code, metric_id, periods, dates
):
    rows = [
        metrics.make_row(nations.name_for_code(code), code, period, date,
                         metric_id, value, "PHS")
        for period, date, value in zip(periods, dates, [50, 60, 70, 80])
    ]
    figures = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: figures.append(fig))
    charts.chart_metric(combine.to_frame(rows), metric_id, tmp_path, indexed=indexed)
    ax = figures[0].axes[0]
    lines = [line for line in ax.lines if line.get_color() == charts.NATION_COLOURS[code]]
    assert [list(pd.to_datetime(line.get_xdata())) for line in lines] == [
        list(pd.to_datetime(dates[:2])), list(pd.to_datetime(dates[2:])),
    ]
    assert [list(line.get_ydata()) for line in lines] == (
        [[100, 120], [140, 160]] if indexed else [[50, 60], [70, 80]]
    )
    assert len(ax.get_legend_handles_labels()[0]) == 1


def test_summary_does_not_compare_across_england_cancer_standards(tmp_path):
    rows = [
        metrics.make_row("England", "ENG", date[:7], date, "cancer_62day_pct", value, "x")
        for date, value in [("2022-04-30", 70), ("2026-04-30", 60)]
    ]
    text = summary.build_summary(combine.to_frame(rows), tmp_path / "summary.md").read_text()
    assert "Not like-for-like (cancer standards break)" in text
    assert "(worse)" not in text


def test_cancer_discovery_prefers_current_publication_to_pinned_snapshot(monkeypatch):
    from nhs_data import england

    current = "https://www.england.nhs.uk/CWT-National-Time-Series-current.xlsx"
    monkeypatch.setattr(england, "_links", lambda page: [("Current national time series", current)])
    assert england._cancer_workbooks()[0] == current


def test_empty_nhs_landing_page_is_not_successful_discovery(monkeypatch, capsys):
    from nhs_data import england

    monkeypatch.setattr(england, "get_bytes", lambda url: b"")
    monkeypatch.setattr(england, "get_json", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="no unique NHS publication API match"):
        england._links(england.LANDING_URLS["rtt"])
    assert england._cancer_workbooks() == england.CANDIDATE_URLS["cancer_timeseries"]
    assert "using pinned workbook" in capsys.readouterr().err


@pytest.mark.parametrize("body", [
    b"", b"<html><h1>JavaScript is disabled</h1></html>",
])
def test_england_discovers_downloads_via_official_api(monkeypatch, body):
    from nhs_data import england

    page = england.LANDING_URLS["rtt"]
    monkeypatch.setattr(england, "get_bytes", lambda url: body)
    calls = []

    def api(url, params):
        calls.append((url, params))
        return [{"link": page, "content": {"rendered":
            '<a href="rtt-data-2026-27/">2026–27 data</a>'}}]

    monkeypatch.setattr(england, "get_json", api)
    assert england._links(page) == [("2026–27 data", page + "rtt-data-2026-27/")]
    assert calls == [(
        "https://www.england.nhs.uk/statistics/wp-json/wp/v2/pages",
        {"slug": "rtt-waiting-times", "_fields": "link,content.rendered"},
    )]

    monkeypatch.setattr(england, "get_json", lambda *args, **kwargs: [
        {"link": page + "rtt-data-2025-26/", "content": {"rendered":
            '<a href="old.zip">Outdated data</a>'}},
    ])
    with pytest.raises(ValueError, match="no unique"):
        england._links(page)


def test_england_normal_html_discovery_does_not_call_api(monkeypatch):
    from nhs_data import england

    monkeypatch.setattr(england, "get_bytes", lambda url:
        b'<a href="current.csv">Monthly data</a>')

    def unexpected(*args, **kwargs):
        raise AssertionError("API should not be called for a usable HTML page")

    monkeypatch.setattr(england, "get_json", unexpected)
    page = england.LANDING_URLS["ae"]
    assert england._links(page) == [("Monthly data", page + "current.csv")]


@pytest.mark.parametrize("legacy_parent", ["statistics", "statistics/rtt-waiting-times"])
def test_england_discovery_normalises_old_publication_aliases(monkeypatch, legacy_parent):
    from nhs_data import england

    parent = england.LANDING_URLS["rtt"]
    canonical = parent + "rtt-data-2014-15/"
    monkeypatch.setattr(england, "_links", lambda url: [
        ("2014-15", f"https://www.england.nhs.uk/{legacy_parent}/rtt-data-2014-15/"),
        ("2014-15", canonical),
    ])
    assert england._discover_pages(parent, "rtt-data-", [], 2015, 2015) == [canonical]


def test_summary_does_not_compare_welsh_cancer_pathway_definitions(tmp_path):
    rows = [
        metrics.make_row("Wales", "WAL", date[:7], date, "cancer_62day_pct", value, "x")
        for date, value in [("2009-10-31", 90), ("2026-05-31", 60)]
    ]
    text = summary.build_summary(combine.to_frame(rows), tmp_path / "summary.md").read_text()
    assert "Not like-for-like (suspected cancer pathway break)" in text
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
