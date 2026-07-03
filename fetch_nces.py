"""Fetch & parse the real US tuition series from the NCES Digest of Education Statistics.

Source (primary, U.S. Department of Education):
    NCES Digest 2023, Table 330.10 — "Average undergraduate tuition, fees, room, and
    board rates charged for full-time students ... 1963-64 through 2022-23".
    https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp

We extract **Public 4-year** "Tuition and required fees" (footnote 2: in-district tuition
is used for public institutions — i.e. the in-state/domestic figure) in BOTH current
dollars and constant 2022-23 dollars (CPI-adjusted by BLS, per the table's footnote 1).

The raw page is cached under ``data/raw/sources/`` so the parse is reproducible offline.
Output: ``data/raw/nces_tuition_public4yr.csv``.
"""

from __future__ import annotations

import csv
import io
import os
import re

import pandas as pd
import requests

from tuition import config

NCES_URL = "https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp"
CACHE_HTML = os.path.join(config.RAW_DIR, "sources", "nces_dt23_330.10.html")
OUT_CSV = os.path.join(config.RAW_DIR, "nces_tuition_public4yr.csv")

# Column offsets within Table 330.10 (0-based): "Tuition and required fees / 4-year".
_COL_CURRENT_4YR = 5      # current dollars
_COL_CONSTANT_4YR = 17    # constant 2022-23 dollars
# Row span of the "Public institutions" control section in the parsed table.
_PUBLIC_START, _PUBLIC_END = 57, 114


def _valid(html: str) -> bool:
    """True if the HTML actually contains the Table 330.10 data (not a bot-challenge)."""
    return "1963-64" in html and "2022-23" in html and "Tuition" in html


def _load_html() -> str:
    """Return the NCES table HTML, preferring a valid cached copy.

    NCES sits behind an F5 bot filter that can return a JS challenge instead of the
    table, so we (1) use a valid cache if present, else (2) download, and only cache a
    download that actually contains the table.
    """
    os.makedirs(os.path.dirname(CACHE_HTML), exist_ok=True)
    if os.path.exists(CACHE_HTML):
        with open(CACHE_HTML, encoding="utf-8", errors="replace") as fh:
            cached = fh.read()
        if _valid(cached):
            return cached
    resp = requests.get(NCES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    resp.raise_for_status()
    if not _valid(resp.text):
        raise RuntimeError(
            "NCES returned a bot-challenge page instead of the table; "
            f"place a saved copy of {NCES_URL} at {CACHE_HTML} and re-run."
        )
    with open(CACHE_HTML, "w", encoding="utf-8") as fh:
        fh.write(resp.text)
    return resp.text


def _num(x) -> float | None:
    s = str(x).replace("$", "").replace(",", "").replace("\xa0", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse(html: str) -> list[dict]:
    tables = pd.read_html(io.StringIO(html))
    data = next(t for t in tables if "1963-64" in t.to_string() and "2022-23" in t.to_string())
    public = data.iloc[_PUBLIC_START:_PUBLIC_END]
    rows: list[dict] = []
    for _, r in public.iterrows():
        acad = str(r.iloc[0]).strip()
        if not re.match(r"^\d{4}-\d{2}$", acad):
            continue
        current = _num(r.iloc[_COL_CURRENT_4YR])
        constant = _num(r.iloc[_COL_CONSTANT_4YR])
        if current is None or constant is None:
            continue
        rows.append({
            "year": int(acad[:4]),
            "academic_year": acad,
            "tuition_current_usd": current,
            "tuition_constant2022_usd": constant,
            "source": "NCES Digest 2023 Table 330.10 (Public 4-year, in-district)",
            "source_url": NCES_URL,
        })
    return rows


def main() -> None:
    rows = parse(_load_html())
    os.makedirs(config.RAW_DIR, exist_ok=True)
    fields = ["year", "academic_year", "tuition_current_usd",
              "tuition_constant2022_usd", "source", "source_url"]
    with open(OUT_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[nces] wrote {len(rows)} years ({rows[0]['academic_year']}..{rows[-1]['academic_year']}) -> {OUT_CSV}")


if __name__ == "__main__":
    main()
