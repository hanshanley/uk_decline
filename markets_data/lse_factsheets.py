"""Fetch LSE-classified UK and total company counts for Main Market plus AIM.

December observations start in 2018, after the Main Market factsheet adopted its
current equity-instrument coverage in May 2018. An explicitly requested later
month can supply the latest partial-year snapshot. This is a separate series,
not a continuation of World Bank/WFE listed domestic companies.
"""

from __future__ import annotations

import calendar
import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import openpyxl
import requests

DOCS_HOST = "docs.londonstockexchange.com"
BASE = f"https://{DOCS_HOST}/reports"
MARKETS = {"Main Market": "main-market", "AIM": "aim"}
SOURCE = "London Stock Exchange monthly factsheets (Main Market + AIM), primary-market summary"
DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "uk_listed_companies_lse.csv"
HISTORICAL_CSV = Path(__file__).with_name("lse_historical_snapshots.csv")
FIELDS = [
    "region", "year", "date", "metric", "value", "unit", "source",
    "source_url", "aim_source_url", "source_accessed",
]
_UA = {"User-Agent": "uk_decline/0.1 (UK listed-company counts research)"}


def _ensure_lse_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == DOCS_HOST or host.endswith(".londonstockexchange.com")):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


@lru_cache(maxsize=2)
def _factsheet_catalogue(market: str) -> dict[tuple[int, int], str]:
    """Read exact published links, including revised filenames, from LSE's catalogue."""
    sheets: dict[tuple[int, int], str] = {}
    pattern = re.compile(
        rf"{re.escape(market)} factsheet ([A-Za-z]+) (\d{{4}})(?:\.xlsx)?"
    )
    for edition in ("latest", "historic"):
        url = f"{BASE}/{MARKETS[market]}/{edition}.json"
        response = requests.get(url, headers=_UA, timeout=90)
        _ensure_lse_host(response.url)
        response.raise_for_status()
        for item in response.json()["Data"]:
            match = pattern.fullmatch(item["displayTitle"])
            if match is None or item.get("fileType", "").lower() != "xlsx":
                continue
            month, year = match.groups()
            month_number = list(calendar.month_name).index(month)
            link = item["downloadLink"]
            _ensure_lse_host(link)
            sheets.setdefault((int(year), month_number), link)
    if not sheets:
        raise ValueError(f"{market}: catalogue contains no monthly XLSX factsheets")
    return sheets


def _factsheet_url(market: str, year: int, month: str = "December") -> str:
    period = year, list(calendar.month_name).index(month)
    try:
        return _factsheet_catalogue(market)[period]
    except KeyError:
        raise ValueError(f"{market} {month} {year}: factsheet not published") from None


def _download(url: str, timeout: int = 90) -> io.BytesIO:
    _ensure_lse_host(url)
    resp = requests.get(url, headers=_UA, timeout=timeout)
    _ensure_lse_host(resp.url)
    resp.raise_for_status()
    return io.BytesIO(resp.content)


def _num(x) -> int | None:
    try:
        value = Decimal(str(x).replace(",", "").strip())
        if value.is_finite() and value >= 0 and value == value.to_integral_value():
            return int(value)
    except InvalidOperation:
        return None
    return None


def _counts(uk, international, total, context: str) -> tuple[int, int]:
    uk, international, total = _num(uk), _num(international), _num(total)
    if uk is None or international is None or total is None:
        raise ValueError(f"{context}: missing or invalid company counts")
    if uk + international != total:
        raise ValueError(f"{context}: UK and international counts do not match total")
    return uk, international


def _sheet_rows(market: str, year: int, month: str, sheet: str) -> list[tuple]:
    workbook = openpyxl.load_workbook(
        _download(_factsheet_url(market, year, month)), data_only=True, read_only=True,
    )
    try:
        rows = list(workbook[sheet].iter_rows(values_only=True))
    finally:
        workbook.close()
    expected = f"{month} {year}"
    if not any(str(cell).strip() == expected for row in rows[:8] for cell in row):
        raise ValueError(f"{market}: factsheet does not identify {expected}")
    return rows


def main_market_year(year: int, month: str = "December") -> tuple[int, int]:
    """Return ``(uk, international)`` counts for the requested month, or raise."""
    rows = _sheet_rows("Main Market", year, month, "Summary")
    for i, r in enumerate(rows):
        vals = [str(c) for c in r if c is not None]
        if "Year" in vals and "Number of Companies" in vals:
            for r2 in rows[i:i + 4]:
                c = list(r2)
                if len(c) > 5 and _num(c[1]) == year:
                    return _counts(c[2], c[3], c[5], f"Main Market {month} {year}")
    raise ValueError(f"Main Market {month} {year}: company-count row not found")


def aim_history(latest_year: int, month: str = "December") -> dict[int, tuple[int, int]]:
    """Return ``{year: (uk, international)}`` AIM counts from one factsheet's history sheet."""
    out: dict[int, tuple[int, int]] = {}
    rows = _sheet_rows("AIM", latest_year, month, "AIM since launch")
    header = next(
        (i for i, row in enumerate(rows) if "Year" in row and "Number of Companies" in row),
        None,
    )
    if header is None:
        raise ValueError(f"AIM {month} {latest_year}: company-count header not found")
    for r in rows[header + 1:]:
        c = list(r)
        if len(c) > 6 and re.fullmatch(r"\d{4}", str(c[1]).strip() if c[1] is not None else ""):
            yr = int(c[1])
            if yr in out:
                raise ValueError(f"AIM: duplicate company-count row for {yr}")
            out[yr] = _counts(c[2], c[4], c[6], f"AIM {yr}")
        elif out:
            break
    if latest_year not in out:
        raise ValueError(f"AIM {month} {latest_year}: company-count row not found")
    return out


