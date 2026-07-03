"""Shared HTTP helper: a pooled requests session with polite retry/backoff."""

from __future__ import annotations

from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "uk_decline-tuition/0.1 (UK vs EU vs US degree-cost comparison; local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session = s
    return _session


def _is_transient(exc: BaseException) -> bool:
    """Retry only transient failures: connection/timeout, HTTP 429, and 5xx."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient network/HTTP errors."""
    resp = session().get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
