"""Offline tests for the gov.uk / ONS download resolvers (get_json is monkeypatched)."""

from __future__ import annotations

import pytest

from uk_migration import _govuk


def test_govuk_attachment_matches_prefix(monkeypatch):
    payload = {
        "details": {
            "attachments": [
                {"file_url": "https://assets/media/x/asylum-summary-mar-2026-tables.ods"},
                {"file_url": "https://assets/media/y/asylum-claims-datasets-mar-2026.xlsx"},
                {"url": "https://assets/media/z/visas-summary-mar-2026-tables.ods"},
            ]
        }
    }
    monkeypatch.setattr(_govuk, "get_json", lambda url, *a, **k: payload)
    url, filename = _govuk.govuk_attachment("asylum-claims-datasets-")
    assert filename == "asylum-claims-datasets-mar-2026.xlsx"
    assert url.endswith(filename)


def test_govuk_attachment_missing_prefix_raises(monkeypatch):
    monkeypatch.setattr(_govuk, "get_json", lambda url, *a, **k: {"details": {"attachments": []}})
    with pytest.raises(LookupError):
        _govuk.govuk_attachment("does-not-exist-")


def test_ons_latest_download_picks_newest_edition(monkeypatch):
    index = {"datasets": [{"uri": "/ds/yearendingdecember2025"}, {"uri": "/ds/yearendingjune2025"}]}
    edition = {"downloads": [{"file": "may2026publicationspreadsheet.xlsx"}]}

    def fake_get_json(url, *a, **k):
        return edition if "yearendingdecember2025" in url else index

    monkeypatch.setattr(_govuk, "get_json", fake_get_json)
    url, filename = _govuk.ons_latest_download("/ds")
    assert filename == "may2026publicationspreadsheet.xlsx"
    assert "uri=/ds/yearendingdecember2025/may2026publicationspreadsheet.xlsx" in url


def test_ons_latest_download_no_editions_raises(monkeypatch):
    monkeypatch.setattr(_govuk, "get_json", lambda url, *a, **k: {"datasets": []})
    with pytest.raises(LookupError):
        _govuk.ons_latest_download("/ds")
