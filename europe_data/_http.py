"""Shared HTTP helpers: a pooled requests session with polite retry/backoff."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlsplit

import requests
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "uk_decline/0.1 (europe per-capita GDP & median income; contact: local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _session = s
    return _session


def transient_error(error: BaseException) -> bool:
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status = error.response.status_code
        return status in (408, 429) or 500 <= status < 600
    return isinstance(error, requests.RequestException)


def _retry_delay(state, backoff) -> float:
    delay = float(backoff(state))
    error = state.outcome.exception()
    response = getattr(error, "response", None)
    if response is not None and response.status_code in (429, 503):
        value = response.headers.get("Retry-After")
        if isinstance(value, str):
            try:
                try:
                    seconds = float(value)
                except ValueError:
                    seconds = (
                        parsedate_to_datetime(value) - datetime.now(timezone.utc)
                    ).total_seconds()
                delay = max(delay, min(60, max(0, seconds)))
            except (TypeError, ValueError, OverflowError):
                pass
    return delay


def request_get(
    url: str, params: dict[str, Any] | None = None, timeout: int = 60, *,
    attempts: int = 5,
    retry_on: Callable[[BaseException], bool] | None = None,
    headers: dict[str, str] | None = None,
    client=None,
    read: Callable[[requests.Response], Any] | None = None,
    validate_url: Callable[[str], None] | None = None,
    before_request: Callable[[str], None] | None = None,
    **options,
) -> Any:
    """Bound retries around the entire GET/read; preserve caller guards and options."""
    if not 1 <= attempts <= 5:
        raise ValueError("HTTP requests must use between one and five attempts")
    backoff = wait_exponential(multiplier=1, min=1, max=30)
    for attempt in Retrying(
        retry=retry_if_exception(retry_on if retry_on is not None else transient_error),
        stop=stop_after_attempt(attempts),
        wait=lambda state: _retry_delay(state, backoff),
        reraise=True,
    ):
        with attempt:
            if validate_url is not None:
                validate_url(url)
            if before_request is not None:
                before_request(url)
            revalidate = (
                urlsplit(url).hostname == "api.worldbank.org"
                or attempt.retry_state.attempt_number > 1
            )
            request_headers = dict(headers or {})
            if revalidate:
                request_headers["Cache-Control"] = "no-cache"
            request_options = dict(options)
            if request_headers:
                request_options["headers"] = request_headers
            resp = (session() if client is None else client).get(
                url, params=params, timeout=timeout, **request_options,
            )
            returned = False
            try:
                if validate_url is not None:
                    validate_url(resp.url)
                resp.raise_for_status()
                result = resp if read is None else read(resp)
                returned = read is None
                return result
            finally:
                if not returned and callable(getattr(resp, "close", None)):
                    resp.close()


def get_json(
    url: str, params: dict[str, Any] | None = None, timeout: int = 60, *,
    attempts: int = 5, retry_on: Callable[[BaseException], bool] | None = None,
    **options,
) -> Any:
    return request_get(
        url, params=params, timeout=timeout, attempts=attempts, retry_on=retry_on,
        read=lambda response: response.json(), **options,
    )


def get_text(
    url: str, params: dict[str, Any] | None = None, timeout: int = 60,
    *, headers: dict[str, str] | None = None, **options,
) -> str:
    """GET ``url`` and return the response body as text (e.g. a CSV download)."""
    return request_get(
        url, params=params, timeout=timeout, headers={"Accept": "*/*", **(headers or {})},
        read=lambda response: response.text, **options,
    )


def get_bytes(url: str, timeout: int = 60, **options) -> bytes:
    """Download a binary source workbook with the shared retry policy."""
    headers = {"Accept": "*/*", **(options.pop("headers", None) or {})}
    return request_get(
        url, timeout=timeout, headers=headers, read=lambda response: response.content, **options,
    )
