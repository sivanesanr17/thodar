from __future__ import annotations

from collections import Counter

import pymupdf

from app.models.document import DocumentElement, DocumentPage, StructuredDocument


def _alignment(bbox: tuple[float, float, float, float], page_width: float) -> str:
    x0, _, x1, _ = bbox
    left_gap = x0
    right_gap = page_width - x1
    block_width = x1 - x0
    if abs(left_gap - right_gap) <= page_width * 0.035 and block_width < page_width * 0.88:
        return "center"
    if right_gap <= page_width * 0.05 and left_gap > page_width * 0.1:
        return "right"
    if left_gap <= page_width * 0.12:
        return "left"
    return "unknown"


def extract_pdf_layout(document: pymupdf.Document) -> StructuredDocument:
    """Extract ordered page elements and basic geometry/style metadata."""
    pages: list[DocumentPage] = []
    for page_index, page in enumerate(document):
        page_width = float(page.rect.width)
        elements: list[DocumentElement] = []
        raw_text_blocks: list[tuple[dict, str, list[dict]]] = []
        font_sizes: list[float] = []
        for block in page.get_text("dict", sort=True)["blocks"]:
            if block.get("type") == 1:
                bbox = tuple(float(value) for value in block["bbox"])
                elements.append(DocumentElement(type="image", bbox=bbox, page=page_index + 1))
                continue
            if block.get("type") != 0:
                continue
            lines = block.get("lines", [])
            spans = [span for line in lines for span in line.get("spans", []) if span.get("text", "").strip()]
            text = "\n".join(
                "".join(span.get("text", "") for span in line.get("spans", []))
                for line in lines
            ).strip()
            if not text or not spans:
                continue
            raw_text_blocks.append((block, text, spans))
            font_sizes.extend(float(span["size"]) for span in spans if span.get("size"))

        median_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 0
        for block, text, spans in raw_text_blocks:
            bbox = tuple(float(value) for value in block["bbox"])
            weighted_sizes = [
                (float(span.get("size", 0)), max(1, len(span.get("text", ""))))
                for span in spans if span.get("size")
            ]
            font_size = (
                sum(size * weight for size, weight in weighted_sizes) / sum(weight for _, weight in weighted_sizes)
                if weighted_sizes else None
            )
            fonts = Counter(span.get("font", "") for span in spans if span.get("font"))
            flags = Counter(int(span.get("flags", 0)) for span in spans)
            looks_like_heading = (
                font_size is not None
                and len(text) < 180
                and (font_size >= 18 or (median_size and font_size >= median_size * 1.25))
            )
            kind = "heading" if looks_like_heading else "paragraph"
            elements.append(DocumentElement(
                type=kind,
                original_text=text,
                bbox=bbox,
                font_size=font_size,
                font_name=fonts.most_common(1)[0][0] if fonts else None,
                flags=flags.most_common(1)[0][0] if flags else None,
                alignment=_alignment(bbox, page_width),
                page=page_index + 1,
            ))

        elements.sort(key=lambda element: (element.bbox[1], element.bbox[0]))
        pages.append(DocumentPage(
            page_number=page_index + 1,
            width=page_width,
            height=float(page.rect.height),
            elements=elements,
        ))
    return StructuredDocument(source_format="pdf", pages=pages)
