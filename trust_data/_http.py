"""Shared HTTP helpers: a pooled requests session with polite retry/backoff.

Mirrors ``europe_data/_http.py`` but also exposes ``get_text`` for the OECD SDMX endpoint,
which occasionally needs an explicit ``Accept`` header and returns non-JSON error bodies.
"""

from __future__ import annotations

from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "uk_decline/0.1 (trust in UK government over time; contact: local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session = s
    return _session


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient network/HTTP errors."""
    resp = session().get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_text(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> str:
    """GET ``url`` and return the raw response text, retrying transient errors."""
    resp = session().get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text
