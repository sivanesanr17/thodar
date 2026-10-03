from __future__ import annotations

import csv
import io
import os
import subprocess
from collections import OrderedDict

from app.models.ocr import OcrTextBlock
from app.services.ocr_service import OcrProviderError

OCR_LANGUAGE_CODES = {"ta": "tam", "en": "eng"}


class TesseractOcrProvider:
    """Tesseract CLI adapter that returns line-level OCR text and confidence."""

    def __init__(self, command: str | None = None, timeout_seconds: int = 90):
        self.command = command or os.getenv("TESSERACT_CMD", "tesseract")
        self.timeout_seconds = timeout_seconds
        self._languages: set[str] | None = None

    def _run(self, arguments: list[str], image: bytes | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.command, *arguments],
                input=image,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise OcrProviderError(
                "Tesseract is not installed or TESSERACT_CMD does not point to it."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise OcrProviderError("Tesseract OCR timed out while processing a page.") from exc
        except OSError as exc:
            raise OcrProviderError("Tesseract could not be started.") from exc

    def available_languages(self) -> set[str]:
        if self._languages is not None:
            return self._languages
        result = self._run(["--list-langs"])
        if result.returncode != 0:
            raise OcrProviderError("Unable to read the installed Tesseract language data.")
        output = result.stdout.decode("utf-8", errors="replace")
        self._languages = {
            line.strip()
            for line in output.splitlines()
            if line.strip() and not line.lower().startswith("list of available")
        }
        return self._languages

    def validate_language(self, language: str) -> None:
        tess_language = OCR_LANGUAGE_CODES.get(language)
        if tess_language is None:
            raise OcrProviderError("OCR supports Tamil and English source documents only.")
        if tess_language not in self.available_languages():
            raise OcrProviderError(
                f"Tesseract language data '{tess_language}' is missing. Install it and restart the backend."
            )

    def recognize(self, image: bytes, language: str, page_number: int) -> list[OcrTextBlock]:
        tess_language = OCR_LANGUAGE_CODES.get(language)
        if tess_language is None:
            raise OcrProviderError("OCR supports Tamil and English source documents only.")
        self.validate_language(language)

        # Automatic page segmentation keeps separate paragraphs in their own
        # boxes; PSM 6 often merges an entire scanned legal page into one box.
        result = self._run(["stdin", "stdout", "-l", tess_language, "--psm", "3", "tsv"], image)
        if result.returncode != 0:
            raise OcrProviderError("Tesseract failed to recognize the scanned page.")

        output = result.stdout.decode("utf-8", errors="replace")
        rows = csv.DictReader(io.StringIO(output), delimiter="\t")
        lines: OrderedDict[tuple[str, str, str], dict] = OrderedDict()
        for row in rows:
            if row.get("level") != "5":
                continue
            text = (row.get("text") or "").strip()
            try:
                confidence = float(row.get("conf") or -1)
                left = float(row["left"])
                top = float(row["top"])
                right = left + float(row["width"])
                bottom = top + float(row["height"])
            except (KeyError, TypeError, ValueError):
                continue
            if not text or confidence < 0 or right <= left or bottom <= top:
                continue

            key = (row.get("block_num", ""), row.get("par_num", ""), row.get("line_num", ""))
            line = lines.setdefault(key, {"words": [], "confidences": [], "bbox": [left, top, right, bottom]})
            line["words"].append(text)
            line["confidences"].append(confidence)
            line["bbox"] = [
                min(line["bbox"][0], left), min(line["bbox"][1], top),
                max(line["bbox"][2], right), max(line["bbox"][3], bottom),
            ]

        paragraphs: OrderedDict[tuple[str, str], dict] = OrderedDict()
        for (block_number, paragraph_number, _line_number), line in lines.items():
            paragraph = paragraphs.setdefault(
                (block_number, paragraph_number),
                {"lines": [], "confidences": [], "bbox": list(line["bbox"])},
            )
            paragraph["lines"].append(" ".join(line["words"]))
            paragraph["confidences"].extend(line["confidences"])
            paragraph["bbox"] = [
                min(paragraph["bbox"][0], line["bbox"][0]),
                min(paragraph["bbox"][1], line["bbox"][1]),
                max(paragraph["bbox"][2], line["bbox"][2]),
                max(paragraph["bbox"][3], line["bbox"][3]),
            ]

        blocks: list[OcrTextBlock] = []
        for paragraph in paragraphs.values():
            text = "\n".join(paragraph["lines"]).strip()
            confidence = sum(paragraph["confidences"]) / len(paragraph["confidences"])
            if text:
                blocks.append(OcrTextBlock(text=text, confidence=confidence,
                                           bbox=tuple(paragraph["bbox"]), page=page_number))
        return blocks
