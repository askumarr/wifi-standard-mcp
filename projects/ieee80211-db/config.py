"""Configuration for IEEE 802.11 PDF extraction pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
REPO_ROOT = PROJECT_ROOT.parent.parent
RESOURCES_DIR = REPO_ROOT / "resources"

PDF_PATH = RESOURCES_DIR / "80211-2020.pdf"
PDF_AX_PATH = RESOURCES_DIR / "80211ax-2021.pdf"

OUTPUT_DIR = PROJECT_ROOT / "output"
DB_PATH = OUTPUT_DIR / "ieee80211.db"
FIGURES_DIR = OUTPUT_DIR / "figures"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"

FIGURE_DPI = 200
FIGURE_FORMAT = "png"

DEFAULT_STANDARD_VERSION = "802.11-2020"

# Map PDF filenames to standard version identifiers
PDF_VERSION_MAP = {
    "80211-2020.pdf": "802.11-2020",
    "80211ax-2021.pdf": "802.11ax-2021",
}

# Section number regex pattern (matches patterns like "9.4.2.183")
SECTION_NUMBER_PATTERN = r'\b(\d+(?:\.\d+)+)\b'

# Table reference pattern (matches "Table 9-92", "Table C-1", etc.)
TABLE_REF_PATTERN = r'(Table\s+[A-Z]?-?\d+(?:-\d+)?)'

# Figure reference pattern (matches "Figure 10-5", "Figure C-1", etc.)
FIGURE_REF_PATTERN = r'(Figure\s+[A-Z]?-?\d+(?:-\d+)?)'
