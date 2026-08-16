"""Official source metadata for the food-bank analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs" / "food_banks"
ACCESSED_DATE = "2026-08-16"
FISCAL_ARCHIVE = RAW_DIR / "food_bank_trussell_fiscal_archive.tsv"

END_YEAR_PAGE = (
    "https://www.trussell.org.uk/news-and-research/latest-stats/end-of-year-stats"
)
MID_YEAR_PAGE = (
    "https://www.trussell.org.uk/news-and-research/latest-stats/mid-year-stats"
)
STORY_PAGE = "https://www.trussell.org.uk/our-work/what-we-do/our-story"
FISCAL_METHODOLOGY_URL = (
    "https://cms.trussell.org.uk/sites/default/files/wp-assets/EYS-methodology.pdf"
)


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    filename: str
    description: str

    def path(self, raw_dir: Path = RAW_DIR) -> Path:
        return Path(raw_dir) / self.filename


CALENDAR_SOURCE = Source(
    key="calendar",
    url=(
        "https://cms.trussell.org.uk/sites/default/files/2026-03/"
        "eys_2025_parcel_stats.xlsx"
    ),
    filename="food_bank_trussell_eys_2025.xlsx",
    description="Trussell 2025 end-of-year parcel statistics",
)

MIDYEAR_SOURCE = Source(
    key="midyear",
    url=(
        "https://trusselltrustprod.prod.acquia-sites.com/sites/default/files/"
        "2024-11/MYS%202024%20parcel%20statistics%20%28web%29.xlsx"
    ),
    filename="food_bank_trussell_mys_2024.xlsx",
    description="Trussell April-September 2024 parcel statistics",
)

FISCAL_SLIDES_SOURCE = Source(
    key="fiscal_history",
    url=(
        "https://hub.foodbank.org.uk/wp-content/uploads/2024/05/"
        "Template-2024-End-of-Year-stats-presentation-slides.pptx"
    ),
    filename="food_bank_trussell_eys_2024_slides.pptx",
    description="Trussell 2023/24 end-of-year statistics slide deck",
)

SOURCES = (CALENDAR_SOURCE, MIDYEAR_SOURCE, FISCAL_SLIDES_SOURCE)
