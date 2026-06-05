"""Main extraction pipeline: PDF -> SQLite database.

Usage:
    python extract.py [--pdf PATH] [--output PATH] [--standard-version VER] [--skip-figures] [--pages START:END]
"""

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

import pymupdf

from config import (
    DB_PATH,
    FIGURES_DIR,
    OUTPUT_DIR,
    PDF_PATH,
    SCHEMA_PATH,
    FIGURE_DPI,
    DEFAULT_STANDARD_VERSION,
)
from extractors.sections import parse_toc, extract_section_text
from extractors.tables import extract_tables_from_doc
from extractors.figures import extract_figures
from extractors.definitions import extract_definitions, extract_acronyms
from extractors.crossrefs import extract_cross_references

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)


def create_database(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    """Create the SQLite database and apply schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")

    with open(schema_path) as f:
        conn.executescript(f.read())

    return conn


def run_pipeline(
    pdf_path: Path,
    db_path: Path,
    schema_path: Path,
    figures_dir: Path,
    standard_version: str,
    skip_figures: bool = False,
    page_range: tuple[int, int] | None = None,
    text_batch_size: int = 50,
):
    """Run the full extraction pipeline."""
    total_start = time.time()

    log.info("Opening PDF: %s", pdf_path)
    log.info("Standard version: %s", standard_version)
    doc = pymupdf.open(str(pdf_path))
    log.info("PDF has %d pages", doc.page_count)

    # --- Step 1: Create/open database ---
    log.info("Database at %s", db_path)
    conn = create_database(db_path, schema_path)

    # Remove existing data for this standard version (allows re-extraction)
    _clear_version(conn, standard_version)

    # --- Step 2: Parse TOC and section hierarchy ---
    log.info("Parsing table of contents...")
    sections = parse_toc(doc)
    log.info("Found %d sections", len(sections))

    # Filter by page range if specified
    if page_range:
        start, end = page_range
        sections = [s for s in sections if s.page_start >= start and s.page_start <= end]
        log.info("Filtered to %d sections in page range %d-%d", len(sections), start, end)

    # Tag all sections with the standard version
    for sec in sections:
        sec.standard_version = standard_version

    # --- Step 3: Extract section text ---
    log.info("Extracting section text (batch_size=%d)...", text_batch_size)
    sections = extract_section_text(doc, sections, batch_size=text_batch_size)
    log.info("Text extraction complete")

    # Insert sections into database
    log.info("Inserting %d sections into database...", len(sections))
    _insert_sections(conn, sections)

    # --- Step 4: Extract tables ---
    log.info("Extracting tables...")
    tables = extract_tables_from_doc(doc, sections, page_range=page_range)
    for t in tables:
        t.standard_version = standard_version
    log.info("Found %d tables", len(tables))
    _insert_tables(conn, tables)

    # --- Step 5: Extract figures ---
    if not skip_figures:
        log.info("Extracting figures (DPI=%d)...", FIGURE_DPI)
        figures = extract_figures(doc, figures_dir, sections, dpi=FIGURE_DPI, page_range=page_range)
        for f in figures:
            f.standard_version = standard_version
        log.info("Extracted %d figures", len(figures))
        _insert_figures(conn, figures)
    else:
        log.info("Skipping figure extraction (--skip-figures)")

    # --- Step 6: Extract definitions ---
    log.info("Extracting definitions from Clause 3...")
    toc_raw = doc.get_toc()
    definitions = extract_definitions(doc, toc_raw)
    acronyms = extract_acronyms(doc, toc_raw)
    all_defs = definitions + acronyms
    for d in all_defs:
        d.standard_version = standard_version
    log.info("Found %d definitions + %d acronyms", len(definitions), len(acronyms))
    _insert_definitions(conn, all_defs)

    # --- Step 7: Extract cross-references ---
    log.info("Scanning cross-references...")
    valid_sections = {sec.section_number for sec in sections}
    crossrefs = extract_cross_references(sections, valid_sections)
    for r in crossrefs:
        r.standard_version = standard_version
    log.info("Found %d unique cross-references", len(crossrefs))
    _insert_crossrefs(conn, crossrefs)

    # --- Finalize ---
    conn.commit()
    conn.close()
    doc.close()

    elapsed = time.time() - total_start
    log.info("Pipeline complete in %.1f seconds", elapsed)
    log.info("Database: %s", db_path)
    log.info("Figures: %s", figures_dir)

    _print_summary(db_path)


def _clear_version(conn: sqlite3.Connection, standard_version: str) -> None:
    """Remove all existing data for a given standard version (allows re-import)."""
    for table in ['sections', 'tables', 'figures', 'definitions', 'cross_references']:
        conn.execute(f"DELETE FROM {table} WHERE standard_version = ?", (standard_version,))
    # Clear FTS tables for this version
    for fts in ['sections_fts', 'tables_fts', 'definitions_fts']:
        try:
            conn.execute(f"DELETE FROM {fts} WHERE standard_version = ?", (standard_version,))
        except Exception:
            pass
    conn.commit()


def _insert_sections(conn: sqlite3.Connection, sections) -> None:
    conn.executemany(
        """INSERT OR REPLACE INTO sections
           (standard_version, section_number, title, level, parent_section, content_markdown, page_start, page_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (s.standard_version, s.section_number, s.title, s.level, s.parent_section,
             s.content_markdown, s.page_start, s.page_end)
            for s in sections
        ]
    )
    conn.commit()


