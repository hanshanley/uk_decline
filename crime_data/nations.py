"""Comparable homicide rates across UK jurisdictions from 2000 onward.

Homicide is used because broad police-recorded crime categories and victimisation surveys
are not harmonised across the UK nations. England and Wales are reported jointly by ONS;
Scotland and Northern Ireland publish separate official series.
"""

from __future__ import annotations

import io
import re
import time
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import csew

METRIC = "homicide_rate_per_million"
UNIT = "per million population"

ENGLAND_WALES = "England & Wales"
SCOTLAND = "Scotland"
NORTHERN_IRELAND = "Northern Ireland"

ONS_HOMICIDE_PATH = (
    "/peoplepopulationandcommunity/crimeandjustice/datasets/"
    "appendixtableshomicideinenglandandwales"
)
ONS_POPULATION_PATH = (
    "/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets/"
    "populationestimatesforukenglandandwalesscotlandandnorthernireland"
)
SCOTLAND_DOCUMENTS_URL = (
    "https://www.gov.scot/publications/homicide-scotland-2024-25/documents/"
)
PSNI_REPORT_URL = (
    "https://www.psni.police.uk/system/files/2025-11/744575614/"
    "Police%20Recorded%20Crime%20in%20Northern%20Ireland%201998-99%20to%202024-25.pdf"
)

