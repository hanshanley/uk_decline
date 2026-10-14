"""Fetch & parse the real US tuition series from the NCES Digest of Education Statistics.

Source (primary, U.S. Department of Education):
    NCES Digest 2024, Table 330.10 — "Average undergraduate tuition, fees, room, and
    board rates charged for full-time students ... 1963-64 through 2023-24".
    https://nces.ed.gov/programs/digest/d24/tables/dt24_330.10.asp

We extract **Public 4-year** "Tuition and required fees" (footnote 2: in-district tuition
is used for public institutions — i.e. the in-state/domestic figure) in BOTH current
dollars and constant 2023-24 dollars (CPI-adjusted by BLS, per the table's footnote 1).

The raw page is cached under ``data/raw/sources/`` so the parse is reproducible offline.
Output: ``data/raw/nces_tuition_public4yr.csv``.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import os
import re

import pandas as pd
import requests

from tuition import config

NCES_URL = "https://nces.ed.gov/programs/digest/d24/tables/dt24_330.10.asp"
CACHE_HTML = os.path.join(config.RAW_DIR, "sources", "nces_dt24_330.10.html")
OUT_CSV = os.path.join(config.RAW_DIR, "nces_tuition_public4yr.csv")
SOURCE = "NCES Digest 2024 Table 330.10 (Public 4-year, in-district)"
CONSTANT_ACADEMIC_YEAR = "2023-24"

# Column offsets within Table 330.10 (0-based): "Tuition and required fees / 4-year".
_COL_CURRENT_4YR = 5      # current dollars
_COL_CONSTANT_4YR = 17    # constant 2023-24 dollars


def _valid(html: str) -> bool:
    """True if the HTML actually contains the Table 330.10 data (not a bot-challenge)."""
    return "1963-64" in html and CONSTANT_ACADEMIC_YEAR in html and "Tuition" in html


def _load_html(*, refresh: bool = False) -> str:
    """Return the NCES table HTML, preferring a valid cached copy.

    NCES sits behind an F5 bot filter that can return a JS challenge instead of the
    table, so we (1) use a valid cache if present, else (2) download, and only cache a
    download that actually contains the table.
    """
    os.makedirs(os.path.dirname(CACHE_HTML), exist_ok=True)
    if not refresh and os.path.exists(CACHE_HTML):
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
        value = float(s)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def parse(html: str) -> list[dict]:
    tables = pd.read_html(io.StringIO(html))
    candidates = [t for t in tables
                  if t.shape[1] > _COL_CONSTANT_4YR
                  and "Public institutions" in t.iloc[:, 0].astype(str).values]
    if len(candidates) != 1:
        raise ValueError("NCES: expected one tuition table with a public-institutions section")
    data = candidates[0]
    for col, basis in [(_COL_CURRENT_4YR, "Current dollars"),
                       (_COL_CONSTANT_4YR, f"Constant {CONSTANT_ACADEMIC_YEAR} dollars")]:
        header = " ".join(map(str, data.columns[col]))
        if not all(text in header for text in (basis, "Tuition and required fees", "4-year")):
            raise ValueError(f"NCES: unexpected public four-year fee column: {header}")
    labels = data.iloc[:, 0].astype(str).str.strip().tolist()
    if labels.count("Public institutions") != 1 or labels.count("Private institutions") != 1:
        raise ValueError("NCES: missing or duplicate institution-control boundaries")
    start, end = labels.index("Public institutions"), labels.index("Private institutions")
    if start >= end:
        raise ValueError("NCES: invalid public-institutions section boundaries")
    public = data.iloc[start + 1:end]
    rows: list[dict] = []
    for _, r in public.iterrows():
        label = str(r.iloc[0]).strip()
        match = re.fullmatch(r"(\d{4})-(\d{4}|\d{2})\d*", label)
        if match is None:
            raise ValueError(f"NCES: invalid academic year {label}")
        next_year = int(match[1]) + 1
        if int(match[2]) != (next_year if len(match[2]) == 4 else next_year % 100):
            raise ValueError(f"NCES: invalid academic year {label}")
        acad = f"{match[1]}-{match[2]}"
        current = _num(r.iloc[_COL_CURRENT_4YR])
        constant = _num(r.iloc[_COL_CONSTANT_4YR])
        if current is None or constant is None:
            raise ValueError(f"NCES: invalid public four-year fees for {acad}")
        rows.append({
            "year": int(acad[:4]),
            "academic_year": acad,
            "tuition_current_usd": current,
            "tuition_constant_usd": constant,
            "constant_dollar_academic_year": CONSTANT_ACADEMIC_YEAR,
            "source": SOURCE,
            "source_url": NCES_URL,
        })
    years = [r["year"] for r in rows]
    if (set(years) != {1963, *range(1968, 2024)}
            or len(set(years)) != len(years)):
        raise ValueError("NCES: empty, duplicate or incomplete public tuition history")
    return sorted(rows, key=lambda r: r["year"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download the source edition.")
    args = parser.parse_args(argv)
    rows = parse(_load_html(refresh=args.refresh))
    if not rows:
        raise RuntimeError("NCES returned no tuition observations; existing data was not replaced")
    os.makedirs(config.RAW_DIR, exist_ok=True)
    fields = ["year", "academic_year", "tuition_current_usd",
              "tuition_constant_usd", "constant_dollar_academic_year", "source", "source_url"]
    with open(OUT_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[nces] wrote {len(rows)} years ({rows[0]['academic_year']}..{rows[-1]['academic_year']}) -> {OUT_CSV}")


if __name__ == "__main__":
    main()
