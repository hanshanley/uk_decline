"""Offline tests for trade as a share of GDP."""

from __future__ import annotations

import pandas as pd
import pytest

from trade_data import charts, worldbank


def test_parse_payload() -> None:
    payload = [
        {"pages": 2},
        [
            {
                "countryiso3code": "GBR",
                "date": "2024",
                "value": 62.8,
            },
            {
                "countryiso3code": "USA",
                "date": "2024",
                "value": None,
            },
            {
                "countryiso3code": "CAN",
                "date": "2024",
                "value": 66.0,
            },
        ],
    ]
    pages, rows = worldbank.parse_payload(payload)
    assert pages == 2
    assert rows == [
        {
            "country": "United Kingdom",
            "country_code": "GBR",
            "year": 2024,
            "value": 62.8,
            "unit": "percent of GDP",
            "source": worldbank.SOURCE,
        }
    ]


def test_bad_payload_rejected() -> None:
    with pytest.raises(ValueError):
        worldbank.parse_payload({"not": "world bank"})


def test_untrusted_host_rejected() -> None:
    with pytest.raises(ValueError):
        worldbank._ensure_host("https://example.com/data")


def test_chart_renders(tmp_path) -> None:
    rows = []
    for code, name, values in [
        ("GBR", "United Kingdom", [(2000, 50), (2024, 63)]),
        ("DEU", "Germany", [(2000, 60), (2024, 80)]),
        ("FRA", "France", [(2000, 55), (2024, 68)]),
        ("JPN", "Japan", [(2000, 20), (2024, 45)]),
        ("USA", "United States", [(2000, 25), (2024, 25)]),
    ]:
        for year, value in values:
            rows.append(
                {
                    "country": name,
                    "country_code": code,
                    "year": year,
                    "value": value,
                    "unit": "percent of GDP",
                    "source": worldbank.SOURCE,
                }
            )
    output = charts.make_chart(pd.DataFrame(rows), tmp_path / "trade.png")
    assert output.exists()
    assert output.stat().st_size > 20_000

