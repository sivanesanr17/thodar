from __future__ import annotations

import asyncio
import logging
import os
from statistics import median

import pymupdf

from app.models.document import DocumentElement, StructuredDocument
from app.models.pdf_detection import PdfDetectionResult
from app.services.ocr_service import OcrProvider

logger = logging.getLogger(__name__)
OCR_RENDER_DPI = 300
DEFAULT_MIN_CONFIDENCE = 40.0


def _minimum_confidence() -> float:
    try:
        return min(100.0, max(0.0, float(os.getenv("OCR_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE))))
    except ValueError:
        return DEFAULT_MIN_CONFIDENCE


async def add_ocr_to_layout(document: pymupdf.Document,
                            layout: StructuredDocument,
                            detection: PdfDetectionResult,
                            provider: OcrProvider,
                            source_language: str) -> None:
    """OCR only scanned pages and merge accepted blocks into the PDF document model."""
    minimum_confidence = _minimum_confidence()
    scale = 72.0 / OCR_RENDER_DPI
    scanned_page_numbers = set(detection.scanned_page_numbers)
    native_sizes = [
        element.font_size
        for page in layout.pages
        if page.page_number not in scanned_page_numbers
        for element in page.elements
        if element.type != "image" and element.font_size is not None
    ]
    pending: list[tuple[int, object, tuple[float, float, float, float], float]] = []

    for page_number in detection.scanned_page_numbers:
        source_page = document[page_number - 1]
        pixmap = source_page.get_pixmap(dpi=OCR_RENDER_DPI, colorspace=pymupdf.csGRAY, alpha=False)
        recognized = await asyncio.to_thread(
            provider.recognize, pixmap.tobytes("png"), source_language, page_number
        )
        accepted = [block for block in recognized if block.confidence >= minimum_confidence and block.text.strip()]
        if not accepted:
            logger.info("OCR returned no text above %.1f confidence on PDF page %d", minimum_confidence, page_number)
            raise ValueError("low_confidence_ocr")

        page_layout = layout.pages[page_number - 1]
        page_layout.elements = [element for element in page_layout.elements if element.type == "image"]
        for block in accepted:
            x0, y0, x1, y1 = block.bbox
            bbox = (x0 * scale, y0 * scale, x1 * scale, y1 * scale)
            estimated_lines = max(1, len(block.text.splitlines()))
            estimated_size = max(1.0, (bbox[3] - bbox[1]) / estimated_lines)
            pending.append((page_number, block, bbox, estimated_size))

    sizes_by_page = {
        page_number: [size for item_page, _, _, size in pending if item_page == page_number]
        for page_number in detection.scanned_page_numbers
    }
    page_medians = [median(sizes) for sizes in sizes_by_page.values() if sizes]
    reference_size = median(native_sizes) if native_sizes else max(11.0, median(page_medians) if page_medians else 11.0)

    for page_number, block, bbox, estimated_size in pending:
        page_sizes = sizes_by_page[page_number]
        page_median = median(page_sizes) if page_sizes else reference_size
        normalized_size = min(72.0, max(6.0, estimated_size * reference_size / page_median))
        page_layout = layout.pages[page_number - 1]
        looks_like_heading = normalized_size >= reference_size * 1.3 and len(block.text) < 180
        page_layout.elements.append(DocumentElement(
            type="heading" if looks_like_heading else "paragraph",
            original_text=block.text,
            bbox=bbox,
            font_size=normalized_size,
            alignment="unknown",
            page=page_number,
            confidence=block.confidence,
        ))