_UA = {"User-Agent": "uk_decline/0.1 (crime statistics research)"}
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _ensure_host(url: str, allowed: tuple[str, ...]) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not any(host == domain or host.endswith(f".{domain}") for domain in allowed):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def _get(url: str, allowed: tuple[str, ...], timeout: int = 120) -> requests.Response:
    for _ in range(6):
        _ensure_host(url, allowed)
        response = requests.get(
            url, headers=_UA, timeout=timeout, allow_redirects=False
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                break
            url = urljoin(url, location)
            continue
        response.raise_for_status()
        return response
    raise ValueError(f"too many redirects while fetching {url!r}")


def _ons_download(landing_path: str, version_pattern: str | None = None) -> bytes:
    landing = csew._get_json(landing_path)
    versions = [entry["uri"] for entry in landing["datasets"]]
    if version_pattern is None:
        version_uri = versions[0]
    else:
        version_uri = next(uri for uri in versions if re.search(version_pattern, uri))
    version = csew._get_json(version_uri)
    filename = version["downloads"][0]["file"]
    url = f"{csew.ONS_BASE}/file?uri={version_uri}/{filename}"
    for attempt in range(4):
        try:
            return csew._ons_get(url, timeout=120).content
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status != 429 or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def _scotland_download() -> bytes:
    page = _get(SCOTLAND_DOCUMENTS_URL, ("gov.scot",))
    soup = BeautifulSoup(page.text, "html.parser")
    href = next(
        (
            link.get("href")
            for link in soup.find_all("a")
            if link.get("href")
            and ".xlsx" in link.get("href", "").lower()
            and "homicide" in link.get("href", "").lower()
        ),
        None,
    )
    if href is None:
        raise ValueError("Scottish homicide data workbook link not found")
    return _get(urljoin(SCOTLAND_DOCUMENTS_URL, href), ("gov.scot",)).content


def _period_end_year(value) -> int | None:
    years = _YEAR_RE.findall(str(value))
    return int(years[-1]) if years else None


def _extract_england_wales_rates(workbook: bytes) -> dict[int, float]:
    frame = pd.read_excel(io.BytesIO(workbook), sheet_name="Table 1", header=None)
    header = next(
        i for i in range(frame.shape[0]) if str(frame.iloc[i, 0]).strip() == "Year"
    )
    rates: dict[int, float] = {}
    for _, row in frame.iloc[header + 1:].iterrows():
        year = _period_end_year(row.iloc[0])
        rate = pd.to_numeric(row.iloc[4], errors="coerce")
        if year is not None and pd.notna(rate):
            rates[year] = float(rate)
    return rates


def _extract_scotland_counts(workbook: bytes) -> dict[int, int]:
    frame = pd.read_excel(io.BytesIO(workbook), sheet_name="Historical Data", header=None)
    header = next(
        i for i in range(frame.shape[0]) if str(frame.iloc[i, 0]).strip() == "Year"
    )
    counts: dict[int, int] = {}
    for _, row in frame.iloc[header + 1:].iterrows():
        year = _period_end_year(row.iloc[0])
        victims = pd.to_numeric(row.iloc[2], errors="coerce")
        if year is not None and pd.notna(victims):
            counts[year] = int(victims)
    return counts


def _extract_population(workbook: bytes, sheet_name: str) -> dict[int, int]:
    frame = pd.read_excel(io.BytesIO(workbook), sheet_name=sheet_name, header=None)
    header = next(
        i for i in range(frame.shape[0]) if str(frame.iloc[i, 0]).strip() == "Year"
    )
    populations: dict[int, int] = {}
    for _, row in frame.iloc[header + 1:].iterrows():
        year = _period_end_year(row.iloc[0])
        population = pd.to_numeric(row.iloc[1], errors="coerce")
        if year is not None and pd.notna(population):
            populations[year] = int(population)
    return populations


def _extract_psni_counts(report: bytes) -> dict[int, int]:
    """Recover the exact integer series from the bars in PSNI's official PDF chart."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency error is environment-specific
        raise RuntimeError("PyMuPDF is required to parse the PSNI homicide chart") from exc

    document = fitz.open(stream=report, filetype="pdf")
    page = next(
        (
            candidate
            for candidate in document
            if "Homicides by calendar year" in candidate.get_text()
        ),
        None,
    )
    if page is None:
        raise ValueError("PSNI homicide chart not found")

    year_match = re.search(
        r"Homicides by calendar year,\s*((?:19|20)\d{2})\s+to\s+((?:19|20)\d{2})",
        page.get_text(),
    )
    if year_match is None:
        raise ValueError("PSNI homicide chart year range not found")
    first_year, last_year = map(int, year_match.groups())

    chart_bars = None
    for drawing in page.get_drawings():
        candidates: list[tuple[float, float, float | None]] = []
        for item in drawing["items"]:
            if item[0] == "re":
                rect = item[1]
                if 2 < rect.width < 5 and rect.height > 0.5:
                    candidates.append((rect.x0 + rect.width / 2, rect.y0, rect.y1))
            elif item[0] == "l":
                start, end = item[1], item[2]
                if abs(start.y - end.y) < 0.1 and 2 < abs(start.x - end.x) < 5:
                    candidates.append(((start.x + end.x) / 2, start.y, None))
        if len(candidates) >= last_year - first_year + 1:
            chart_bars = candidates
            break
    if chart_bars is None:
        raise ValueError("PSNI homicide chart bars not found")

    baseline = max(bottom for _, _, bottom in chart_bars if bottom is not None)
    tops = [
        item for item in chart_bars
        if item[2] is not None or item[1] < baseline - 0.5
    ]
    by_x = {round(x, 1): (x, top) for x, top, _ in tops}
    bars = sorted(by_x.values())
    expected = last_year - first_year + 1
    if len(bars) != expected:
        raise ValueError(f"expected {expected} PSNI homicide bars, found {len(bars)}")

    x_min, x_max = bars[0][0], bars[-1][0]
    grid_lines: list[float] = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            start, end = item[1], item[2]
            if (
                abs(start.y - end.y) < 0.1
                and min(start.x, end.x) <= x_min
                and max(start.x, end.x) >= x_max
                and start.y <= baseline
            ):
                grid_lines.append(start.y)
    if not grid_lines:
        raise ValueError("PSNI homicide chart grid not found")
    chart_top = min(grid_lines)

    axis_values = [
        int(word[4])
        for word in page.get_text("words")
        if word[0] < x_min
        and chart_top - 10 <= word[1] <= baseline + 10
        and re.fullmatch(r"\d+", word[4])
        and int(word[4]) <= 1_000
    ]
    if not axis_values:
        raise ValueError("PSNI homicide chart axis not found")
    axis_max = max(axis_values)
    points_per_homicide = (baseline - chart_top) / axis_max

    return {
        year: round((baseline - top) / points_per_homicide)
        for year, (_, top) in zip(range(first_year, last_year + 1), bars)
    }


def _assemble_rows(
    england_wales_rates: dict[int, float],
    scotland_counts: dict[int, int],
    northern_ireland_counts: dict[int, int],
    scotland_population: dict[int, int],
    northern_ireland_population: dict[int, int],
    start: int,
) -> list[dict]:
    rows: list[dict] = []
    sources = {
        ENGLAND_WALES: "ONS Homicide Index",
        SCOTLAND: "Scottish Government, Homicide in Scotland; ONS population estimates",
        NORTHERN_IRELAND: (
            "Police Service of Northern Ireland; ONS population estimates"
        ),
    }

    for year, rate in england_wales_rates.items():
        if year >= start:
            rows.append({
                "jurisdiction": ENGLAND_WALES,
                "year": year,
                "metric": METRIC,
                "value": round(rate, 3),
                "unit": UNIT,
                "source": sources[ENGLAND_WALES],
            })

    for jurisdiction, counts, populations in (
        (SCOTLAND, scotland_counts, scotland_population),
        (NORTHERN_IRELAND, northern_ireland_counts, northern_ireland_population),
    ):
        for year, count in counts.items():
            population = populations.get(year)
            if year >= start and population:
                rows.append({
                    "jurisdiction": jurisdiction,
                    "year": year,
                    "metric": METRIC,
                    "value": round(count / population * 1_000_000, 3),
                    "unit": UNIT,
                    "source": sources[jurisdiction],
                })

    rows.sort(key=lambda row: (row["jurisdiction"], row["year"]))
    return rows


def build_rows(start: int = 2000) -> list[dict]:
    """Fetch official series and return UK-jurisdiction homicide rates from ``start``."""
    england_wales_workbook = _ons_download(ONS_HOMICIDE_PATH)
    population_workbook = _ons_download(
        ONS_POPULATION_PATH, r"/ukpopulationestimates\d+to\d+$"
    )
    scotland_workbook = _scotland_download()
    psni_report = _get(PSNI_REPORT_URL, ("psni.police.uk",)).content

    return _assemble_rows(
        _extract_england_wales_rates(england_wales_workbook),
        _extract_scotland_counts(scotland_workbook),
        _extract_psni_counts(psni_report),
        _extract_population(population_workbook, "Table 14"),
        _extract_population(population_workbook, "Table 17"),
        start,
    )
