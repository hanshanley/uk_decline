"""Shared filesystem paths for nhs_data outputs.

All generated artifacts (combined CSV, charts, summary) are written under the
project-level ``outputs/nhs/`` folder so the deliverables live in one place.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"          # kept for any raw/intermediate data
OUTPUT_DIR = PROJECT_DIR / "outputs" / "nhs"   # generated deliverables (CSV, charts, summary)
DEFAULT_CSV = OUTPUT_DIR / "nhs_waiting_times.csv"
CHART_DIR = OUTPUT_DIR                    # charts written directly under outputs/nhs/
DEFAULT_SUMMARY = OUTPUT_DIR / "nhs_waiting_times_summary.md"
