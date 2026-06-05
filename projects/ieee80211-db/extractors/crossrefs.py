"""Extract cross-references between sections, tables, and figures."""

import re
from dataclasses import dataclass


@dataclass
class CrossReference:
    source_section: str
    target_section: str
    target_type: str  # "section", "table", "figure", "annex"
    context: str
    standard_version: str = ""


# Patterns for different reference types
SECTION_REF = re.compile(r'(\d+\.\d+(?:\.\d+)*)')
TABLE_REF = re.compile(r'Table\s+([A-Z]?-?\d+(?:-\d+)?)')
FIGURE_REF = re.compile(r'Figure\s+([A-Z]?-?\d+(?:-\d+)?)')
ANNEX_REF = re.compile(r'Annex\s+([A-Z])')


def extract_cross_references(
    sections: list,
    valid_section_numbers: set[str] | None = None,
) -> list[CrossReference]:
    """Scan all section content for cross-references to other sections/tables/figures.

    Args:
        sections: List of Section objects with content_markdown
        valid_section_numbers: Set of known section numbers to validate against
    """
    refs: list[CrossReference] = []
    all_section_numbers = valid_section_numbers or {
        sec.section_number for sec in sections
    }

    for sec in sections:
        if not sec.content_markdown:
            continue

        text = sec.content_markdown

        # Find section references
        for match in SECTION_REF.finditer(text):
            target = match.group(1)
            if target == sec.section_number:
                continue  # skip self-references
            if target in all_section_numbers:
                context = _get_context(text, match.start(), match.end())
                refs.append(CrossReference(
                    source_section=sec.section_number,
                    target_section=target,
                    target_type="section",
                    context=context,
                ))

        # Find table references
        for match in TABLE_REF.finditer(text):
            table_num = f"Table {match.group(1)}"
            context = _get_context(text, match.start(), match.end())
            refs.append(CrossReference(
                source_section=sec.section_number,
                target_section=table_num,
                target_type="table",
                context=context,
            ))

        # Find figure references
        for match in FIGURE_REF.finditer(text):
            fig_num = f"Figure {match.group(1)}"
            context = _get_context(text, match.start(), match.end())
            refs.append(CrossReference(
                source_section=sec.section_number,
                target_section=fig_num,
                target_type="figure",
                context=context,
            ))

        # Find annex references
        for match in ANNEX_REF.finditer(text):
            annex_id = f"Annex_{match.group(1)}"
            context = _get_context(text, match.start(), match.end())
            refs.append(CrossReference(
                source_section=sec.section_number,
                target_section=annex_id,
                target_type="annex",
                context=context,
            ))

    # Deduplicate (same source->target pair, keep first context)
    refs = _deduplicate(refs)

    return refs


def _get_context(text: str, start: int, end: int, window: int = 80) -> str:
    """Extract surrounding context for a reference."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)

    context = text[ctx_start:ctx_end].strip()
    # Clean up whitespace
    context = re.sub(r'\s+', ' ', context)

    if ctx_start > 0:
        context = "..." + context
    if ctx_end < len(text):
        context = context + "..."

    return context


def _deduplicate(refs: list[CrossReference]) -> list[CrossReference]:
    """Remove duplicate references (same source->target pair)."""
    seen: set[tuple[str, str, str]] = set()
    unique = []

    for ref in refs:
        key = (ref.source_section, ref.target_section, ref.target_type)
        if key not in seen:
            seen.add(key)
            unique.append(ref)

    return unique
