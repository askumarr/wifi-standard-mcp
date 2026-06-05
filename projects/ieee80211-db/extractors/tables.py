"""Extract tables from the 802.11 PDF and convert to structured JSON."""

import re
import json
import logging
import pymupdf
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    table_number: str | None
    caption: str
    section_number: str | None
    markdown: str
    structured_json: str
    page_number: int


def extract_tables_from_doc(
    doc: pymupdf.Document,
    sections: list | None = None,
    page_range: tuple[int, int] | None = None,
) -> list[ExtractedTable]:
    """Extract all tables using PyMuPDF's find_tables() (fast).

    This is significantly faster than pdfplumber for large documents.
    """
    tables: list[ExtractedTable] = []

    start_page = page_range[0] if page_range else 0
    end_page = page_range[1] if page_range else doc.page_count - 1

    total_pages = min(end_page + 1, doc.page_count) - start_page
    for i, page_idx in enumerate(range(start_page, min(end_page + 1, doc.page_count))):
        if i % 500 == 0:
            log.info("  Table scan progress: %d/%d pages (%d tables found so far)",
                     i, total_pages, len(tables))

        page = doc[page_idx]
        found = page.find_tables()

        if not found or not found.tables:
            continue

        page_text = page.get_text("text")

        for tbl_idx, tbl in enumerate(found.tables):
            try:
                df = tbl.to_pandas()
                if df.empty or len(df) < 1:
                    continue

                # Convert to cleaned rows
                headers = [str(h).replace('\n', ' ').strip() for h in df.columns]
                rows = []
                for _, row in df.iterrows():
                    rows.append([str(v).replace('\n', ' ').strip() if v is not None else '' for v in row])

                # Build markdown
                markdown = _rows_to_markdown(headers, rows)

                # Build structured JSON
                structured = _rows_to_json(headers, rows)

                # Find caption
                caption, table_number = _find_table_caption(page_text, tbl_idx)

                # Find section
                sec_num = _find_section_for_page(page_idx, sections) if sections else None

                tables.append(ExtractedTable(
                    table_number=table_number,
                    caption=caption,
                    section_number=sec_num,
                    markdown=markdown,
                    structured_json=json.dumps(structured, ensure_ascii=False),
                    page_number=page_idx,
                ))
            except Exception as e:
                log.debug("Skipping table on page %d: %s", page_idx, e)
                continue

    return tables


def _rows_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    """Convert headers + rows to markdown table."""
    if not headers:
        return ""

    col_count = len(headers)
    lines = []
    lines.append('| ' + ' | '.join(headers) + ' |')
    lines.append('| ' + ' | '.join(['---'] * col_count) + ' |')

    for row in rows:
        padded = row + [''] * (col_count - len(row))
        cells = [c.replace('|', '/') for c in padded[:col_count]]
        lines.append('| ' + ' | '.join(cells) + ' |')

    return '\n'.join(lines)


def _rows_to_json(headers: list[str], rows: list[list[str]]) -> list[dict]:
    """Convert headers + rows to list of dicts."""
    if not headers or not rows:
        return []

    # Ensure unique headers
    seen: dict[str, int] = {}
    unique_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)

    result = []
    for row in rows:
        entry = {}
        for i, header in enumerate(unique_headers):
            entry[header] = row[i] if i < len(row) else ""
        result.append(entry)

    return result


def _find_table_caption(page_text: str, table_idx: int) -> tuple[str, str | None]:
    """Find table caption in the page text."""
    pattern = re.compile(r'Table\s+([\w\-–]+)\s*[—\-–:\.]\s*(.+?)(?:\n|$)')
    matches = list(pattern.finditer(page_text))

    if table_idx < len(matches):
        m = matches[table_idx]
        table_number = f"Table {m.group(1)}"
        caption = m.group(2).strip()
        return caption, table_number

    # If more tables than captions, try to assign remaining
    if matches:
        m = matches[-1]
        table_number = f"Table {m.group(1)}"
        caption = m.group(2).strip()
        return caption, table_number

    return "", None


def _find_section_for_page(page_number: int, sections: list) -> str | None:
    """Find which section a page belongs to."""
    if not sections:
        return None
    for sec in reversed(sections):
        if hasattr(sec, 'page_start') and sec.page_start <= page_number:
            return sec.section_number
    return None
