"""Download the official Trussell workbooks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .sources import RAW_DIR, SOURCES, Source

GetBytes = Callable[[str], bytes]
_ALLOWED_HOSTS = {
    "cms.trussell.org.uk",
    "hub.foodbank.org.uk",
    "trusselltrustprod.prod.acquia-sites.com",
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


def refresh(raw_dir: Path = RAW_DIR, *, get_bytes: GetBytes = http_get) -> list[Path]:
    return [download(source, raw_dir, get_bytes=get_bytes) for source in SOURCES]


def ensure_sources(raw_dir: Path = RAW_DIR) -> list[Path]:
    paths = [source.path(Path(raw_dir)) for source in SOURCES]
    missing = [source for source, path in zip(SOURCES, paths) if not path.exists()]
    for source in missing:
        download(source, raw_dir)
    return paths
