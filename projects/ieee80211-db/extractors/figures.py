"""Extract figures (raster images and vector diagrams) from the 802.11 PDF."""

import re
from pathlib import Path
from dataclasses import dataclass

import pymupdf


@dataclass
class ExtractedFigure:
    figure_number: str | None
    caption: str
    section_number: str | None
    image_path: str
    figure_type: str
    page_number: int


# Minimum dimensions to filter out decorative elements (lines, borders)
MIN_DRAWING_AREA = 5000  # square points (~70x70 pt minimum)
MIN_IMAGE_SIZE = (50, 50)  # pixels


def extract_figures(
    doc: pymupdf.Document,
    output_dir: Path,
    sections: list | None = None,
    dpi: int = 200,
    page_range: tuple[int, int] | None = None,
) -> list[ExtractedFigure]:
    """Extract all figures from the PDF.

    Handles two types:
    1. Raster images (embedded PNGs/JPEGs) - extracted directly
    2. Vector diagrams (state machines, frame formats) - rendered to PNG
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures: list[ExtractedFigure] = []

    start_page = page_range[0] if page_range else 0
    end_page = page_range[1] if page_range else doc.page_count - 1

    for page_idx in range(start_page, min(end_page + 1, doc.page_count)):
        page = doc[page_idx]

        # Extract raster images
        raster_figs = _extract_raster_images(doc, page, page_idx, output_dir)
        figures.extend(raster_figs)

        # Detect and render vector diagrams
        vector_figs = _extract_vector_diagrams(doc, page, page_idx, output_dir, dpi)
        figures.extend(vector_figs)

    # Assign captions and section numbers
    _assign_captions(doc, figures)
    if sections:
        _assign_sections(figures, sections)

    return figures


def _extract_raster_images(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    page_idx: int,
    output_dir: Path,
) -> list[ExtractedFigure]:
    """Extract embedded raster images from a page."""
    figures = []
    images = page.get_images(full=True)

    for img_idx, img_info in enumerate(images):
        xref = img_info[0]
        width = img_info[2]
        height = img_info[3]

        if width < MIN_IMAGE_SIZE[0] or height < MIN_IMAGE_SIZE[1]:
            continue

        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n > 4:  # CMYK or other
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

            filename = f"raster_p{page_idx:04d}_{img_idx:02d}.png"
            filepath = output_dir / filename
            pix.save(str(filepath))

            figures.append(ExtractedFigure(
                figure_number=None,
                caption="",
                section_number=None,
                image_path=str(filepath.relative_to(output_dir.parent)),
                figure_type="raster",
                page_number=page_idx,
            ))
        except Exception:
            continue

    return figures


def _extract_vector_diagrams(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    page_idx: int,
    output_dir: Path,
    dpi: int,
) -> list[ExtractedFigure]:
    """Detect and render vector diagram regions to PNG.

    Identifies clusters of vector drawings (paths, lines, rects) that
    form diagrams like state machines and frame format illustrations.
    """
    drawings = page.get_drawings()
    if len(drawings) < 5:
        return []

    # Cluster drawings into diagram regions
    regions = _cluster_drawing_regions(drawings, page.rect)
    if not regions:
        return []

    figures = []
    for reg_idx, rect in enumerate(regions):
        # Expand slightly for padding
        padded = pymupdf.Rect(
            rect.x0 - 5, rect.y0 - 5,
            rect.x1 + 5, rect.y1 + 5
        )
        padded.intersect(page.rect)

        # Render the region to a pixmap
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        clip = padded
        pix = page.get_pixmap(matrix=mat, clip=clip)

        filename = f"vector_p{page_idx:04d}_{reg_idx:02d}.png"
        filepath = output_dir / filename
        pix.save(str(filepath))

        # Classify the diagram type based on drawing characteristics
        fig_type = _classify_diagram(drawings, rect)

        figures.append(ExtractedFigure(
            figure_number=None,
            caption="",
            section_number=None,
            image_path=str(filepath.relative_to(output_dir.parent)),
            figure_type=fig_type,
            page_number=page_idx,
        ))

    return figures


def _cluster_drawing_regions(
    drawings: list[dict],
    page_rect: pymupdf.Rect,
) -> list[pymupdf.Rect]:
    """Cluster vector drawings into distinct diagram regions.

    Groups nearby drawings together and filters out small decorative elements
    like page borders and rule lines.
    """
    # Collect bounding boxes of all drawing items
    rects = []
    for d in drawings:
        r = pymupdf.Rect(d["rect"])
        area = r.width * r.height
        # Filter out full-width lines (likely borders/separators)
        if r.width > page_rect.width * 0.9 and r.height < 3:
            continue
        if area < 100:  # tiny decorative elements
            continue
        rects.append(r)

    if not rects:
        return []

    # Merge overlapping/nearby rectangles into clusters
    clusters = _merge_rects(rects, gap_threshold=15)

    # Filter clusters by minimum area
    result = []
    for cluster in clusters:
        area = cluster.width * cluster.height
        if area >= MIN_DRAWING_AREA:
            result.append(cluster)

    return result


def _merge_rects(rects: list[pymupdf.Rect], gap_threshold: float) -> list[pymupdf.Rect]:
    """Merge rectangles that are close to each other."""
    if not rects:
        return []

    # Sort by y position then x
    rects = sorted(rects, key=lambda r: (r.y0, r.x0))

    merged = [pymupdf.Rect(rects[0])]
    for rect in rects[1:]:
        # Check if this rect is close to any existing cluster
        found = False
        for i, cluster in enumerate(merged):
            expanded = pymupdf.Rect(
                cluster.x0 - gap_threshold,
                cluster.y0 - gap_threshold,
                cluster.x1 + gap_threshold,
                cluster.y1 + gap_threshold,
            )
            if expanded.intersects(rect):
                merged[i] = cluster | rect  # union
                found = True
                break
        if not found:
            merged.append(pymupdf.Rect(rect))

    # Iteratively merge until stable
    prev_count = -1
    while len(merged) != prev_count:
        prev_count = len(merged)
        new_merged = []
        used = set()
        for i in range(len(merged)):
            if i in used:
                continue
            current = pymupdf.Rect(merged[i])
            for j in range(i + 1, len(merged)):
                if j in used:
                    continue
                expanded = pymupdf.Rect(
                    current.x0 - gap_threshold,
                    current.y0 - gap_threshold,
                    current.x1 + gap_threshold,
                    current.y1 + gap_threshold,
                )
                if expanded.intersects(merged[j]):
                    current = current | merged[j]
                    used.add(j)
            new_merged.append(current)
            used.add(i)
        merged = new_merged

    return merged


def _classify_diagram(drawings: list[dict], region: pymupdf.Rect) -> str:
    """Classify diagram type based on drawing characteristics."""
    circles = 0
    arrows = 0
    rects_count = 0

    for d in drawings:
        r = pymupdf.Rect(d["rect"])
        if not region.intersects(r):
            continue

        items = d.get("items", [])
        for item in items:
            if item[0] == "c":  # curve (likely circle/ellipse)
                circles += 1
            elif item[0] == "l":  # line
                arrows += 1
            elif item[0] == "re":  # rectangle
                rects_count += 1

    # Heuristic classification
    if circles > 3 and arrows > 3:
        return "state_machine"
    elif rects_count > 5 and arrows > 2:
        return "frame_format"
    elif arrows > 10:
        return "flow_diagram"
    else:
        return "block_diagram"


def _assign_captions(doc: pymupdf.Document, figures: list[ExtractedFigure]) -> None:
    """Find and assign figure captions from page text."""
    # Group figures by page
    by_page: dict[int, list[ExtractedFigure]] = {}
    for fig in figures:
        by_page.setdefault(fig.page_number, []).append(fig)

    caption_pattern = re.compile(
        r'Figure\s+([\w\-–]+)\s*[—\-–:]\s*(.+?)(?:\n|$)'
    )

    for page_idx, page_figs in by_page.items():
        page = doc[page_idx]
        text = page.get_text()
        matches = list(caption_pattern.finditer(text))

        for i, fig in enumerate(page_figs):
            if i < len(matches):
                m = matches[i]
                fig.figure_number = f"Figure {m.group(1)}"
                fig.caption = m.group(2).strip()


def _assign_sections(figures: list[ExtractedFigure], sections: list) -> None:
    """Assign section numbers to figures based on page location."""
    for fig in figures:
        for sec in reversed(sections):
            if hasattr(sec, 'page_start') and sec.page_start <= fig.page_number:
                fig.section_number = sec.section_number
                break