def build_rows(
    start: int = 2018, end: int | None = None, latest_month: str | None = None,
) -> list[dict]:
    """Build complete annual observations and an optional later month (``YYYY-MM``)."""
    end = date.today().year - 1 if end is None else end
    if start < 2018 or start > end or end >= date.today().year:
        raise ValueError("LSE annual range must start in 2018 or later and end in a completed year")
    periods = [(year, 12) for year in range(start, end + 1)]
    if latest_month is not None:
        if not re.fullmatch(r"\d{4}-\d{2}", latest_month):
            raise ValueError("latest_month must use YYYY-MM")
        latest = date.fromisoformat(f"{latest_month}-01")
        month_end = date(latest.year, latest.month, calendar.monthrange(latest.year, latest.month)[1])
        if latest.year <= end or month_end >= date.today():
            raise ValueError("latest_month must be completed and later than the annual range")
        periods.append((latest.year, latest.month))
    latest_year, month_number = periods[-1]
    month = calendar.month_name[month_number]
    aim = aim_history(latest_year, month)
    aim_url = _factsheet_url("AIM", latest_year, month)
    rows: list[dict] = []
    for year, month_number in periods:
        month = calendar.month_name[month_number]
        # LSE omitted December 2022 when migrating its archive in October 2026.
        if (year, month_number) == (2022, 12) and (year, month_number) not in _factsheet_catalogue("Main Market"):
            with HISTORICAL_CSV.open(newline="") as handle:
                snapshots = list(csv.DictReader(handle))
            expected = {"lse_companies_uk", "lse_companies_total"}
            if len(snapshots) != 2 or {row["metric"] for row in snapshots} != expected:
                raise ValueError("LSE historical snapshot must contain both company counts")
            counts = {row["metric"]: _num(row["value"]) for row in snapshots}
            if (
                any(row["date"] != "2022-12-31" or row["year"] != "2022" for row in snapshots)
                or any(value is None for value in counts.values())
                or counts["lse_companies_uk"] > counts["lse_companies_total"]
            ):
                raise ValueError("LSE historical snapshot contains invalid dates or counts")
            rows.extend(
                {**row, "year": int(row["year"]), "value": counts[row["metric"]]}
                for row in snapshots
            )
            continue
        mm_uk, mm_intl = main_market_year(year, month)
        if year not in aim:
            raise ValueError(f"AIM {month} {year}: company-count row not found")
        aim_uk, aim_intl = aim[year]
        uk = mm_uk + aim_uk
        total = mm_uk + mm_intl + aim_uk + aim_intl
        for metric, value in (("lse_companies_uk", uk), ("lse_companies_total", total)):
            rows.append({
                "region": "United Kingdom",
                "year": year,
                "date": date(year, month_number, calendar.monthrange(year, month_number)[1]).isoformat(),
                "metric": metric,
                "value": value,
                "unit": "companies",
                "source": SOURCE,
                "source_url": _factsheet_url("Main Market", year, month),
                "aim_source_url": aim_url,
                "source_accessed": date.today().isoformat(),
            })
    rows.sort(key=lambda r: (r["metric"], r["year"]))
    return rows


def latest_available_month(end: int | None = None) -> str | None:
    """Find the latest completed month with both official market factsheets."""
    today = date.today()
    end = today.year - 2 if end is None else end
    common = _factsheet_catalogue("Main Market").keys() & _factsheet_catalogue("AIM").keys()
    completed = [
        (year, month) for year, month in common
        if year > end and date(year, month, calendar.monthrange(year, month)[1]) < today
    ]
    if not completed:
        raise ValueError("LSE catalogues contain no common completed month after the annual range")
    year, month = max(completed)
    return f"{year:04d}-{month:02d}"


def write_csv(
    path: Path | str = DEFAULT_CSV, start: int = 2018,
    end: int | None = None, latest_month: str | None = None,
) -> Path:
    """Fetch the LSE factsheets and write the tidy cited CSV. Returns the path."""
    rows = build_rows(start, end, latest_month)
    if not rows:
        raise RuntimeError("LSE returned no company counts; existing data was not replaced")
    path = Path(path)
    if path.exists():
        with path.open(newline="") as handle:
            previous = list(csv.DictReader(handle))
        if previous and max(row["date"] for row in rows) < max(row["date"] for row in previous):
            raise ValueError("LSE refresh would lose the latest published observation")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=2018)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--latest-month", help="optional later month-end snapshot, YYYY-MM")
    parser.add_argument("--latest", action="store_true", help="discover the latest available monthly factsheets")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--no-chart", action="store_true", help="write data only")
    args = parser.parse_args()
    if args.latest and args.latest_month:
        parser.error("--latest and --latest-month are mutually exclusive")
    if args.latest:
        args.latest_month = latest_available_month(args.end)
        if args.end is None and args.latest_month:
            year, month = map(int, args.latest_month.split("-"))
            args.end = year if month == 12 else year - 1
            if month == 12:
                args.latest_month = None
    out = write_csv(args.csv, args.start, args.end, args.latest_month)
    print(f"[lse_factsheets] wrote {out}")
    if not args.no_chart:
        from .charts import chart_lse_companies

        print(f"[lse_factsheets] wrote {chart_lse_companies(out)}")
