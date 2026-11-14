"""Exercise real World Bank consumers against transient and persistent failures."""

from unittest.mock import Mock

import pytest
import requests
from tenacity import wait_none

from europe_data import _http, _worldbank

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
        return pyramids._fetch_api_counts(["GBR"], 2024, 2024)
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


def response(year=2024, pages=1, code="GBR", value=1.5):
    result = Mock()
    result.json.return_value = [{"pages": pages}, [{
        "countryiso3code": code, "date": str(year), "value": value,
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
    if source == "pyramids":
        assert first.kwargs["params"]["source"] == 16


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


@pytest.mark.parametrize("failure", ["timeout", "gateway"])
def test_bulk_recovery_discards_partial_pages_and_preserves_wgi_database(client, failure):
    def download(url, params, **kwargs):
        codes = url.split("/country/")[1].split("/indicator/")[0]
        assert params["source"] == 3
        assert params["date"] == "2024:2024"
        if ";" in codes:
            if params["page"] == 1:
                return response(pages=2, value=999)
            if failure == "timeout":
                raise requests.ReadTimeout("bulk page two timed out")
            raise requests.HTTPError("502", response=Mock(status_code=502))
        return response(code=codes)

    client.get.side_effect = download
    rows = _worldbank.observations("GOV_WGI_CC.EST", ["GBR", "USA"], 2024, 2024, source=3)
    assert sorted((row["countryiso3code"], row["value"]) for row in rows) == [
        ("GBR", 1.5), ("USA", 1.5),
    ]
    assert client.get.call_count == 4


def test_single_country_recovery_partitions_years_without_gaps_or_overlap(client):
    def download(url, params, **kwargs):
        start, end = map(int, params["date"].split(":"))
        if start != end:
            raise requests.ReadTimeout("multi-year query timed out")
        return response(year=start)

    client.get.side_effect = download
    rows = _worldbank.observations("SP.POP.65UP.TO.ZS", ["GBR"], 2020, 2023)
    assert [int(row["date"]) for row in rows] == [2020, 2021, 2022, 2023]
    assert client.get.call_count == 7


def test_failed_partition_never_returns_its_successful_sibling(client):
    def download(url, **kwargs):
        codes = url.split("/country/")[1].split("/indicator/")[0]
        if codes != "GBR":
            raise requests.ReadTimeout("bulk query or final partition failed")
        return response()

    client.get.side_effect = download
    with pytest.raises(requests.ReadTimeout, match="final partition failed"):
        _worldbank.observations("SP.POP.65UP.TO.ZS", ["GBR", "USA"], 2024, 2024)
    assert client.get.call_count == 7


def test_permanent_bulk_errors_are_not_hidden_by_query_partitioning(client):
    client.get.side_effect = requests.HTTPError("404", response=Mock(status_code=404))
    with pytest.raises(requests.HTTPError, match="404"):
        _worldbank.observations("INVALID", ["GBR", "USA"], 2020, 2024)
    assert client.get.call_count == 1


@pytest.mark.parametrize("records", [None, []])
def test_unpublished_year_has_no_observations_rather_than_invalid_pagination(client, records):
    result = Mock()
    result.json.return_value = [{"pages": 0, "total": 0}, records]
    client.get.return_value = result
    assert _worldbank.observations("GOV_WGI_CC.EST", ["GBR"], 1974, 1974, source=3) == []


def test_incomplete_pagination_is_rejected_without_returning_first_page(client):
    missing = Mock()
    missing.json.return_value = [{"pages": 2}, []]
    client.get.side_effect = [response(pages=2), missing]
    with pytest.raises(ValueError, match="Missing World Bank observations"):
        _worldbank.observations("SP.POP.65UP.TO.ZS", ["GBR"], 2024, 2024)


def test_population_response_from_wrong_database_is_rejected(client):
    wrong = response()
    wrong.json.return_value[0]["sourceid"] = "2"
    client.get.return_value = wrong
    with pytest.raises(ValueError, match="Unexpected World Bank database"):
        _worldbank.observations("SP.POP.0509.FE", ["GBR"], 2024, 2024, source=16)


def test_bls_cached_503_recovery_uses_revalidation_and_preserves_query(client):
    from tuition import cpi

    failed = response()
    failed.raise_for_status.side_effect = requests.HTTPError(
        "503 cached gateway failure", response=Mock(status_code=503),
    )
    current = Mock()
    current.json.return_value = {"status": "REQUEST_SUCCEEDED"}
    client.get.side_effect = [failed, current]
    params = {"startyear": 1973, "endyear": 1982, "annualaverage": "true"}
    assert cpi.get_json(cpi.SOURCE_URL, params) == {"status": "REQUEST_SUCCEEDED"}
    first, second = client.get.call_args_list
    assert first.kwargs["params"] == second.kwargs["params"] == params
    assert "headers" not in first.kwargs
    assert second.kwargs["headers"] == {"Cache-Control": "no-cache"}


def test_tuition_permanent_http_error_still_fails_without_retry(client):
    from tuition import http

    client.get.side_effect = requests.HTTPError("404", response=Mock(status_code=404))
    with pytest.raises(requests.HTTPError, match="404"):
        http.get_json("https://api.bls.gov/missing")
    assert client.get.call_count == 1


def bad_request(url="https://api.worldbank.org/v2/country/GBR/indicator/SP.POP.TOTL",
                body=b"<html><title>400 Bad Request</title></html>"):
    result = requests.Response()
    result.status_code = 400
    result.url = url
    result._content = body
    result._content_consumed = True
    result.headers["Content-Type"] = "text/html"
    return result


@pytest.mark.parametrize("source", SOURCES)
def test_worldbank_consumers_recover_from_intermittent_bad_request(client, source):
    client.get.side_effect = lambda *a, **k: (
        bad_request() if client.get.call_count == 1 else response()
    )
    assert fetch_rows(source)
    first, second = client.get.call_args_list[:2]
    assert first.args == second.args
    assert first.kwargs == second.kwargs
    assert all(
        call.kwargs["headers"]["Cache-Control"] == "no-cache"
        for call in client.get.call_args_list
    )


@pytest.mark.parametrize("source", SOURCES)
def test_worldbank_bad_request_exhaustion_stops_without_saved_data(client, source):
    client.get.side_effect = lambda *a, **k: bad_request()
    with pytest.raises(requests.HTTPError, match="400"):
        fetch_rows(source)
    assert client.get.call_count == 5


@pytest.mark.parametrize("body", [
    b'[{"message":[{"id":"120","value":"Invalid parameter"}]}]',
    b'{"error":"Invalid endpoint"}',
    b'<wb:error><wb:message id="120">Invalid parameter</wb:message></wb:error>',
])
def test_structured_worldbank_bad_requests_still_fail_immediately(client, body):
    client.get.return_value = bad_request(body=body)
    with pytest.raises(requests.HTTPError, match="400"):
        _worldbank.observations("INVALID", ["GBR", "USA"], 2020, 2024)
    assert client.get.call_count == 1


@pytest.mark.parametrize("url", [
    "https://api.bls.gov/publicAPI/v2/timeseries/data",
    "https://api.worldbank.org/v2/invalid",
    "https://example.org/v2/country/GBR/indicator/SP.POP.TOTL",
])
def test_bad_request_recovery_is_scoped_to_worldbank_indicator_queries(client, url):
    client.get.return_value = bad_request(url)
    with pytest.raises(requests.HTTPError, match="400"):
        _http.get_json(url)
    assert client.get.call_count == 1


def test_bad_request_on_later_bulk_page_restarts_atomically(client):
    def download(url, params, **kwargs):
        codes = url.split("/country/")[1].split("/indicator/")[0]
        if ";" in codes:
            if params["page"] == 1:
                return response(pages=2, value=999)
            return bad_request(url)
        return response(code=codes)

    client.get.side_effect = download
    rows = _worldbank.observations("GOV_WGI_CC.EST", ["GBR", "USA"], 2024, 2024, source=3)
    assert sorted((row["countryiso3code"], row["value"]) for row in rows) == [
        ("GBR", 1.5), ("USA", 1.5),
    ]
    assert client.get.call_count == 4
    assert all(call.kwargs["params"]["source"] == 3 for call in client.get.call_args_list)


def test_persistent_bad_request_partition_does_not_return_successful_sibling(client):
    def download(url, **kwargs):
        codes = url.split("/country/")[1].split("/indicator/")[0]
        return response() if codes == "GBR" else bad_request(url)

    client.get.side_effect = download
    with pytest.raises(requests.HTTPError, match="400"):
        _worldbank.observations("SP.POP.65UP.TO.ZS", ["GBR", "USA"], 2024, 2024)
    assert client.get.call_count == 7


@pytest.mark.parametrize("source", ["trade", "gdp", "markets"])
def test_later_page_bad_request_recovers_without_partial_or_duplicate_rows(client, source):
    client.get.side_effect = [
        response(2023, pages=2), bad_request(), response(2024, pages=2),
    ]
    rows = fetch_rows(source)
    assert sorted(row["year"] for row in rows) == [2023, 2024]
    assert [call.kwargs["params"]["page"] for call in client.get.call_args_list] == [1, 2, 2]
