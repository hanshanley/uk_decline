"""Recover failing bulk World Bank queries without publishing partial pages."""

from __future__ import annotations

import requests

from ._http import get_json

BASE = "https://api.worldbank.org/v2"
MAX_PAGES = 50


def _transient(error: requests.RequestException) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    return (
        isinstance(error, requests.HTTPError) and error.response is not None
        and (error.response.status_code == 429 or error.response.status_code >= 500)
    )


def _pages(
    indicator: str, codes: list[str], start: int, end: int,
    source: int | None, download, attempts: int,
) -> list[dict]:
    rows = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "format": "json", "per_page": 1000,
            "date": f"{start}:{end}", "page": page,
        }
        if source is not None:
            params["source"] = source
        payload = download(
            f"{BASE}/country/{';'.join(codes)}/indicator/{indicator}",
            params=params, attempts=attempts,
        )
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[0], dict):
            raise ValueError(f"Malformed World Bank response for {indicator}, page {page}")
        meta, observations = payload[:2]
        pages = int(meta.get("pages", 1))
        if page == 1 and (observations is None or observations == []) and pages in (0, 1):
            return []
        if not 1 <= pages <= MAX_PAGES:
            raise ValueError(f"Invalid World Bank page count for {indicator}: {pages}")
        if not isinstance(observations, list) or (not observations and pages > 1):
            raise ValueError(f"Missing World Bank observations for {indicator}, page {page}")
        rows.extend(observations)
        if page >= pages:
            return rows
    raise ValueError(f"World Bank pagination did not terminate for {indicator}")


def observations(
    indicator: str, codes: list[str], start: int, end: int, *,
    source: int | None = None, download=get_json,
) -> list[dict]:
    """Fetch complete pages; split transiently failing country/year ranges."""
    if start > end:
        raise ValueError("World Bank start year must not exceed end year")
    if not codes:
        return []
    splittable = len(codes) > 1 or start < end
    try:
        # Split slow bulk queries promptly; retain five retries for indivisible queries.
        return _pages(indicator, codes, start, end, source, download, 1 if splittable else 5)
    except requests.RequestException as error:
        if not splittable or not _transient(error):
            raise
        print(
            f"[worldbank] splitting {indicator} for {';'.join(codes)} "
            f"{start}-{end} after {type(error).__name__}",
            flush=True,
        )
    if len(codes) > 1:
        middle = len(codes) // 2
        return observations(
            indicator, codes[:middle], start, end, source=source, download=download,
        ) + observations(
            indicator, codes[middle:], start, end, source=source, download=download,
        )
    middle = (start + end) // 2
    return observations(
        indicator, codes, start, middle, source=source, download=download,
    ) + observations(
        indicator, codes, middle + 1, end, source=source, download=download,
    )
