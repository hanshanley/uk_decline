"""Exercise real World Bank consumers against transient and persistent failures."""

from unittest.mock import Mock

import pytest
import requests
from tenacity import wait_none

from europe_data import _http

SOURCES = ("trade", "ageing", "pyramids", "crime", "markets", "trust",
           "migration", "tuition", "gdp", "ppp")


def fetch_rows(source):
    if source == "trade":
        from trade_data import worldbank
        return worldbank.fetch(2024, 2024)
    if source == "ageing":
        from age_data import worldbank
        return worldbank.fetch(2024, 2024, iso3s=["GBR"])
    if source == "pyramids":
        from age_data import pyramids
        return pyramids._fetch_counts(["GBR"], 2024, 2024)
    if source == "crime":
        from crime_data import homicide
        return homicide.build_rows(2024, 2024, iso3s=["GBR"])
    if source == "markets":
        from markets_data import worldbank
        return worldbank.fetch(2024, 2024, codes=["GBR"],
                               indicators=["CM.MKT.LCAP.GD.ZS"])
    if source == "trust":
        from trust_data import worldbank
        return worldbank.fetch(2024, 2024, iso3s=["GBR"],
                               indicators=["GOV_WGI_GE.EST"])
    if source == "migration":
        from uk_migration.sources import worldbank
        return worldbank._fetch_indicator("SP.POP.TOTL", 2024, 2024)
    if source == "tuition":
        from tuition import rates
        return rates.fetch_series("PA.NUS.FCRF", ["GBR"], 2024, 2024)
    if source == "gdp":
        from europe_data import worldbank
        return worldbank.fetch(2024, 2024, iso3s=["GBR"],
                               indicators=["NY.GDP.PCAP.KD"])
    if source == "ppp":
        from ppp_data import worldbank
        return list(worldbank._fetch_indicator("NY.GDP.PCAP.PP.CD", ["GBR"], 2024, 2024))
    raise AssertionError(source)


def response(year=2024, pages=1):
    result = Mock()
    result.json.return_value = [{"pages": pages}, [{
        "countryiso3code": "GBR", "date": str(year), "value": 1.5,
        "country": {"id": "GB", "value": "United Kingdom"},
    }]]
    return result


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    monkeypatch.setattr(_http, "session", lambda: client)
    monkeypatch.setattr(_http, "wait_exponential", lambda **kwargs: wait_none())
    bypass = Mock(side_effect=AssertionError("World Bank consumer bypassed shared HTTP"))
    monkeypatch.setattr(requests, "get", bypass)
    monkeypatch.setattr(requests.Session, "get", bypass)
    return client


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("failure", ["timeout", "gateway"])
def test_worldbank_consumers_recover_without_losing_request_parameters(client, source, failure):
    current = response()
    failed = response()
    failed.raise_for_status.side_effect = requests.HTTPError("502 cached gateway failure")

    def download(*args, **kwargs):
        if client.get.call_count == 1:
            if failure == "timeout":
                raise requests.ReadTimeout("World Bank read timed out")
            return failed
        return current

    client.get.side_effect = download
    assert fetch_rows(source)
    first, second = client.get.call_args_list[:2]
    assert first.args == second.args
    assert first.kwargs == second.kwargs
    assert first.kwargs["headers"] == {"Cache-Control": "no-cache"}
    assert first.kwargs["timeout"] == 60
    if source == "trust":
        assert first.kwargs["params"]["source"] == 3


@pytest.mark.parametrize("source", SOURCES)
def test_worldbank_consumers_stop_after_five_failures_without_saved_data(client, source):
    client.get.side_effect = requests.ReadTimeout("persistent upstream failure")
    with pytest.raises(requests.ReadTimeout, match="persistent upstream failure"):
        fetch_rows(source)
    assert client.get.call_count == 5


@pytest.mark.parametrize("source", ["trade", "crime"])
def test_retried_second_page_neither_duplicates_nor_skips_observations(client, source):
    client.get.side_effect = [
        response(2023, pages=2), requests.ReadTimeout("page two timed out"), response(2024, pages=2),
    ]
    rows = fetch_rows(source)
    assert sorted(row["year"] for row in rows) == [2023, 2024]
    assert [call.kwargs["params"]["page"] for call in client.get.call_args_list] == [1, 2, 2]
