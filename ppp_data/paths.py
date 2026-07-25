"""Shared filesystem paths for the PPP analysis.

Mirrors the ``markets_data.paths`` convention: regenerable CSVs and the run manifest go
under ``data/`` (git-ignored), while the committed showcase figures go under
``outputs/ppp/``.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data"
OUTPUT_DIR = _ROOT / "outputs"

# Regenerable data (git-ignored under data/).
LONG_CSV = DATA_DIR / "ppp_long.csv"
WIDE_CSV = DATA_DIR / "ppp_wide.csv"
MANIFEST = DATA_DIR / "ppp_manifest.json"

# Inputs produced by sibling analyses (read-only here).
TUITION_HISTORY_CSV = DATA_DIR / "processed" / "tuition_history.csv"

# Committed showcase figures.
CHART_DIR = OUTPUT_DIR / "ppp"
