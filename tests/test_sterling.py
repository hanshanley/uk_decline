"""Offline tests for the ECB sterling exchange-rate pipeline."""

from __future__ import annotations

import io

import pandas as pd
import pytest
import requests

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


@pytest.mark.parametrize("failure", [504, 429, requests.Timeout(), requests.ConnectionError()])
def test_download_recovers_from_transient_failures(monkeypatch, failure) -> None:
    calls = []

    def download(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1 and isinstance(failure, Exception):
            raise failure
        response = requests.Response()
        response.status_code = failure if len(calls) == 1 else 200
        response._content = b"official ECB CSV"
        return response

    monkeypatch.setattr(ecb.requests, "get", download)
    monkeypatch.setattr(ecb.download_csv.retry, "sleep", lambda _: None)
    assert ecb.download_csv(timeout=7) == b"official ECB CSV"
    assert len(calls) == 2
    assert all(url == ecb.ECB_URL and kwargs["timeout"] == 7 for url, kwargs in calls)
    assert all(kwargs["headers"]["Accept"] == "text/csv" for _, kwargs in calls)


@pytest.mark.parametrize(("status", "attempts"), [(504, 5), (400, 1)])
def test_download_failure_is_bounded_and_never_uses_saved_data(monkeypatch, status, attempts) -> None:
    calls = []

    def download(*args, **kwargs):
        calls.append(args)
        response = requests.Response()
        response.status_code = status
        return response

    monkeypatch.setattr(ecb.requests, "get", download)
    monkeypatch.setattr(ecb.download_csv.retry, "sleep", lambda _: None)
    with pytest.raises(requests.HTTPError):
        ecb.download_csv()
    assert len(calls) == attempts


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
    assert by[(2000, "USD")].period_status == "incomplete_year"
    assert by[(2001, "USD")].period_status == "year_to_date"
    assert by[(2001, "USD")].months == 1


def test_missing_currency_rejected() -> None:
    frame = _monthly()
    frame = frame[frame["CURRENCY"] != "CHF"]
    with pytest.raises(ValueError, match="complete monthly coverage"):
        ecb.build_annual(frame)


def test_untrusted_host_rejected() -> None:
    with pytest.raises(ValueError):
        ecb.download_csv("https://example.com/data.csv")


def test_chart_renders(tmp_path) -> None:
    monthly = _monthly()
    for month in range(3, 13):
        extra = monthly[monthly["date"] == pd.Timestamp("2000-01")].copy()
        extra["date"] = pd.Timestamp(2000, month, 1)
        monthly = pd.concat([monthly, extra])
    frame = ecb.build_annual(monthly)
    assert set(frame.loc[frame["year"] == 2000, "period_status"]) == {"full_year"}
    output = charts.make_chart(frame, tmp_path / "sterling.png")
    assert output.exists()
    assert output.stat().st_size > 20_000


def test_currency_strength_change() -> None:
    frame = ecb.build_annual(_monthly())
    changed = charts.currency_strength_change(frame)
    base = changed[changed["year"] == 2000]
    assert base["change_pct"].tolist() == pytest.approx([0, 0, 0, 0])
    usd_2001 = changed[
        (changed["year"] == 2001) & (changed["currency"] == "USD")
    ].iloc[0]
    assert usd_2001["change_pct"] == pytest.approx((2.1 / 1.5 - 1) * 100)
