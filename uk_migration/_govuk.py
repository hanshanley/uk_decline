"""Resolve current download URLs from gov.uk and ONS publication pages.

Home Office statistics are published on gov.uk as dated attachments (e.g.
``asylum-claims-datasets-mar-2026.xlsx``) on a stable "statistical data set" page.
The filename changes every quarter, so we resolve the *current* attachment by matching
a stable filename **prefix** via the gov.uk content API, breaking any ties on the date
embedded in the filename (newest wins).

ONS publishes the Long-Term International Migration spreadsheet on ons.gov.uk. The dataset
page's ``/data`` JSON lists editions; each edition's ``/data`` lists the downloadable file,
served from ``/file?uri=<edition>/<file>``. We pick the newest edition by the date embedded
in its URI rather than trusting list order.
"""

from __future__ import annotations

import re

from ._http import get_json

GOVUK_CONTENT = "https://www.gov.uk/api/content"
ONS_BASE = "https://www.ons.gov.uk"

# The Home Office master "statistical data set" page carrying the detailed datasets.
IMMIGRATION_SYSTEM_STATISTICS = (
    "/government/statistical-data-sets/immigration-system-statistics-data-tables"
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# e.g. "...-mar-2026.xlsx"
_FILE_DATE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-(\d{4})")
# e.g. ".../yearendingdecember2025"
_EDITION_DATE = re.compile(
    r"yearending(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)(\d{4})"
)


def _date_key(text: str, pattern: re.Pattern) -> tuple[int, int]:
    """Sort key ``(year, month)`` from a date embedded in ``text`` (``(0, 0)`` if absent)."""
    match = pattern.search(text.lower())
    if not match:
        return (0, 0)
    return (int(match.group(2)), _MONTHS[match.group(1)[:3]])


def _attachments(base_path: str) -> list[dict]:
    payload = get_json(f"{GOVUK_CONTENT}{base_path}")
    return (payload.get("details", {}) or {}).get("attachments", []) or []


def govuk_attachment(prefix: str, base_path: str = IMMIGRATION_SYSTEM_STATISTICS) -> tuple[str, str]:
    """Return ``(file_url, filename)`` for the newest attachment whose name starts with ``prefix``.

    Raises ``LookupError`` if no attachment on the page matches.
    """
    matches: list[tuple[str, str]] = []
    for att in _attachments(base_path):
        url = att.get("file_url") or att.get("url") or ""
        filename = url.rsplit("/", 1)[-1]
        if filename.startswith(prefix):
            matches.append((url, filename))
    if not matches:
        raise LookupError(f"no attachment starting with {prefix!r} on {base_path}")
    url, filename = max(matches, key=lambda m: _date_key(m[1], _FILE_DATE))
    return url, filename


def ons_latest_download(dataset_path: str) -> tuple[str, str]:
    """Return ``(file_url, filename)`` for the newest edition of an ONS dataset.

    ``dataset_path`` is the ONS dataset page path (no host), e.g.
    ``/peoplepopulationandcommunity/.../longterminternational...provisional``.
    """
    index = get_json(f"{ONS_BASE}{dataset_path}/data")
    editions = index.get("datasets") or []
    if not editions:
        raise LookupError(f"no editions listed for ONS dataset {dataset_path}")
    newest = max(editions, key=lambda e: _date_key(e.get("uri", ""), _EDITION_DATE))
    edition_uri = newest["uri"]
    edition = get_json(f"{ONS_BASE}{edition_uri}/data")
    downloads = edition.get("downloads") or []
    if not downloads:
        raise LookupError(f"no downloads for ONS edition {edition_uri}")
    filename = downloads[0]["file"]
    file_uri = f"{edition_uri}/{filename}"
    return f"{ONS_BASE}/file?uri={file_uri}", filename
