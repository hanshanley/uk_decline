"""Shared HTTP helpers: a pooled requests session with polite retry/backoff."""

from __future__ import annotations

from typing import Any

import requests
from europe_data._http import get_json as _get_json

USER_AGENT = "uk_decline/0.1 (UK vs US stock-market size; contact: local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session = s
    return _session


def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient network/HTTP errors."""
    return _get_json(url, params=params, timeout=timeout, client=session())
