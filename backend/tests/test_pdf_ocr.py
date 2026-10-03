import asyncio
import unittest

try:
    import pymupdf
    from app.models.ocr import OcrTextBlock
    from app.services.pdf_detection import detect_pdf_content
    from app.services.pdf_layout import extract_pdf_layout
    from app.services.pdf_ocr import add_ocr_to_layout
except ImportError:
    pymupdf = None
    OcrTextBlock = None
    detect_pdf_content = None
    extract_pdf_layout = None
    add_ocr_to_layout = None


class StubOcrProvider:
    def __init__(self, confidence=90):
        self.confidence = confidence

    def recognize(self, image, language, page_number):
        self.image_size = len(image)
        self.language = language
        return [OcrTextBlock(text="Recognized paragraph", confidence=self.confidence,
                             bbox=(100, 200, 300, 240), page=page_number)]


class VariableScaleOcrProvider(StubOcrProvider):
    def recognize(self, image, language, page_number):
        height = 40 * page_number
        return [OcrTextBlock(text="Comparable body text", confidence=90,
                             bbox=(100, 200, 300, 200 + height), page=page_number)]


@unittest.skipIf(pymupdf is None, "PyMuPDF is required for scanned PDF OCR tests")
class PdfOcrLayoutTests(unittest.TestCase):
    def _scanned_document(self):
        document = pymupdf.open()
        page = document.new_page(width=144, height=144)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
        pixmap.clear_with(240)
        page.insert_image(page.rect, stream=pixmap.tobytes("png"))
        return document

    def test_ocr_text_confidence_page_and_bbox_enter_document_model(self):
        document = self._scanned_document()
        layout = extract_pdf_layout(document)
        detection = detect_pdf_content(document)
        provider = StubOcrProvider()

        asyncio.run(add_ocr_to_layout(document, layout, detection, provider, "en"))

        page = layout.pages[0]
        element = next(item for item in page.elements if item.original_text)
        self.assertEqual(element.original_text, "Recognized paragraph")
        self.assertEqual(element.confidence, 90)
        self.assertEqual(element.page, 1)
        for actual, expected in zip(element.bbox, (24, 48, 72, 57.6)):
            self.assertAlmostEqual(actual, expected, places=1)
        self.assertTrue(provider.image_size > 0)
        self.assertEqual(provider.language, "en")
        document.close()

    def test_low_confidence_page_is_rejected(self):
        document = self._scanned_document()
        layout = extract_pdf_layout(document)
        detection = detect_pdf_content(document)

        with self.assertRaisesRegex(ValueError, "low_confidence_ocr"):
            asyncio.run(add_ocr_to_layout(document, layout, detection,
                                          StubOcrProvider(confidence=20), "en"))
        document.close()

    def test_ocr_font_sizes_are_balanced_across_pages(self):
        document = self._scanned_document()
        page = document.new_page(width=144, height=144)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
        pixmap.clear_with(240)
        page.insert_image(page.rect, stream=pixmap.tobytes("png"))
        layout = extract_pdf_layout(document)
        detection = detect_pdf_content(document)

        asyncio.run(add_ocr_to_layout(document, layout, detection,
                                      VariableScaleOcrProvider(), "en"))

        page_sizes = [
            next(item.font_size for item in page.elements if item.original_text)
            for page in layout.pages
        ]
        self.assertAlmostEqual(page_sizes[0], page_sizes[1], places=1)
        document.close()


if __name__ == "__main__":
    unittest.main()
