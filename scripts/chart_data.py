"""Validate the actual observations exported alongside publication figures."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess


def tracked_charts(root: Path) -> list[Path]:
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "outputs"], cwd=root,
    ).decode().split("\0")
    return sorted(
        Path(name) for name in files
        if name.endswith(".png") and not name.startswith("outputs/page_background/")
    )


def _bounds(value) -> bool:
    return (
        isinstance(value, list) and len(value) == 4
        and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in value)
        and value[0] <= value[2] and value[1] <= value[3]
    )


def load_chart_data(root: Path, chart: Path) -> dict:
    sidecar = chart.with_suffix(".json")
    if not (root / sidecar).is_file():
        raise ValueError(f"{chart}: missing hover observations ({sidecar})")
    payload = json.loads((root / sidecar).read_text())
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"{sidecar}: unsupported hover data")
    if payload.get("image_sha256") != hashlib.sha256((root / chart).read_bytes()).hexdigest():
        raise ValueError(f"{sidecar}: observations do not match the published PNG")
    series = payload.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError(f"{sidecar}: no plotted observations")
    for item in series:
        if (
            not isinstance(item, dict)
            or not all(isinstance(item.get(key), str) for key in ("label", "x_label", "y_label"))
            or not _bounds(item.get("bounds"))
            or not isinstance(item.get("points"), list) or not item["points"]
        ):
            raise ValueError(f"{sidecar}: invalid observation series")
        for point in item["points"]:
            if (
                not isinstance(point, list) or len(point) not in (4, 5)
                or not all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in point[:2])
                or not all(isinstance(label, str) and label for label in point[2:4])
                or (len(point) == 5 and not _bounds(point[4]))
            ):
                raise ValueError(f"{sidecar}: invalid observation or image coordinate")
    return payload


def validate_refresh(root: Path, started_ns: int) -> None:
    """Every published original must be regenerated before advancing refresh status."""
    for chart in tracked_charts(root):
        load_chart_data(root, chart)
        if any((root / path).stat().st_mtime_ns < started_ns for path in (chart, chart.with_suffix(".json"))):
            raise RuntimeError(f"{chart}: chart or observations were not regenerated in this refresh")
