"""Extract section hierarchy and text content from the 802.11 PDF."""

import re
import logging
import pymupdf
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class Section:
    section_number: str
    title: str
    level: int
    parent_section: str | None
    page_start: int
    page_end: int | None = None
    content_markdown: str = ""


def parse_toc(doc: pymupdf.Document) -> list[Section]:
    """Parse PDF table of contents into structured Section objects.

    Filters out front matter (cover, participants, etc.) and keeps only
    numbered sections (e.g., '1. Overview', '9.4.2.183 ...').
    """
    toc = doc.get_toc()
    sections: list[Section] = []
    section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)$')

    for level, title, page in toc:
        title = title.strip()
        match = section_pattern.match(title)
        if not match:
            annex_match = re.match(r'^(Annex\s+[A-Z])\s*[.—\-:]\s*(.+)$', title)
            if annex_match:
                sec_num = annex_match.group(1).replace(" ", "_")
                sec_title = annex_match.group(2).strip()
            else:
                continue
        else:
            sec_num = match.group(1)
            sec_title = match.group(2).strip()

        parent = _find_parent(sec_num)

        sections.append(Section(
            section_number=sec_num,
            title=sec_title,
            level=level,
            parent_section=parent,
            page_start=page - 1,
        ))

    # Compute page_end for each section
    for i in range(len(sections) - 1):
        sections[i].page_end = sections[i + 1].page_start
    if sections:
        sections[-1].page_end = doc.page_count - 1

    return sections


def _find_parent(section_number: str) -> str | None:
    """Derive parent section number from a section number string."""
    if section_number.startswith("Annex_"):
        return None
    parts = section_number.split('.')
    if len(parts) <= 1:
        return None
    return '.'.join(parts[:-1])


def extract_section_text(
    doc: pymupdf.Document,
    sections: list[Section],
    batch_size: int = 100,
) -> list[Section]:
    """Extract text for each section using PyMuPDF's fast text extraction.

    Uses get_text() for plain text and find_tables() for inline table markdown.
    This is much faster than pymupdf4llm (~0.01s/page vs ~10s/page).
    """
    if not sections:
        return sections

    # Collect all unique pages we need
    all_pages = set()
    for sec in sections:
        end = sec.page_end if sec.page_end is not None else sec.page_start
        # Cap at 50 pages per section to avoid massive sections dominating
        for p in range(sec.page_start, min(end + 1, sec.page_start + 50)):
            all_pages.add(p)

    sorted_pages = sorted(all_pages)
    log.info("Extracting text from %d unique pages...", len(sorted_pages))

    # Extract text from all pages using fast get_text()
    # Tables are extracted separately in the tables extraction step
    page_text: dict[int, str] = {}
    for page_num in sorted_pages:
        page = doc[page_num]
        page_text[page_num] = page.get_text("text")

    # Assign content to sections by combining their page range text
    for sec in sections:
        end = sec.page_end if sec.page_end is not None else sec.page_start
        pages_content = []
        for p in range(sec.page_start, min(end + 1, sec.page_start + 50)):
            if p in page_text:
                pages_content.append(page_text[p])
        sec.content_markdown = '\n\n'.join(pages_content)

    # Refine section boundaries
    _refine_section_boundaries(sections)

    return sections


def _refine_section_boundaries(sections: list[Section]) -> None:
    """Trim section content to only include text belonging to that section.

    Uses section title matching to find where the section actually starts
    within the page text, and where the next section begins.
    """
    for i, sec in enumerate(sections):
        if not sec.content_markdown:
            continue

        # Try to find the section header in the text
        escaped_title = re.escape(sec.title[:30])
        header_pattern = re.compile(
            re.escape(sec.section_number) + r'\s+' + escaped_title,
            re.IGNORECASE
        )
        match = header_pattern.search(sec.content_markdown)
        if match:
            sec.content_markdown = sec.content_markdown[match.start():]

        # Trim at the start of the next section if on the same page
        if i + 1 < len(sections):
            next_sec = sections[i + 1]
            if next_sec.page_start <= sec.page_start + 1:
                escaped_next = re.escape(next_sec.title[:30])
                next_pattern = re.compile(
                    re.escape(next_sec.section_number) + r'\s+' + escaped_next,
                    re.IGNORECASE
                )
                next_match = next_pattern.search(sec.content_markdown)
                if next_match and next_match.start() > 0:
                    sec.content_markdown = sec.content_markdown[:next_match.start()]
