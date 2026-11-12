"""Use central JSON retries/revalidation, retaining tuition's transient-only rule."""

from __future__ import annotations

from typing import Any

import requests
from europe_data._http import get_json as _get_json
from europe_data._http import session


def _is_transient(exc: BaseException) -> bool:
    """Retry only transient failures: connection/timeout, HTTP 429, and 5xx."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient network/HTTP errors."""
    return _get_json(url, params=params, timeout=timeout, retry_on=_is_transient)
