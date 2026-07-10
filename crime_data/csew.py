"""Fetch and reshape the ONS Crime Survey for England & Wales (CSEW) long-run trend.

Source: Office for National Statistics, *Crime in England and Wales: Appendix Tables*,
sheet **``Table_A1a``** — "Trends in incidents of CSEW headline crime … year ending
December 1981 to <latest>", offence groups (rows) x survey periods (columns), values in
**1,000s of incidents**.

The CSEW (formerly the British Crime Survey) is the ONS-preferred measure of long-run crime
*trends*, because it is unaffected by changes in police recording practice. It covers
**England & Wales only** (Scotland and Northern Ireland run their own surveys).

Two headline totals are published and both are emitted here:
  * ``ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE`` — the comparable
    long-run spine (available from 1981); this is the series that shows the large fall.
  * ``ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE`` — available only from
    the year ending March 2017, when fraud & computer misuse were added.

We resolve the current download URL from the ONS dataset page at run time (the filename
changes each release), restricted to the ``ons.gov.uk`` host.
"""

from __future__ import annotations

import datetime as dt
import io
import re
from urllib.parse import urlsplit

import pandas as pd
import requests

ONS_BASE = "https://www.ons.gov.uk"
DATASET_PATH = (
    "/peoplepopulationandcommunity/crimeandjustice/datasets/"
    "crimeinenglandandwalesappendixtables"
)
SHEET = "Table_A1a"
REGION = "England and Wales"
METRIC = "csew_incidents_1000s"
UNIT = "incidents (thousands)"
SOURCE = "Crime Survey for England and Wales, Office for National Statistics (ONS)"

_UA = {"User-Agent": "uk_decline/0.1 (crime statistics research)"}

# "Unweighted base ..." rows are sample sizes, not crime counts — never emit them.
_SKIP_PREFIX = "unweighted base"

_MONTH_END = {
    "Jan": (1, 31), "Feb": (2, 28), "Mar": (3, 31), "Apr": (4, 30),
    "May": (5, 31), "Jun": (6, 30), "Jul": (7, 31), "Aug": (8, 31),
    "Sep": (9, 30), "Oct": (10, 31), "Nov": (11, 30), "Dec": (12, 31),
}


def _ensure_ons_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == "ons.gov.uk" or host.endswith(".ons.gov.uk")):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def _ons_get(url: str, timeout: int, max_redirects: int = 5) -> requests.Response:
    """GET ``url`` with the ONS host-allowlist enforced on the initial URL *and every
    redirect hop*, so a redirect can never send a live request to an off-allowlist host."""
    for _ in range(max_redirects + 1):
        _ensure_ons_host(url)
        resp = requests.get(url, headers=_UA, timeout=timeout, allow_redirects=False)
        if resp.is_redirect or resp.is_permanent_redirect:
            nxt = resp.headers.get("Location")
            if not nxt:
                break
            url = requests.compat.urljoin(url, nxt)
            continue
        resp.raise_for_status()
        return resp
    raise ValueError(f"too many redirects while fetching {url!r}")


def _get_json(path: str, timeout: int = 60) -> dict:
    return _ons_get(f"{ONS_BASE}{path}/data", timeout).json()


def resolve_download_url() -> str:
    """Resolve the current Appendix-Tables xlsx download URL from the ONS dataset page."""
    landing = _get_json(DATASET_PATH)
    version_uri = landing["datasets"][0]["uri"]  # e.g. ".../current"
    version = _get_json(version_uri)
    filename = version["downloads"][0]["file"]
    return f"{ONS_BASE}/file?uri={version_uri}/{filename}"


def download_workbook(url: str | None = None, timeout: int = 120) -> pd.DataFrame:
    """Download the Appendix-Tables workbook and return the ``Table_A1a`` sheet (header-less)."""
    url = url or resolve_download_url()
    resp = _ons_get(url, timeout)
    return pd.read_excel(io.BytesIO(resp.content), sheet_name=SHEET, header=None)


def _clean_label(text: str) -> str:
    """Trim indentation, collapse whitespace/newlines, and drop ``[note N]`` markers."""
    text = re.sub(r"\[notes?[^\]]*\]", "", str(text), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _indent_level(raw: str) -> int:
    """Hierarchy depth from the leading spaces ONS uses to indent sub-categories."""
    return (len(raw) - len(raw.lstrip(" "))) // 4


def _parse_period(label: str) -> tuple[str, int, str] | None:
    """('Apr 2001 to Mar 2002') -> (clean_label, end_year, iso_date_of_period_end)."""
    clean = _clean_label(label)
    m = re.search(r"to\s+([A-Z][a-z]{2})\s+(\d{4})", clean)
    if not m:
        return None
    month, year = m.group(1), int(m.group(2))
    if month not in _MONTH_END:
        return None
    mo, day = _MONTH_END[month]
    return clean, year, dt.date(year, mo, day).isoformat()


def _to_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None  # ONS shorthand like "[x]" (not available) / blank
    return f if f == f else None  # drop NaN


def _find_header_row(df: pd.DataFrame) -> int:
    for i in range(min(15, df.shape[0])):
        if "offence group" in str(df.iloc[i, 0]).lower():
            return i
    raise ValueError("could not find the 'Offence group' header row in Table_A1a")


def build_rows(df: pd.DataFrame | None = None) -> list[dict]:
    """Return tidy rows: one per (offence_group, period) with a non-missing value."""
    if df is None:
        df = download_workbook()

    header = _find_header_row(df)
    # period columns: (col_index -> (period_label, end_year, iso_date))
    periods: dict[int, tuple[str, int, str]] = {}
    for j in range(1, df.shape[1]):
        parsed = _parse_period(df.iloc[header, j])
        if parsed is not None:
            periods[j] = parsed

    rows: list[dict] = []
    for i in range(header + 1, df.shape[0]):
        raw = df.iloc[i, 0]
        if raw is None or str(raw).strip() == "" or str(raw).strip().lower() == "nan":
            continue
        raw = str(raw)
        name = _clean_label(raw)
        if name.lower().startswith(_SKIP_PREFIX):
            continue
        level = _indent_level(raw)
        for j, (period, year, iso_date) in periods.items():
            value = _to_float(df.iloc[i, j])
            if value is None:
                continue
            rows.append({
                "region": REGION,
                "offence_group": name,
                "level": level,
                "period": period,
                "date": iso_date,
                "year": year,
                "metric": METRIC,
                "value": round(value, 3),
                "unit": UNIT,
                "source": SOURCE,
            })
    rows.sort(key=lambda r: (r["offence_group"], r["date"]))
    return rows
