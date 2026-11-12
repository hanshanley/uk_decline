"""Exercise production source transports, including streamed and guarded downloads."""

import ast
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from importlib import import_module
from unittest.mock import Mock

import pytest
import requests
from tenacity import wait_none

from europe_data import _http
from scripts.refresh_data import ROOT, STEPS


SOURCES = (
    "income", "food-banks", "rail", "london", "treasury", "nations", "lse",
    "lse-catalogue", "sterling", "csew", "ni-html", "tuition-common", "collegeboard",
    "trust-json", "trust-text", "tax-text", "migration-json", "migration-bytes",
    "markets-json", "nhs-json", "nhs-bytes", "shared-text", "shared-bytes",
)


def response(url="https://www.nhs.uk/data"):
    result = Mock(
        status_code=200, url=url, is_redirect=False, is_permanent_redirect=False,
        headers={}, content=b"current", text="current",
    )
    result.iter_content.side_effect = lambda **kwargs: iter([b"current"])
    result.json.return_value = {"ok": True, "Data": [{
        "displayTitle": "Main Market factsheet October 2026",
        "fileType": "xlsx", "downloadLink": "https://docs.londonstockexchange.com/current.xlsx",
    }]}
    return result


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    monkeypatch.setattr(requests, "get", client.get)
    monkeypatch.setattr(_http, "session", lambda: client)
    monkeypatch.setattr(_http, "wait_exponential", lambda **kwargs: wait_none())
    return client


def fetch(source, client, monkeypatch):
    if source == "income":
        from europe_data import recent_income
        return recent_income.download("https://www.ons.gov.uk/income.xlsx")
    if source == "food-banks":
        from foodbank_data import fetch as food
        return food.http_get("https://cms.trussell.org.uk/current.xlsx")
    if source == "rail":
        from rail_data import orr
        monkeypatch.setattr(orr.pd, "read_excel", lambda *a, **k: {"current": True})
        return orr.download_workbook()
    if source == "london":
        from london_data import ons
        return ons._get("https://www.ons.gov.uk/current.xlsx", timeout=60)
    if source == "treasury":
        from austerity_data import treasury
        return treasury._get("https://www.gov.uk/current.xlsx")
    if source == "nations":
        from crime_data import nations
        return nations._get(nations.SCOTLAND_ANSWER_URL, ("parliament.scot",))
    if source in ("lse", "lse-catalogue"):
        from markets_data import lse_factsheets as lse
        if source == "lse":
            return lse._download("https://docs.londonstockexchange.com/current.xlsx")
        lse._factsheet_catalogue.cache_clear()
        return lse._factsheet_catalogue("Main Market")
    if source == "sterling":
        from sterling_data import ecb
        return ecb.download_csv()
    if source == "csew":
        from crime_data import csew
        monkeypatch.setattr(csew, "_SESSION", client)
        return csew._get_json("/dataset")
    if source == "ni-html":
        from nhs_data import northern_ireland as ni
        monkeypatch.setattr(ni._http, "session", lambda: client)
        monkeypatch.setattr(ni, "_polite_pause", Mock())
        ni._html.cache_clear()
        return ni._html("https://www.health-ni.gov.uk/current")
    if source == "tuition-common":
        from tuition import common_year
        class DownloadsComplete(Exception):
            pass
        monkeypatch.setattr(common_year, "session", lambda: client)
        monkeypatch.setattr(common_year, "latest_workbook", lambda _: (
            2025, "https://eurydice.eacea.ec.europa.eu/current.xlsx",
        ))
        monkeypatch.setattr(
            common_year.pd, "read_excel", Mock(side_effect=DownloadsComplete),
        )
        with pytest.raises(DownloadsComplete):
            common_year.main([])
        return True
    if source == "collegeboard":
        from tuition import fetch_collegeboard as collegeboard
        class DownloadsComplete(Exception):
            pass
        monkeypatch.setattr(collegeboard, "session", lambda: client)
        monkeypatch.setattr(collegeboard, "latest_workbook", lambda _: (
            "https://research.collegeboard.org/current.xlsx", 2025,
        ))
        monkeypatch.setattr(
            collegeboard.pd, "read_excel", Mock(side_effect=DownloadsComplete),
        )
        with pytest.raises(DownloadsComplete):
            collegeboard.main([])
        return True
    package, kind = source.split("-")
    module = import_module({
        "trust": "trust_data._http", "tax": "tax._http",
        "migration": "uk_migration._http", "markets": "markets_data._http",
        "nhs": "nhs_data._http", "shared": "europe_data._http",
    }[package])
    monkeypatch.setattr(module, "session", lambda: client)
    return getattr(module, f"get_{kind}")("https://www.nhs.uk/data")


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("failure", ["timeout", "gateway", "rate_limit"])
def test_source_entrypoints_recover_and_preserve_request_options(
    source, failure, client, monkeypatch,
):
    current = response()
    failed = response()
    failed.status_code = 429 if failure == "rate_limit" else 502
    failed.headers = {"Retry-After": "0"}
    failed.raise_for_status.side_effect = requests.HTTPError("transient", response=failed)

    def download(url, **kwargs):
        if client.get.call_count == 1:
            if failure == "timeout":
                raise requests.ReadTimeout("transient")
            return failed
        current.url = url
        return current

    client.get.side_effect = download
    assert fetch(source, client, monkeypatch)
    first, second = client.get.call_args_list[:2]
    assert first.args == second.args
    assert {k: v for k, v in first.kwargs.items() if k != "headers"} == {
        k: v for k, v in second.kwargs.items() if k != "headers"
    }
    assert second.kwargs["headers"] == {
        **first.kwargs.get("headers", {}), "Cache-Control": "no-cache",
    }
    assert first.kwargs["timeout"] > 0
    if failure != "timeout":
        failed.close.assert_called_once()


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("failure", ["persistent_timeout", "permanent_404"])
def test_every_source_transport_is_bounded_and_fails_closed(
    source, failure, client, monkeypatch,
):
    if failure == "persistent_timeout":
        error = requests.ReadTimeout("source unavailable")
        attempts = 5
    else:
        missing = requests.Response()
        missing.status_code = 404
        error = requests.HTTPError("source unavailable", response=missing)
        attempts = 1
    client.get.side_effect = error
    with pytest.raises(type(error), match="source unavailable"):
        fetch(source, client, monkeypatch)
    assert client.get.call_count == attempts


