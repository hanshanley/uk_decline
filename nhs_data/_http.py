"""Shared HTTP helpers for nhs_data: a pooled session with polite retry/backoff.

Extends the JSON helper used by ``europe_data`` with byte/CSV download helpers,
because NHS England and Northern Ireland publish bulk CSV/Excel files rather than
offering a REST API.
"""

from __future__ import annotations

import io
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "uk_decline/0.1 (UK NHS waiting-times research; contact: local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        _session = s
    return _session


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    """GET ``url`` and return parsed JSON, retrying transient network/HTTP errors."""
    resp = session().get(
        url, params=params, timeout=timeout, headers={"Accept": "application/json"}
    )
    resp.raise_for_status()
    return resp.json()


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_bytes(url: str, params: dict[str, Any] | None = None, timeout: int = 120) -> bytes:
    """GET ``url`` and return the raw response body (for CSV/Excel downloads)."""
    resp = session().get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def get_csv(url: str, params: dict[str, Any] | None = None, timeout: int = 120, **read_csv_kwargs: Any):
    """GET ``url`` and parse the body as CSV into a pandas DataFrame."""
    import pandas as pd

    content = get_bytes(url, params=params, timeout=timeout)
    return pd.read_csv(io.BytesIO(content), **read_csv_kwargs)


def get_excel(url: str, params: dict[str, Any] | None = None, timeout: int = 120, **read_excel_kwargs: Any):
    """GET ``url`` and parse the body as an Excel workbook into pandas.

    Returns whatever ``pandas.read_excel`` returns (a DataFrame, or a dict of
    ``{sheet_name: DataFrame}`` when ``sheet_name=None``).
    """
    import pandas as pd

    content = get_bytes(url, params=params, timeout=timeout)
    return pd.read_excel(io.BytesIO(content), **read_excel_kwargs)
