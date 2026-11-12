"""Keep offline tests independent of external source availability."""

from urllib.parse import urlsplit

import pytest
from requests.adapters import HTTPAdapter


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    send = HTTPAdapter.send

    def offline_send(self, request, *args, **kwargs):
        if urlsplit(request.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise AssertionError(f"Offline test attempted external HTTP: {request.url}")
        return send(self, request, *args, **kwargs)

    monkeypatch.setattr(HTTPAdapter, "send", offline_send)