def _insert_tables(conn: sqlite3.Connection, tables) -> None:
    conn.executemany(
        """INSERT INTO tables
           (standard_version, section_number, table_number, caption, markdown, structured_json, page_number)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (t.standard_version, t.section_number, t.table_number, t.caption,
             t.markdown, t.structured_json, t.page_number)
            for t in tables
        ]
    )
    conn.commit()


def _insert_figures(conn: sqlite3.Connection, figures) -> None:
    conn.executemany(
        """INSERT INTO figures
           (standard_version, section_number, figure_number, caption, image_path, description, figure_type, page_number)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (f.standard_version, f.section_number, f.figure_number, f.caption,
             f.image_path, None, f.figure_type, f.page_number)
            for f in figures
        ]
    )
    conn.commit()


def _insert_definitions(conn: sqlite3.Connection, definitions) -> None:
    conn.executemany(
        """INSERT INTO definitions (standard_version, term, definition, section_number)
           VALUES (?, ?, ?, ?)""",
        [(d.standard_version, d.term, d.definition, d.section_number) for d in definitions]
    )
    conn.commit()


def _insert_crossrefs(conn: sqlite3.Connection, crossrefs) -> None:
    conn.executemany(
        """INSERT INTO cross_references
           (standard_version, source_section, target_section, target_type, context)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (r.standard_version, r.source_section, r.target_section, r.target_type, r.context)
            for r in crossrefs
        ]
    )
    conn.commit()


def _print_summary(db_path: Path) -> None:
    """Print extraction summary statistics."""
    conn = sqlite3.connect(str(db_path))
    counts = {}
    for table in ['sections', 'tables', 'figures', 'definitions', 'cross_references']:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cur.fetchone()[0]

    # Also show per-version counts
    versions = conn.execute("SELECT DISTINCT standard_version FROM sections").fetchall()
    conn.close()

    log.info("=" * 50)
    log.info("EXTRACTION SUMMARY")
    log.info("=" * 50)
    for table, count in counts.items():
        log.info("  %-20s %6d records", table, count)
    log.info("-" * 50)
    log.info("  Standards loaded: %s", ", ".join(v[0] for v in versions))
    log.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Extract IEEE 802.11 PDF into structured SQLite database"
    )
    parser.add_argument(
        '--pdf', type=Path, default=PDF_PATH,
        help='Path to the 802.11 PDF file'
    )
    parser.add_argument(
        '--output', type=Path, default=DB_PATH,
        help='Output database path'
    )
    parser.add_argument(
        '--figures-dir', type=Path, default=FIGURES_DIR,
        help='Directory for extracted figure images'
    )
    parser.add_argument(
        '--standard-version', type=str, default=DEFAULT_STANDARD_VERSION,
        help='Standard version identifier (e.g., "802.11-2020", "802.11ax-2021")'
    )
    parser.add_argument(
        '--skip-figures', action='store_true',
        help='Skip figure extraction (faster for testing)'
    )
    parser.add_argument(
        '--pages', type=str, default=None,
        help='Page range to process (e.g., "0:100" for first 100 pages)'
    )
    parser.add_argument(
        '--batch-size', type=int, default=50,
        help='Number of pages to process in each text extraction batch'
    )

    args = parser.parse_args()

    page_range = None
    if args.pages:
        parts = args.pages.split(':')
        page_range = (int(parts[0]), int(parts[1]))

    if not args.pdf.exists():
        log.error("PDF not found: %s", args.pdf)
        sys.exit(1)

    run_pipeline(
        pdf_path=args.pdf,
        db_path=args.output,
        schema_path=SCHEMA_PATH,
        figures_dir=args.figures_dir,
        standard_version=args.standard_version,
        skip_figures=args.skip_figures,
        page_range=page_range,
        text_batch_size=args.batch_size,
    )


if __name__ == '__main__':
    main()
