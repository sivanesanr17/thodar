import shutil
import subprocess
import unittest
from unittest.mock import patch

try:
    import pymupdf
    from app.services.ocr_service import OcrProviderError
    from app.services.tesseract_ocr import TesseractOcrProvider
except ImportError:
    pymupdf = None
    OcrProviderError = None
    TesseractOcrProvider = None


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


@unittest.skipIf(TesseractOcrProvider is None, "OCR service dependencies are required")
class TesseractOcrTests(unittest.TestCase):
    def test_parses_tamil_paragraph_blocks_and_confidence(self):
        tamil_word = "\u0baa\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1"
        rows = [
            "5\t1\t2\t1\t1\t1\t10\t20\t30\t12\t85.0\tFirst",
            "5\t1\t2\t1\t1\t2\t42\t20\t35\t12\t75.0\tline",
            f"5\t1\t2\t1\t2\t1\t10\t38\t40\t12\t80.0\t{tamil_word}",
        ]
        tsv = (TSV_HEADER + "\n".join(rows) + "\n").encode("utf-8")
        list_languages = subprocess.CompletedProcess([], 0, b"List of available languages (2):\neng\ntam\n", b"")
        recognized = subprocess.CompletedProcess([], 0, tsv, b"")

        with patch("app.services.tesseract_ocr.subprocess.run", side_effect=[list_languages, recognized]) as run:
            blocks = TesseractOcrProvider().recognize(b"image", "ta", 3)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].text, f"First line\n{tamil_word}")
        self.assertEqual(blocks[0].page, 3)
        self.assertEqual(blocks[0].bbox, (10, 20, 77, 50))
        self.assertAlmostEqual(blocks[0].confidence, 80.0)
        self.assertIn("tam", run.call_args_list[1].args[0])
        self.assertIn("--psm", run.call_args_list[1].args[0])
        self.assertIn("3", run.call_args_list[1].args[0])

    def test_reports_missing_tamil_language_data(self):
        available = subprocess.CompletedProcess([], 0, b"List of available languages (1):\neng\n", b"")
        with patch("app.services.tesseract_ocr.subprocess.run", return_value=available):
            with self.assertRaisesRegex(OcrProviderError, "tam.*missing"):
                TesseractOcrProvider().validate_language("ta")

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract executable is not installed")
    def test_real_english_ocr_returns_text_bbox_and_confidence(self):
        provider = TesseractOcrProvider()
        if "eng" not in provider.available_languages():
            self.skipTest("English Tesseract language data is not installed")

        source = pymupdf.open()
        page = source.new_page(width=420, height=300)
        page.insert_textbox((35, 40, 380, 120), "TESSERACT OCR TEST", fontsize=30)
        image = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY, alpha=False).tobytes("png")
        blocks = provider.recognize(image, "en", 1)
        source.close()

        self.assertTrue(blocks)
        self.assertTrue(any("TESSERACT" in block.text.upper() for block in blocks))
        self.assertGreaterEqual(blocks[0].confidence, 40)
        self.assertGreater(blocks[0].bbox[2], blocks[0].bbox[0])


if __name__ == "__main__":
    unittest.main()
