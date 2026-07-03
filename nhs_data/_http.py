"""Shared HTTP helpers for nhs_data: a pooled session with polite retry/backoff.

Extends the JSON helper used by ``europe_data`` with byte/CSV download helpers,
because NHS England and Northern Ireland publish bulk CSV/Excel files rather than
offering a REST API.
"""

from __future__ import annotations

import io
from typing import Any
from urllib.parse import urlsplit

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "uk_decline/0.1 (UK NHS waiting-times research; contact: local use)"

# Downloads target only official UK health/government hosts. Restricting to these
# suffixes (and validating the post-redirect host) prevents a scraped/spoofed
# landing-page link or API nextLink from redirecting fetches to an arbitrary host.
ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (
    ".nhs.uk",
    ".nhs.scot",
    ".gov.wales",
    ".gov.uk",
    ".nomisweb.co.uk",  # ONS official data service (population estimates)
)

# Cap on a single download's size, guarding against a runaway/redirected body.
MAX_DOWNLOAD_BYTES = 1_073_741_824  # 1 GiB

_session: requests.Session | None = None


def _host_allowed(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def _ensure_allowed_host(url: str) -> None:
    if not _host_allowed(url):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


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
    _ensure_allowed_host(url)
    resp = session().get(
        url, params=params, timeout=timeout, headers={"Accept": "application/json"}
    )
    _ensure_allowed_host(resp.url)  # reject redirects to an untrusted host
    resp.raise_for_status()
    return resp.json()


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def get_bytes(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 120,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> bytes:
    """GET ``url`` and return the raw body (for CSV/Excel/ZIP downloads).

    Streams the response and aborts if it exceeds ``max_bytes`` so a huge or
    redirected body cannot exhaust memory. Only official UK health/gov hosts are
    permitted, before and after any redirect.
    """
    _ensure_allowed_host(url)
    with session().get(url, params=params, timeout=timeout, stream=True) as resp:
        _ensure_allowed_host(resp.url)
        resp.raise_for_status()
        buffer = io.BytesIO()
        total = 0
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(
                    f"download exceeded {max_bytes} bytes: {url!r}"
                )
            buffer.write(chunk)
        return buffer.getvalue()


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
