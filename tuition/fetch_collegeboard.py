"""Fetch the complete nominal US public four-year history from College Board.

Uses the 2025 edition throughout, not an append to the different NCES collection.
The publisher identifies a collection/enrollment-weighting break in 1987/88.
"""

from __future__ import annotations

import argparse
import csv
from io import BytesIO
import math
from pathlib import Path
import re

import pandas as pd

from tuition import config
from tuition.http import session

SOURCE_URL = (
    "https://research.collegeboard.org/media/xlsx/"
    "Trends-in_College-Pricing-2025-excel-data.xlsx"
)
BREAK_YEAR = 1987
FIRST_YEAR = 1971
LAST_YEAR = 2025
FIELDS = ["year", "tuition_current_usd", "source", "source_url"]


def parse(frame: pd.DataFrame) -> list[dict]:
    """Locate nominal tuition, excluding constant dollars and room/board."""
    sections = [
        i for i in range(len(frame))
        if "Tuition and Fees in Current Dollars" in frame.iloc[i].values
    ]
    if len(sections) != 1:
        raise ValueError("College Board nominal tuition section is missing or ambiguous")
    section = frame.iloc[sections[0]].tolist()
    housing = "Tuition and Fees and Housing and Food in Current Dollars"
    if section.count(housing) != 1:
        raise ValueError("College Board tuition/housing section boundary changed")
    header = frame.iloc[sections[0] + 1, :section.index(housing)].tolist()
    if header.count("Public Four-Year") != 1 or header[0] != "Academic Year":
        raise ValueError("College Board public four-year header changed")
    column = header.index("Public Four-Year")
    notes = " ".join(str(v) for v in frame.iloc[:, 0] if pd.notna(v))
    if not all(text in notes for text in (
        "1987-88 and after", "full-time undergraduate enrollment",
        "1986-87 and prior", "full-time equivalent enrollment",
    )):
        raise ValueError("College Board collection/weighting notes changed")
    rows = []
    for _, row in frame.iloc[sections[0] + 2:].iterrows():
        label = str(row.iloc[0]).strip()
        match = re.fullmatch(r"(\d{2})-(\d{2})", label)
        if not match:
            continue
        first, last = map(int, match.groups())
        year = 1900 + first if first >= 71 else 2000 + first
        if last != (year + 1) % 100:
            raise ValueError(f"College Board invalid academic year: {label}")
        value = float(row.iloc[column])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"College Board invalid tuition for {label}")
        collection = (
            "Annual Survey of Colleges; full-time undergraduate weights"
            if year >= BREAK_YEAR else "NCES/IPEDS; full-time-equivalent weights"
        )
        rows.append({
            "year": year, "tuition_current_usd": value,
            "source": f"College Board Trends in College Pricing 2025 Table CP-2; {collection}",
            "source_url": SOURCE_URL,
        })
    years = [row["year"] for row in rows]
    if years != list(range(FIRST_YEAR, LAST_YEAR + 1)):
        raise ValueError("College Board nominal history has missing/duplicate/unexpected years")
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, help="read a previously downloaded publisher workbook")
    args = ap.parse_args(argv)
    if args.input:
        content = args.input.read_bytes()
    else:
        response = session().get(SOURCE_URL, timeout=60)
        response.raise_for_status()
        content = response.content
    frame = pd.read_excel(BytesIO(content), sheet_name="Table CP-2", header=None)
    rows = parse(frame)
    with open(config.COLLEGEBOARD_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[College Board] wrote {len(rows)} nominal observations: {config.COLLEGEBOARD_CSV}")


if __name__ == "__main__":
    main()
