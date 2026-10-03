from __future__ import annotations

import re
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    fitz = None

from app.services.translation_service import TranslationProvider, TranslationUnavailable
from app.models.document import StructuredDocument
from app.services.pdf_layout import extract_pdf_layout
from app.services.pdf_docx_renderer import render_translated_docx
from app.models.pdf_detection import PdfDetectionResult
from app.services.ocr_service import OcrProvider, OcrProviderError
from app.services.pdf_detection import detect_pdf_content
from app.services.pdf_ocr import add_ocr_to_layout

URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
NUMBER_ONLY_PATTERN = re.compile(r"\s*(?:\d+|[ivxlcdm]+)\s*", re.IGNORECASE)


def _eligible(text: str) -> bool:
    return bool(text.strip()) and not NUMBER_ONLY_PATTERN.fullmatch(text.strip()) and not URL_PATTERN.fullmatch(text.strip())


async def translate_pdf_to_file(document: fitz.Document, provider: TranslationProvider,
                                source_language: str, target_language: str,
                                output_path: Path,
                                ocr_provider: OcrProvider | None = None,
                                detection: PdfDetectionResult | None = None) -> int:
    detection = detection or detect_pdf_content(document)
    structured_document = extract_pdf_layout(document)
    if detection.content_type in {"scanned", "mixed"}:
        if ocr_provider is None:
            raise OcrProviderError("OCR provider is not configured.")
        await add_ocr_to_layout(
            document, structured_document, detection, ocr_provider, source_language
        )

    source_texts = [
        element.original_text
        for page in structured_document.pages
        for element in page.elements
        if element.type != "image" and _eligible(element.original_text)
    ]
    if not source_texts:
        raise ValueError("no_extractable_text")
    unique_texts = list(dict.fromkeys(source_texts))
    translations: dict[str, str] = {}
    translate_many = getattr(provider, "translate_many", None)
    if callable(translate_many):
        for start in range(0, len(unique_texts), 8):
            batch = unique_texts[start:start + 8]
            results = await translate_many(batch, source_language, target_language)
            if len(results) != len(batch):
                raise TranslationUnavailable("The translation service returned an incomplete batch.")
            translations.update(zip(batch, results))
    else:
        for text in unique_texts:
            translations[text] = await provider.translate(text, source_language, target_language)

    translated_count = 0
    for page in structured_document.pages:
        for element in page.elements:
            if element.type == "image":
                continue
            element.translated_text = translations.get(element.original_text, element.original_text)
            translated_count += element.original_text in translations
    render_translated_docx(structured_document, output_path, target_language)
    return translated_count
