from __future__ import annotations

import re

import pymupdf

from app.models.pdf_detection import PdfDetectionResult

MIN_TEXT_CHARS_ON_IMAGE_PAGE = 20
IMAGE_DOMINANCE_RATIO = 0.35


def detect_pdf_content(document: pymupdf.Document) -> PdfDetectionResult:
    """Classify a PDF from selectable text and page-sized raster image coverage."""
    text_pages = 0
    scanned_pages = 0
    empty_pages = 0
    scanned_page_numbers: list[int] = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        compact_text = re.sub(r"\s+", "", text)
        page_area = max(1.0, float(page.rect.width * page.rect.height))
        image_area = 0.0
        for image in page.get_image_info():
            bbox = pymupdf.Rect(image["bbox"]) & page.rect
            image_area += max(0.0, bbox.width) * max(0.0, bbox.height)
        image_coverage = min(1.0, image_area / page_area)

        if image_coverage >= IMAGE_DOMINANCE_RATIO and len(compact_text) < MIN_TEXT_CHARS_ON_IMAGE_PAGE:
            scanned_pages += 1
            scanned_page_numbers.append(page_number)
        elif text:
            text_pages += 1
        else:
            empty_pages += 1

    if scanned_pages and text_pages:
        content_type = "mixed"
    elif scanned_pages:
        content_type = "scanned"
    elif text_pages:
        content_type = "text"
    else:
        content_type = "empty"

    return PdfDetectionResult(
        content_type=content_type,
        text_pages=text_pages,
        scanned_pages=scanned_pages,
        empty_pages=empty_pages,
        scanned_page_numbers=scanned_page_numbers,
    )
