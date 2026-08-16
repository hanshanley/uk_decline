"""Historical Trussell financial-year series with explicit source-vintage breaks."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from .sources import ACCESSED_DATE, FISCAL_SLIDES_SOURCE

FISCAL_COLUMNS = [
    "period_type",
    "period_label",
    "start_year",
    "end_year",
    "start_date",
    "end_date",
    "adults",
    "children",
    "total",
    "change_within_series_pct",
    "metric_wording",
    "comparability_group",
    "source_label",
    "source_url",
    "source_location",
    "accessed_date",
]


def _validate(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "period_label",
        "start_year",
        "end_year",
        "total",
        "metric_wording",
        "comparability_group",
        "source_label",
        "source_url",
        "source_location",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"historical data missing columns: {sorted(missing)}")
    if frame.empty or frame["period_label"].duplicated().any():
        raise ValueError("historical periods must be non-empty and unique")
    if (frame["total"] <= 0).any():
        raise ValueError("historical parcel counts must be positive; missing years are not zero")
    expected_labels = frame.apply(
        lambda row: f"{int(row['start_year'])}/{str(int(row['end_year']))[-2:]}",
        axis=1,
    )
    if not expected_labels.equals(frame["period_label"].astype(str)):
        raise ValueError("financial-year labels do not match start/end years")
    if not (frame["end_year"] == frame["start_year"] + 1).all():
        raise ValueError("financial-year periods must span exactly one year")
    return frame.sort_values("start_year").reset_index(drop=True)


def load_archive(source: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(source, sep="\t")
    frame["adults"] = pd.NA
    frame["children"] = pd.NA
    frame["period_type"] = "financial_year"
    frame["start_date"] = frame["start_year"].astype(str) + "-04-01"
    frame["end_date"] = frame["end_year"].astype(str) + "-03-31"
    frame["accessed_date"] = ACCESSED_DATE
    frame = _validate(frame)
    frame["change_within_series_pct"] = frame["total"].pct_change() * 100
    return frame[FISCAL_COLUMNS]


def parse_official_fiscal_pptx(source: str | Path) -> pd.DataFrame:
    """Extract the UK table embedded in Trussell's official 2023/24 slide deck."""
    with zipfile.ZipFile(source) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")
        ]
        table = None
        for name in candidates:
            workbook = io.BytesIO(archive.read(name))
            candidate = pd.read_excel(workbook, header=0, index_col=0)
            if "Total number of parcels" in candidate.columns:
                table = candidate
                break
    if table is None:
        raise ValueError("could not find the UK fiscal parcel table in the PPTX")

    records = []
    for label, row in table.iterrows():
        match = re.fullmatch(r"(20\d{2})/(\d{2})", str(label).strip())
        if not match:
            continue
        start_year = int(match.group(1))
        end_year = (start_year // 100) * 100 + int(match.group(2))
        if end_year <= start_year:
            end_year += 100
        records.append(
            {
                "period_type": "financial_year",
                "period_label": str(label),
                "start_year": start_year,
                "end_year": end_year,
                "start_date": f"{start_year}-04-01",
                "end_date": f"{end_year}-03-31",
                "adults": int(row["Number of parcels for adults"]),
                "children": int(row["Number of parcels for children"]),
                "total": int(row["Total number of parcels"]),
                "metric_wording": (
                    "Emergency food parcels; from April 2020 three- and seven-day "
                    "parcels are combined"
                ),
                "comparability_group": "modern_fiscal",
                "source_label": "Trussell end-of-year statistics 2023/24 slide deck",
                "source_url": FISCAL_SLIDES_SOURCE.url,
                "source_location": "Embedded UK Excel table",
                "accessed_date": ACCESSED_DATE,
            }
        )

    frame = _validate(pd.DataFrame(records))
    mismatch = frame["adults"] + frame["children"] != frame["total"]
    if mismatch.any():
        raise ValueError("modern fiscal adult and child parcels do not sum to total")
    frame["change_within_series_pct"] = frame["total"].pct_change() * 100
    return frame[FISCAL_COLUMNS]


def build_fiscal_history(
    archive_source: str | Path,
    pptx_source: str | Path,
) -> pd.DataFrame:
    archive = load_archive(archive_source)
    modern = parse_official_fiscal_pptx(pptx_source)
    if set(archive["period_label"]) & set(modern["period_label"]):
        raise ValueError("source-vintage groups must not overlap")
    frame = pd.concat([archive, modern], ignore_index=True)
    frame = _validate(frame)
    frame["change_within_series_pct"] = (
        frame.groupby("comparability_group", sort=False)["total"].pct_change() * 100
    )
    return frame[FISCAL_COLUMNS]
