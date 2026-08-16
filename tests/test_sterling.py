"""Offline tests for the ECB sterling exchange-rate pipeline."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from sterling_data import charts, ecb


def _monthly() -> pd.DataFrame:
    rows = []
    values = {
        "2000-01": {"GBP": 0.5, "USD": 1.0, "JPY": 100.0, "CHF": 1.5},
        "2000-02": {"GBP": 0.5, "USD": 1.1, "JPY": 110.0, "CHF": 1.6},
        "2001-01": {"GBP": 0.8, "USD": 1.2, "JPY": 120.0, "CHF": 1.4},
    }
    for month, currencies in values.items():
        for currency, value in currencies.items():
            rows.append(
                {
                    "date": pd.Timestamp(month),
                    "CURRENCY": currency,
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


def test_parse_monthly_csv() -> None:
    csv = io.StringIO(
        "TIME_PERIOD,CURRENCY,OBS_VALUE\n"
        "2000-01,GBP,0.5\n2000-01,USD,1.0\n"
        "2000-01,JPY,100\n2000-01,CHF,1.5\n"
    )
    frame = ecb.parse_monthly(csv)
    assert set(frame["CURRENCY"]) == {"GBP", "USD", "JPY", "CHF"}
    assert frame["date"].dt.strftime("%Y-%m").unique().tolist() == ["2000-01"]


def test_cross_rate_math_and_ytd_status() -> None:
    annual = ecb.build_annual(_monthly())
    by = {(row.year, row.currency): row for row in annual.itertuples()}

    # 2000 monthly USD/GBP cross-rates: 2.0 and 2.2 -> annual average 2.1.
    assert by[(2000, "USD")].value == pytest.approx(2.1)
    # EUR/GBP is 1 / 0.5 = 2.0 in both months.
    assert by[(2000, "EUR")].value == pytest.approx(2.0)
    # JPY/GBP: 200 and 220 -> 210.
    assert by[(2000, "JPY")].value == pytest.approx(210)
    assert by[(2000, "CHF")].value == pytest.approx(3.1)
    assert by[(2000, "USD")].period_status == "full_year"
    assert by[(2001, "USD")].period_status == "year_to_date"
    assert by[(2001, "USD")].months == 1


def test_missing_currency_rejected() -> None:
    frame = _monthly()
    frame = frame[frame["CURRENCY"] != "CHF"]
    with pytest.raises(ValueError, match="complete monthly coverage"):
        ecb.build_annual(frame)


def test_untrusted_host_rejected() -> None:
    with pytest.raises(ValueError):
        ecb._ensure_host("https://example.com/data.csv")


def test_chart_renders(tmp_path) -> None:
    frame = ecb.build_annual(_monthly())
    output = charts.make_chart(frame, tmp_path / "sterling.png")
    assert output.exists()
    assert output.stat().st_size > 20_000


def test_index_to_2000() -> None:
    frame = ecb.build_annual(_monthly())
    indexed = charts.index_to_year(frame)
    base = indexed[indexed["year"] == 2000]
    assert base["index"].tolist() == pytest.approx([100, 100, 100, 100])
    usd_2001 = indexed[
        (indexed["year"] == 2001) & (indexed["currency"] == "USD")
    ].iloc[0]
    assert usd_2001["index"] == pytest.approx((1.5 / 2.1) * 100)
