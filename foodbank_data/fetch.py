"""Download the official Trussell workbooks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from .sources import CALENDAR_SOURCE, END_YEAR_PAGE, RAW_DIR, SOURCES, Source

GetBytes = Callable[[str], bytes]
_ALLOWED_HOSTS = {
    "cms.trussell.org.uk",
    "hub.foodbank.org.uk",
    "trusselltrustprod.prod.acquia-sites.com",
    "www.trussell.org.uk",
    "trussell.org.uk",
}
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def _check_host(url: str) -> None:
    if (urlsplit(url).hostname or "").lower() not in _ALLOWED_HOSTS:
        raise ValueError(f"refusing to fetch an untrusted host: {url}")


def http_get(url: str, timeout: int = 60) -> bytes:
    _check_host(url)
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "uk_decline food-bank analysis/1.0"},
    )
    _check_host(response.url)
    response.raise_for_status()
    payload = response.content
    if len(payload) > _MAX_DOWNLOAD_BYTES:
        raise ValueError(f"download exceeded {_MAX_DOWNLOAD_BYTES} bytes: {url}")
    return payload


def download(
    source: Source,
    raw_dir: Path = RAW_DIR,
    *,
    get_bytes: GetBytes = http_get,
) -> Path:
    """Download one XLSX atomically; ``get_bytes`` keeps tests offline."""
    destination = source.path(Path(raw_dir))
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = get_bytes(source.url)
    if not payload.startswith(b"PK"):
        raise ValueError(f"{source.url} did not return an XLSX file")
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.write_bytes(payload)
    partial.replace(destination)
    return destination


def discover_calendar_source(*, get_bytes: GetBytes = http_get) -> Source:
    """Use the official release page rather than a year-pinned workbook URL."""
    page = BeautifulSoup(get_bytes(END_YEAR_PAGE), "html.parser")
    candidates = set()
    for link in page.select("a[href]"):
        url = urljoin(END_YEAR_PAGE, link["href"])
        match = re.search(r"eys[_-](20\d{2}).*parcel.*\.xlsx$", urlsplit(url).path, re.I)
        if match:
            _check_host(url)
            candidates.add((int(match[1]), url))
    if not candidates:
        raise ValueError("Trussell release page has no calendar-year parcel workbook")
    year = max(year for year, _ in candidates)
    urls = {url for edition, url in candidates if edition == year}
    if len(urls) != 1 or year < 2025:
        raise ValueError("Trussell parcel workbook is ambiguous or predates calendar-year reporting")
    return Source(
        key="calendar", url=urls.pop(),
        filename=CALENDAR_SOURCE.filename if year == 2025 else f"food_bank_trussell_eys_{year}.xlsx",
        description=f"Trussell {year} end-of-year parcel statistics",
    )


def refresh(
    raw_dir: Path = RAW_DIR, *, get_bytes: GetBytes = http_get,
    calendar_source: Source = CALENDAR_SOURCE,
) -> list[Path]:
    return [
        download(calendar_source if source.key == "calendar" else source, raw_dir, get_bytes=get_bytes)
        for source in SOURCES
    ]


def ensure_sources(raw_dir: Path = RAW_DIR, *, calendar_source: Source = CALENDAR_SOURCE) -> list[Path]:
    sources = [calendar_source if source.key == "calendar" else source for source in SOURCES]
    paths = [source.path(Path(raw_dir)) for source in sources]
    missing = [source for source, path in zip(sources, paths) if not path.exists()]
    for source in missing:
        download(source, raw_dir)
    return paths
