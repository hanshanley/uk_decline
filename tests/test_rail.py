"""Offline regression tests for ORR aggregation and smoothing."""

import pandas as pd
import pytest

from rail_data import charts, orr


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
