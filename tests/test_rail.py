"""Offline regression tests for ORR aggregation and smoothing."""

import pandas as pd
import pytest

from rail_data import charts, orr


def test_empty_fetch_preserves_saved_rail_data(monkeypatch, tmp_path):
    from rail_data import __main__ as cli

    path = tmp_path / "rail.csv"
    path.write_text("preserved source data\n")
    monkeypatch.setattr(orr, "build_rows", lambda: [])
    with pytest.raises(RuntimeError, match="Rail source returned no observations"):
        cli.main(["--csv", str(path), "--charts-dir", str(tmp_path)])
    assert path.read_text() == "preserved source data\n"


def _sheets():
    header = ["Franchise status", "Franchise title", "Franchise code",
              "Train operator", "Jan to Mar 2020", "Apr to Jun 2020"]
    metadata = [
        ["Existing", "Chiltern Railways", "HO", "Operator A"],
        ["Existing", "Crossrail", "EX", "Operator B"],
        ["Existing", "Greater Anglia", "GA", "Operator C"],
    ]
    trains = pd.DataFrame([[None] * 6] * 3 + [header] +
                          [m + v for m, v in zip(metadata, [[10, 10], [30, 30], [float("nan"), 0]])])
    values = pd.DataFrame([[None] * 6] * 3 + [header] +
                          [m + v for m, v in zip(metadata, [[80, 80], [100, 100], [50, 50]])])
    return trains, values


def test_orr_weighting_excludes_blank_weights_and_uses_calendar_quarters():
    trains, values = _sheets()
    wb = {"3103a": trains, "3103b": values, "3103c": values}
    rows = orr.build_rows(wb)
    assert all(r["value"] == 95 for r in rows)
    assert {(r["date"], r["quarter"]) for r in rows} == {
        ("2020-03-31", 1), ("2020-06-30", 2)
    }
    assert orr._to_float(float("inf")) is None


def test_orr_weighting_rejects_misaligned_operator_axes():
    trains, values = _sheets()
    values.iloc[[4, 5]] = values.iloc[[5, 4]].to_numpy()
    with pytest.raises(ValueError, match="operator rows"):
        orr._weighted_series(trains, values, orr.LONDON_SE_FRANCHISES)


def test_orr_does_not_reweight_around_missing_positive_weight_metric():
    trains, values = _sheets()
    values.iloc[5, 4] = float("nan")
    with pytest.raises(ValueError, match="metric missing for positive planned trains"):
        orr._weighted_series(trains, values, orr.LONDON_SE_FRANCHISES)
    trains.iloc[5, 4] = 0
    assert orr._weighted_series(trains, values, orr.LONDON_SE_FRANCHISES)[0][1] == 80


def test_rolling_mean_does_not_bridge_missing_quarters():
    df = pd.DataFrame({
        "region": [charts.LONDON] * 5,
        "metric": ["ppm_pct"] * 5,
        "date": ["2020-03-31", "2020-06-30", "2020-12-31", "2021-03-31", "2021-06-30"],
        "value": [80, 80, 80, 80, 80],
    })
    assert charts._maa(df, charts.LONDON, "ppm_pct").empty
    df.loc[5] = [charts.LONDON, "ppm_pct", "2021-09-30", 80]
    result = charts._maa(df, charts.LONDON, "ppm_pct")
    assert result["date"].tolist() == [pd.Timestamp("2021-09-30")]
    assert result["maa"].tolist() == [80]


def test_rolling_series_retains_internal_gaps_for_plotting(monkeypatch, tmp_path):
    dates = pd.date_range("2020-03-31", periods=10, freq="QE")
    df = pd.DataFrame([
        {"region": region, "metric": "ppm_pct", "date": date, "value": 80}
        for region in (charts.LONDON, charts.GB)
        for date in dates if date != dates[4]
    ])
    captured = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: captured.append(fig))
    charts._chart(df, "ppm_pct", "Title", "Subtitle", "Percent", "test.png", tmp_path)
    for line in captured[0].axes[0].lines:
        assert pd.isna(line.get_ydata()).sum() == 4
        assert list(pd.to_datetime(line.get_xdata())) == list(dates[3:])


def _official_workbook():
    header = ["Time period", "Great Britain (percentage)",
              "London and South East sector (percentage)"]
    return {"3113_PPM_(quarterly)": pd.DataFrame([
        ["Table 3113a: quarterly data", None, None], header,
        ["Jan to Mar 2026", 80, 81],
        ["Apr to Jun 2026 [p]", 82, 83],
        [None, None, None],
        ["Table 3113b: moving annual average", None, None], header,
        ["Jan to Mar 2026", 90, 91],
        ["Apr to Jun 2026 [p]", 92, 93],
    ])}


