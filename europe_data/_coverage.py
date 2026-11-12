"""Preserve published observations when a live source returns a partial table."""

import csv
import math
from pathlib import Path


def validate_csv_refresh(
    rows: list[dict], path: Path, keys: tuple[str, ...], *,
    start: int | None = None, end: int | None = None,
) -> None:
    seen = set()
    for row in rows:
        key = tuple(str(row[field]).strip() for field in keys)
        if any(value in ("", "None") for value in key) or key in seen:
            raise ValueError(f"{path}: missing or duplicate observation key {key}")
        if not math.isfinite(float(row["value"])):
            raise ValueError(f"{path}: nonfinite observation {key}")
        seen.add(key)
    if not path.exists():
        return
    with path.open(newline="") as handle:
        previous = {
            tuple(row[field].strip() for field in keys)
            for row in csv.DictReader(handle)
            if row["value"] not in ("", None)
            and (start is None or int(row["year"]) >= start)
            and (end is None or int(row["year"]) <= end)
        }
    missing = previous - seen
    if missing:
        raise RuntimeError(
            f"{path}: refresh would lose {len(missing)} published observations; "
            "existing data was not replaced"
        )
