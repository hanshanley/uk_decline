"""Shared filesystem paths for markets_data outputs.

Regenerable data (CSVs, manifest) lives under ``data/`` (git-ignored). The
showcase artifacts that reference their sources -- charts and the markdown
summary -- are written to ``outputs/`` so they can be committed, mirroring the
sibling ``pre1870_reapportionment_package`` project.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data"
OUTPUT_DIR = _ROOT / "outputs"

# Regenerable data (git-ignored under data/).
DEFAULT_CSV = DATA_DIR / "stock_market_size.csv"
DEFAULT_WIDE_CSV = DATA_DIR / "stock_market_size_wide.csv"
DEFAULT_MANIFEST = DATA_DIR / "stock_market_size_manifest.json"

# Committable showcase outputs (charts + summary) under outputs/stock_markets/.
CHART_DIR = OUTPUT_DIR / "stock_markets"
DEFAULT_SUMMARY = OUTPUT_DIR / "stock_markets" / "stock_market_size_summary.md"