def test_orr_official_quarters_and_published_maa_are_separate_series():
    rows = orr.build_official_rows(_official_workbook())
    assert len(rows) == 8
    assert max(r["date"] for r in rows) == "2026-06-30"
    london = {(r["metric"], r["date"]): r for r in rows if r["region"] == orr.LONDON_SE}
    assert london[("ppm_official_pct", "2026-06-30")]["value"] == 83
    assert london[("ppm_official_maa_pct", "2026-06-30")]["value"] == 93
    assert london[("ppm_official_pct", "2026-06-30")]["period"].endswith("[p]")
    assert all("Table 3113" in r["source"] for r in rows)


def test_orr_official_maa_can_start_after_quarterly_but_not_have_internal_suppression():
    wb = _official_workbook()
    wb["3113_PPM_(quarterly)"].iloc[7, 1:] = ["[z]", "[z]"]
    rows = orr.build_official_rows(wb)
    assert len(rows) == 6
    assert {r["date"] for r in rows if r["metric"] == "ppm_official_maa_pct"} == {
        "2026-06-30",
    }
    wb = _official_workbook()
    wb["3113_PPM_(quarterly)"].iloc[8, 1:] = ["[z]", "[z]"]
    with pytest.raises(ValueError, match="invalid official"):
        orr.build_official_rows(wb)


def test_orr_official_missing_or_duplicate_data_is_not_silently_published():
    for bad in [None, -1, 101, float("inf")]:
        wb = _official_workbook()
        wb["3113_PPM_(quarterly)"].iloc[3, 2] = bad
        with pytest.raises(ValueError, match="invalid official"):
            orr.build_official_rows(wb)
    wb = _official_workbook()
    wb["3113_PPM_(quarterly)"].iloc[3, 0] = "Jan to Mar 2026"
    with pytest.raises(ValueError, match="duplicate official"):
        orr.build_official_rows(wb)
    wb = _official_workbook()
    wb["3113_PPM_(quarterly)"] = wb["3113_PPM_(quarterly)"].drop(index=3)
    with pytest.raises(ValueError, match="incomplete official"):
        orr.build_official_rows(wb)


def test_official_rail_chart_uses_published_maa_without_smoothing_it_again(monkeypatch, tmp_path):
    df = pd.DataFrame(orr.build_official_rows(_official_workbook()))
    captured = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: captured.append(fig))
    charts._chart(df, "ppm_official_maa_pct", "Title", "Subtitle", "Percent",
                  "official.png", tmp_path)
    lines = captured[0].axes[0].lines
    assert list(lines[0].get_ydata()) == [90, 92]
    assert list(lines[1].get_ydata()) == [91, 93]
    assert "Table 3113" in captured[0].texts[0].get_text()
    assert "trains-weighted" in captured[0].texts[0].get_text()


def test_rail_charts_explain_delay_thresholds_without_measure_acronyms(monkeypatch, tmp_path):
    official = pd.DataFrame(orr.build_official_rows(_official_workbook()))
    historical = []
    for region in (charts.LONDON, charts.GB):
        for date in pd.date_range("2020-03-31", periods=4, freq="QE"):
            for metric in ("ppm_pct", "casl_pct"):
                historical.append({"region": region, "date": date, "metric": metric, "value": 90})
    captured = []
    monkeypatch.setattr(charts.plt.Figure, "savefig", lambda fig, *a, **k: captured.append(fig))
    paths = charts.make_charts(pd.concat([official, pd.DataFrame(historical)]), tmp_path)
    assert len(paths) == 3
    for fig in captured:
        ax = fig.axes[0]
        visible = " ".join([ax.get_title(), ax.get_ylabel(), *[t.get_text() for t in ax.texts]])
        assert "PPM" not in visible
        assert "CaSL" not in visible
        caption = fig.texts[0].get_text()
        if "disruption" in ax.get_title():
            assert "more than 30 minutes late" in visible
            assert "full or part cancellations" in caption
        else:
            assert "5 / 10 minutes" in ax.get_ylabel()
            assert "within 10 minutes for long-distance" in caption
            assert "one-minute" in caption


def test_official_fetch_failure_preserves_saved_rail_dataset(monkeypatch, tmp_path):
    from rail_data import __main__ as cli

    path = tmp_path / "rail.csv"
    path.write_text("saved rail data\n")
    monkeypatch.setattr(orr, "build_rows", lambda: [{"value": 90}])

    def fail():
        raise ValueError("ORR: incomplete official PPM sector/quarter coverage")

    monkeypatch.setattr(orr, "build_official_rows", fail)
    with pytest.raises(ValueError, match="incomplete official"):
        cli.main(["--csv", str(path)])
    assert path.read_text() == "saved rail data\n"
