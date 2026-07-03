"""Shared filesystem paths for nhs_data outputs."""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CSV = DATA_DIR / "nhs_waiting_times.csv"
CHART_DIR = DATA_DIR / "charts"
DEFAULT_SUMMARY = DATA_DIR / "nhs_waiting_times_summary.md"
