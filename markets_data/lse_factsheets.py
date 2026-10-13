"""Fetch LSE-classified UK and total company counts for Main Market plus AIM.

December observations start in 2018, after the Main Market factsheet adopted its
current equity-instrument coverage in May 2018. An explicitly requested later
month can supply the latest partial-year snapshot. This is a separate series,
not a continuation of World Bank/WFE listed domestic companies.
"""

from __future__ import annotations

import calendar
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import openpyxl
import requests

DOCS_HOST = "docs.londonstockexchange.com"
BASE = f"https://{DOCS_HOST}/sites/default/files/reports"
SOURCE = "London Stock Exchange monthly factsheets (Main Market + AIM), primary-market summary"
DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "uk_listed_companies_lse.csv"
FIELDS = [
    "region", "year", "date", "metric", "value", "unit", "source",
    "source_url", "aim_source_url", "source_accessed",
]
_UA = {"User-Agent": "uk_decline/0.1 (UK listed-company counts research)"}


def _ensure_lse_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == DOCS_HOST or host.endswith(".londonstockexchange.com")):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def _factsheet_url(market: str, year: int, month: str = "December") -> str:
    # market is "Main Market" or "AIM"; spaces are URL-encoded by requests' params-free path.
    name = f"{market} factsheet {month} {year}.xlsx".replace(" ", "%20")
    return f"{BASE}/{name}"


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


def write_csv(
    path: Path | str = DEFAULT_CSV, start: int = 2018,
    end: int | None = None, latest_month: str | None = None,
) -> Path:
    """Fetch the LSE factsheets and write the tidy cited CSV. Returns the path."""
    import csv
    rows = build_rows(start, end, latest_month)
    if not rows:
        raise RuntimeError("LSE returned no company counts; existing data was not replaced")
    path = Path(path)
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
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--no-chart", action="store_true", help="write data only")
    args = parser.parse_args()
    out = write_csv(args.csv, args.start, args.end, args.latest_month)
    print(f"[lse_factsheets] wrote {out}")
    if not args.no_chart:
        from .charts import chart_lse_companies

        print(f"[lse_factsheets] wrote {chart_lse_companies(out)}")
