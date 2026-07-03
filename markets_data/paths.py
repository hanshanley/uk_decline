"""Shared filesystem paths for markets_data outputs."""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CSV = DATA_DIR / "stock_market_size.csv"
DEFAULT_WIDE_CSV = DATA_DIR / "stock_market_size_wide.csv"
DEFAULT_MANIFEST = DATA_DIR / "stock_market_size_manifest.json"
CHART_DIR = DATA_DIR / "charts"
DEFAULT_SUMMARY = DATA_DIR / "stock_market_size_summary.md"
