"""Extract definitions from Clause 3 of the 802.11 standard."""

import re
from dataclasses import dataclass

import pymupdf


@dataclass
class Definition:
    term: str
    definition: str
    section_number: str
    standard_version: str = ""


def extract_definitions(
    doc: pymupdf.Document,
    toc: list[tuple],
) -> list[Definition]:
    """Extract all definitions from Clause 3 of the standard.

    Clause 3 has subsections:
    - 3.1 Definitions (general IEEE definitions)
    - 3.2 Definitions specific to IEEE Std 802.11
    - 3.3 Definitions specific to IEEE 802.11 operation in some regulatory domains
    - 3.4 Acronyms and abbreviations
    """
    # Find the page range for Clause 3
    clause3_start = None
    clause3_end = None

    for level, title, page in toc:
        if re.match(r'^3[\s.]', title) or title.startswith('3 '):
            if clause3_start is None:
                clause3_start = page - 1
        elif clause3_start is not None and re.match(r'^4[\s.]', title):
            clause3_end = page - 1
            break

    if clause3_start is None:
        return []
    if clause3_end is None:
        clause3_end = min(clause3_start + 100, doc.page_count - 1)

    # Extract text from Clause 3 pages
    full_text = ""
    for page_idx in range(clause3_start, clause3_end):
        page = doc[page_idx]
        full_text += page.get_text() + "\n"

    # Parse definitions
    definitions = []

    # Determine which subsection pages belong to
    subsections = _find_definition_subsections(toc)

    # Pattern for definitions: term followed by colon or bold formatting
    # IEEE standards use format: "term: definition text"
    # or sometimes "term (synonym): definition text"
    definitions.extend(_parse_definition_block(full_text, subsections))

    return definitions


def _find_definition_subsections(toc: list[tuple]) -> dict[str, str]:
    """Map page ranges to subsection numbers for Clause 3."""
    subsections = {}
    for level, title, page in toc:
        match = re.match(r'^(3\.\d+)', title)
        if match:
            subsections[match.group(1)] = title
    return subsections


def _parse_definition_block(text: str, subsections: dict) -> list[Definition]:
    """Parse a block of definition text into individual definitions.

    The 802.11 standard uses these formats:
    - "term: definition" (most common)
    - "term (abbreviation): definition"
    - Multi-line definitions that continue until the next term
    """
    definitions = []

    # Current section tracking
    current_section = "3.1"

    # Detect section headers in the text
    section_pattern = re.compile(r'^(3\.\d+)\s+(.+)$', re.MULTILINE)

    # Split text into lines for processing
    lines = text.split('\n')

    # Pattern for a definition start: word(s) followed by colon with definition
    # IEEE format: lowercase term, possibly with parenthetical, then ": "
    def_start_pattern = re.compile(
        r'^([a-z][a-z\s\-/()]+?):\s+(.+)$'
    )

    # Also handle bold-style definitions (term on its own line, def on next)
    # and numbered definitions like "3.2 term: definition"

    current_term = None
    current_def_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for section header
        sec_match = section_pattern.match(line)
        if sec_match:
            # Save current definition if any
            if current_term:
                definitions.append(Definition(
                    term=current_term,
                    definition=' '.join(current_def_lines).strip(),
                    section_number=current_section,
                ))
                current_term = None
                current_def_lines = []
            current_section = sec_match.group(1)
            continue

        # Skip page headers/footers
        if _is_header_footer(line):
            continue

        # Check for new definition
        def_match = def_start_pattern.match(line)
        if def_match:
            # Save previous definition
            if current_term:
                definitions.append(Definition(
                    term=current_term,
                    definition=' '.join(current_def_lines).strip(),
                    section_number=current_section,
                ))

            current_term = def_match.group(1).strip()
            current_def_lines = [def_match.group(2).strip()]
        elif current_term:
            # Continuation of current definition
            current_def_lines.append(line)

    # Don't forget the last definition
    if current_term:
        definitions.append(Definition(
            term=current_term,
            definition=' '.join(current_def_lines).strip(),
            section_number=current_section,
        ))

    return definitions


def extract_acronyms(
    doc: pymupdf.Document,
    toc: list[tuple],
) -> list[Definition]:
    """Extract acronyms and abbreviations from section 3.4."""
    # Find section 3.4
    sec_start = None
    sec_end = None

    for level, title, page in toc:
        if '3.4' in title and 'cronym' in title.lower():
            sec_start = page - 1
        elif sec_start is not None and re.match(r'^[4-9][\s.]', title):
            sec_end = page - 1
            break

    if sec_start is None:
        return []
    if sec_end is None:
        sec_end = min(sec_start + 20, doc.page_count - 1)

    text = ""
    for page_idx in range(sec_start, sec_end):
        page = doc[page_idx]
        text += page.get_text() + "\n"

    acronyms = []
    # Acronym format: "ABBREVIATION  definition" or "ABBREVIATION - definition"
    acronym_pattern = re.compile(
        r'^([A-Z][A-Z0-9\-/]{1,15})\s{2,}(.+?)$',
        re.MULTILINE
    )

    for match in acronym_pattern.finditer(text):
        term = match.group(1).strip()
        definition = match.group(2).strip()
        if len(term) >= 2 and len(definition) >= 3:
            acronyms.append(Definition(
                term=term,
                definition=definition,
                section_number="3.4",
            ))

    return acronyms


def _is_header_footer(line: str) -> bool:
    """Detect page headers and footers to skip."""
    if 'IEEE Std 802.11' in line:
        return True
    if 'Copyright' in line and 'IEEE' in line:
        return True
    if re.match(r'^\d+$', line):  # bare page numbers
        return True
    if 'All rights reserved' in line:
        return True
    return False
