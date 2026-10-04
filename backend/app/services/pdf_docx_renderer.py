from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from app.models.document import DocumentElement, DocumentPage, StructuredDocument
from app.services.docx_translation import append_translated_text


def _paragraph_alignment(element: DocumentElement, page: DocumentPage) -> WD_ALIGN_PARAGRAPH:
    if element.alignment == "center":
        return WD_ALIGN_PARAGRAPH.CENTER
    if element.alignment == "right":
        return WD_ALIGN_PARAGRAPH.RIGHT
    if element.alignment == "justified":
        return WD_ALIGN_PARAGRAPH.JUSTIFY
    if element.alignment == "unknown":
        x0, _, x1, _ = element.bbox
        left_gap = x0
        right_gap = page.width - x1
        if abs(left_gap - right_gap) <= page.width * 0.035 and (x1 - x0) < page.width * 0.88:
            return WD_ALIGN_PARAGRAPH.CENTER
    return WD_ALIGN_PARAGRAPH.LEFT


def _paragraph_spacing(element: DocumentElement, previous_bottom: float | None) -> float:
    if previous_bottom is None:
        return 0.0
    gap = max(0.0, element.bbox[1] - previous_bottom)
    return min(18.0, max(0.0, (gap - 8.0) * 0.2))


def _ordered_page_elements(page: DocumentPage) -> list[DocumentElement]:
    """Read clear two-column pages down the left column, then the right."""
    elements = [element for element in page.elements if element.type != "image"]
    ordered = sorted(elements, key=lambda item: (item.bbox[1], item.bbox[0]))
    if len(ordered) < 4:
        return ordered

    centers = sorted((element.bbox[0] + element.bbox[2]) / 2 for element in ordered)
    splits = [
        (right - left, (left + right) / 2)
        for left, right in zip(centers, centers[1:])
        if right - left >= page.width * 0.12
    ]
    for _, gutter in sorted(splits, reverse=True):
        left = [element for element in ordered if (element.bbox[0] + element.bbox[2]) / 2 < gutter]
        right = [element for element in ordered if (element.bbox[0] + element.bbox[2]) / 2 >= gutter]
        if len(left) < 2 or len(right) < 2:
            continue
        gap = min(element.bbox[0] for element in right) - max(element.bbox[2] for element in left)
        if gap < page.width * 0.06:
            continue
        if any(element.bbox[0] < gutter < element.bbox[2] for element in ordered):
            continue
        left_top, left_bottom = min(e.bbox[1] for e in left), max(e.bbox[3] for e in left)
        right_top, right_bottom = min(e.bbox[1] for e in right), max(e.bbox[3] for e in right)
        overlap = min(left_bottom, right_bottom) - max(left_top, right_top)
        shorter_column = min(left_bottom - left_top, right_bottom - right_top)
        if shorter_column <= 0 or overlap < shorter_column * 0.3:
            continue
        return sorted(left, key=lambda item: (item.bbox[1], item.bbox[0])) + sorted(
            right, key=lambda item: (item.bbox[1], item.bbox[0])
        )
    return ordered


def render_translated_docx(document: StructuredDocument, output_path: Path,
                           target_language: str) -> None:
    """Write extracted PDF content as ordinary flowing Word paragraphs."""
    output = Document()
    normal = output.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)

    previous_bottom: float | None = None
    previous_page: int | None = None
    for page in document.pages:
        new_source_page = previous_page is not None and page.page_number != previous_page
        if new_source_page:
            previous_bottom = None

        page_elements = _ordered_page_elements(page)
        first_paragraph_on_page = True
        for element in page_elements:
            text = element.translated_text or element.original_text
            if not text.strip() or element.type == "image":
                continue

            paragraph = output.add_paragraph()
            paragraph.alignment = _paragraph_alignment(element, page)
            spacing_before = _paragraph_spacing(element, previous_bottom)
            if new_source_page and first_paragraph_on_page:
                spacing_before = max(spacing_before, 12.0)
            paragraph.paragraph_format.space_before = Pt(spacing_before)
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.line_spacing = 1.15
            if element.type == "heading":
                paragraph.paragraph_format.space_before = Pt(
                    max(8, paragraph.paragraph_format.space_before.pt or 0)
                )

            append_translated_text(paragraph, text)
            for run in paragraph.runs:
                run.font.size = Pt(14 if element.type == "heading" else 11)
                if element.type == "heading":
                    run.bold = True
                elif element.flags is not None:
                    run.bold = bool(element.flags & 16)
                    run.italic = bool(element.flags & 2)

            previous_bottom = element.bbox[3]
            first_paragraph_on_page = False
        previous_page = page.page_number

    output.sections[0].left_margin = Inches(0.8)
    output.sections[0].right_margin = Inches(0.8)
    output.sections[0].top_margin = Inches(0.7)
    output.sections[0].bottom_margin = Inches(0.7)
    output.save(output_path)
