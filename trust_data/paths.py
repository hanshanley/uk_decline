"""Shared output paths for the trust pipeline."""

from __future__ import annotations

import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG_DIR)

OUT_DIR = os.path.join(ROOT, "data", "trust")
RAW_DIR = os.path.join(OUT_DIR, "raw")
PROCESSED_DIR = os.path.join(OUT_DIR, "processed")
CHART_DIR = os.path.join(OUT_DIR, "charts")

DEFAULT_LONG_CSV = os.path.join(OUT_DIR, "trust_combined_long.csv")
SUMMARY_CSV = os.path.join(PROCESSED_DIR, "trust_summary.csv")
