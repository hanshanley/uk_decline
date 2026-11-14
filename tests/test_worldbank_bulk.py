"""Verify separate-host bulk recovery without snapshots or silent missing data."""

import csv
from datetime import date
import io
import os
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests

from europe_data import _worldbank, _worldbank_bulk as bulk
from europe_data import _http
from tenacity import wait_none

YEAR = date.today().year - 1
INDICATOR = "NY.GDP.PCAP.KD"


def archive(source=2, defect=None):
    fields = [*bulk.FIELDS, str(YEAR - 1), str(YEAR)]
    data = io.StringIO()
    writer = csv.DictWriter(data, fieldnames=fields)
    writer.writeheader()
    row = {
        "Country Name": "United Kingdom", "Country Code": "GBR",
        "Indicator Name": "GDP", "Indicator Code": INDICATOR,
        str(YEAR - 1): "42", str(YEAR): "43",
    }
    if defect == "nonfinite":
        row[str(YEAR)] = "nan"
    if defect == "missing":
        row["Country Code"] = "USA"
    writer.writerow(row)
    if defect == "duplicate":
        writer.writerow(row)
    result = io.BytesIO()
    with ZipFile(result, "w") as zipped:
        zipped.writestr(bulk.ARCHIVES[source][1], data.getvalue())
    return result.getvalue()


def prepare(monkeypatch, tmp_path, source=2, defect=None):
    monkeypatch.setattr(bulk, "get_bytes", lambda *a, **k: archive(source, defect))
    bulk.prepare(tmp_path, source, {INDICATOR})
    monkeypatch.setenv(bulk.ENV, str(tmp_path))


@pytest.mark.parametrize("source", [2, 3])
def test_fresh_bulk_serves_exact_requested_database_countries_and_years_without_api(
    monkeypatch, tmp_path, source,
):
    prepare(monkeypatch, tmp_path, source)
    download = Mock(side_effect=AssertionError("API should not be required"))
    rows = _worldbank.observations(INDICATOR, ["GBR"], YEAR, YEAR, source=source, download=download)
    assert [(row["countryiso3code"], row["date"], row["value"]) for row in rows] == [
        ("GBR", str(YEAR), 43),
    ]
    download.assert_not_called()


@pytest.mark.parametrize("defect", ["nonfinite", "missing", "duplicate"])
def test_invalid_bulk_profiles_use_live_api_without_returning_partial_bulk_rows(
    monkeypatch, tmp_path, defect,
):
    prepare(monkeypatch, tmp_path, defect=defect)
    download = Mock(return_value=[{"pages": 1}, [{"date": str(YEAR), "value": 99}]])
    assert _worldbank.observations(INDICATOR, ["GBR"], YEAR - 1, YEAR, download=download) == [
        {"date": str(YEAR), "value": 99},
    ]
    download.assert_called_once()


def test_bulk_preparation_never_installs_a_partial_indicator_set(monkeypatch, tmp_path):
    monkeypatch.setattr(bulk, "get_bytes", lambda *a, **k: archive())
    with pytest.raises(ValueError, match="lacks indicators"):
        bulk.prepare(tmp_path, 2, {INDICATOR, "MISSING"})
    assert not (tmp_path / "2").exists()


def test_missing_historical_year_column_cannot_silently_truncate_a_query(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    path = tmp_path / "2" / f"{INDICATOR}.csv"
    text = path.read_text().splitlines()
    text[0] = text[0].replace(f",{YEAR - 1}", "")
    text[1] = text[1].replace(",42", "")
    path.write_text("\n".join(text) + "\n")
    download = Mock(side_effect=requests.HTTPError("API unavailable", response=Mock(status_code=404)))
    with pytest.raises(requests.HTTPError, match="API unavailable"):
        _worldbank.observations(INDICATOR, ["GBR"], YEAR - 1, YEAR, download=download)
    download.assert_called_once()


def test_governance_retains_documented_nonannual_early_years_and_nulls(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path, source=3)
    path = tmp_path / "3" / f"{INDICATOR}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*bulk.FIELDS, "1996", "1998", "2000"])
        writer.writeheader()
        writer.writerow({
            "Country Name": "United Kingdom", "Country Code": "GBR",
            "Indicator Name": "Governance", "Indicator Code": INDICATOR,
            "1996": "1.5", "1998": "", "2000": "-0.2",
        })
    rows = bulk.observations(INDICATOR, ["GBR"], 1996, 2000, source=3)
    assert [(row["date"], row["value"]) for row in rows] == [
        ("1996", 1.5), ("1998", None), ("2000", -0.2),
    ]


def test_population_database_sixteen_never_uses_wdi_bulk(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    assert bulk.observations(INDICATOR, ["GBR"], YEAR, YEAR, source=16) is None


@pytest.mark.parametrize("failure", [requests.ReadTimeout("offline"), ValueError("invalid archive")])
def test_bulk_outage_preserves_live_api_recovery_and_never_uses_an_old_directory(
    monkeypatch, tmp_path, failure,
):
    monkeypatch.setenv(bulk.ENV, str(tmp_path / "old"))
    monkeypatch.setattr(bulk, "required_indicators", lambda: {2: {INDICATOR}})
    monkeypatch.setattr(bulk, "prepare", Mock(side_effect=failure))
    with bulk.fresh_bulk([2]):
        fresh = Path(os.environ[bulk.ENV])
        assert fresh != tmp_path / "old"
        client = Mock()
        client.get.side_effect = requests.ReadTimeout("API offline too")
        monkeypatch.setattr(_http, "session", lambda: client)
        monkeypatch.setattr(_http, "wait_exponential", lambda **k: wait_none())
        with pytest.raises(requests.ReadTimeout, match="API offline too"):
            _worldbank.observations(INDICATOR, ["GBR"], YEAR, YEAR)
        assert client.get.call_count == 5
    assert not fresh.exists()
    assert os.environ[bulk.ENV] == str(tmp_path / "old")


def test_bulk_cache_is_deleted_after_success_and_next_refresh_downloads_again(monkeypatch):
    monkeypatch.delenv(bulk.ENV, raising=False)
    monkeypatch.setattr(bulk, "required_indicators", lambda: {2: {INDICATOR}})
    download = Mock(return_value=archive())
    monkeypatch.setattr(bulk, "get_bytes", download)
    directories = []
    for _ in range(2):
        with bulk.fresh_bulk([2]):
            directory = Path(os.environ[bulk.ENV])
            directories.append(directory)
            assert _worldbank.observations(INDICATOR, ["GBR"], YEAR, YEAR)[0]["value"] == 43
        assert not directory.exists()
    assert directories[0] != directories[1]
    assert download.call_count == 2
    assert bulk.ENV not in os.environ


def test_refresh_entrypoint_prepares_both_live_databases_before_sources(monkeypatch):
    from contextlib import contextmanager
    from scripts import refresh_data
    events = []

    @contextmanager
    def fresh(sources):
        events.append(("prepare", sources))
        yield
        events.append(("cleanup",))

    monkeypatch.setattr(bulk, "fresh_bulk", fresh)
    monkeypatch.setattr(refresh_data, "refresh", lambda **kwargs: events.append(("refresh",)))
    monkeypatch.setattr("sys.argv", ["refresh_data.py", "--check-all"])
    refresh_data.main()
    assert events == [("prepare", [2, 3]), ("refresh",), ("cleanup",)]
