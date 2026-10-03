import os
from typing import Protocol

from app.models.ocr import OcrTextBlock


class OcrProviderError(RuntimeError):
    """Raised when OCR is unavailable or cannot process a rendered page."""


class OcrProvider(Protocol):
    def validate_language(self, language: str) -> None:
        """Fail early if the provider cannot recognize the requested source language."""

    def recognize(self, image: bytes, language: str, page_number: int) -> list[OcrTextBlock]:
        """Recognize one page image and return text blocks with page coordinates."""


def create_ocr_provider() -> OcrProvider:
    provider_name = os.getenv("OCR_PROVIDER", "tesseract").strip().lower()
    if provider_name == "tesseract":
        from app.services.tesseract_ocr import TesseractOcrProvider

        return TesseractOcrProvider()
    raise OcrProviderError(f"Unsupported OCR provider: {provider_name}.")