def test_stream_failure_discards_partial_bytes_and_closes_both_responses(client, monkeypatch):
    from nhs_data import _http as nhs
    first, second = response(), response()

    def interrupted(**kwargs):
        yield b"partial"
        raise requests.ConnectionError("interrupted stream")

    first.iter_content.side_effect = interrupted
    client.get.side_effect = [first, second]
    monkeypatch.setattr(nhs, "session", lambda: client)
    assert nhs.get_bytes("https://www.nhs.uk/data") == b"current"
    first.close.assert_called_once()
    second.close.assert_called_once()


def test_ni_html_preserves_polite_pause_on_every_attempt(client, monkeypatch):
    from nhs_data import northern_ireland as ni
    pause = Mock()
    monkeypatch.setattr(ni, "_polite_pause", pause)
    monkeypatch.setattr(ni._http, "session", lambda: client)
    ni._html.cache_clear()
    current = response("https://www.health-ni.gov.uk/current")
    client.get.side_effect = [requests.ReadTimeout("transient"), current]
    assert ni._html(current.url) == "current"
    assert pause.call_count == 2


@pytest.mark.parametrize("defect", ["initial_host", "redirect_host", "oversize"])
def test_guarded_downloads_still_reject_invalid_hosts_and_oversized_bodies(
    defect, client, monkeypatch,
):
    from nhs_data import _http as nhs
    current = response()
    current.url = "https://example.invalid/data" if defect == "redirect_host" else current.url
    client.get.return_value = current
    monkeypatch.setattr(nhs, "session", lambda: client)
    url = "https://example.invalid/data" if defect == "initial_host" else "https://www.nhs.uk/data"
    with pytest.raises(ValueError):
        nhs.get_bytes(url, max_bytes=2 if defect == "oversize" else 100)
    assert client.get.call_count == (0 if defect == "initial_host" else 1)


@pytest.mark.parametrize("header,expected", [("86400", 60), ("-1", 1), ("invalid", 1), ("date", 30)])
def test_retry_after_is_respected_but_cannot_stall_the_refresh(monkeypatch, header, expected):
    now = datetime(2026, 11, 12, 21, tzinfo=timezone.utc)
    monkeypatch.setattr(_http, "datetime", Mock(now=Mock(return_value=now)))
    failed = requests.Response()
    failed.status_code = 429
    failed.headers["Retry-After"] = (
        format_datetime(now + timedelta(seconds=30), usegmt=True) if header == "date" else header
    )
    state = Mock()
    state.outcome.exception.return_value = requests.HTTPError(response=failed)
    assert _http._retry_delay(state, lambda _: 1) == expected


def test_update_sources_cannot_reintroduce_one_shot_python_http_clients():
    packages = {
        command[1].split(".")[0]
        for commands in STEPS.values() for command in commands if command[0] == "-m"
    }
    violations = []
    for package in sorted(packages):
        for path in (ROOT / package).rglob("*.py"):
            if path == ROOT / "europe_data/_http.py":
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                direct = isinstance(owner, ast.Name) and owner.id in {
                    "requests", "client", "_session", "_SESSION",
                }
                session_call = isinstance(owner, ast.Call) and (
                    (isinstance(owner.func, ast.Name) and owner.func.id == "session")
                    or (isinstance(owner.func, ast.Attribute) and owner.func.attr in {"session", "Session"})
                )
                if node.func.attr in {"get", "post", "request"} and (direct or session_call):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not violations, f"Update source bypasses bounded HTTP transport: {violations}"
