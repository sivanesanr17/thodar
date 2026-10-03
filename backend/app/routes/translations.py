import logging
import re
import tempfile
import shutil
from pathlib import Path, PurePosixPath
from typing import Literal

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.models.pdf_detection import PdfDetectionResult
from app.services.docx_translation import translate_docx
from app.services.pdf_translation import translate_pdf_to_file
from app.services.pdf_detection import detect_pdf_content
from app.services.ocr_service import OcrProviderError, create_ocr_provider
from app.services.translation_service import (
    TranslationConfigurationError,
    TranslationUnavailable,
    create_translation_provider,
)
from app.utils.pdf_limits import enforce_pdf_page_limit
from app.utils.uploads import validate_upload

logger = logging.getLogger(__name__)
router = APIRouter()
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _output_filename(original_filename: str | None) -> str:
    stem = PurePosixPath((original_filename or "document.docx").replace("\\", "/")).stem
    safe_stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._")[:100] or "document"
    return f"{safe_stem}_translated.docx"


def _translated_filename(original_filename: str | None, extension: str) -> str:
    stem = PurePosixPath((original_filename or f"document{extension}").replace("\\", "/")).stem
    safe_stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._")[:100] or "document"
    return f"{safe_stem}_translated{extension}"


@router.post("/pdf/detect", response_model=PdfDetectionResult)
async def detect_pdf_file(file: UploadFile = File(...)) -> PdfDetectionResult:
    """Classify a PDF so the UI can warn before processing scanned pages."""
    try:
        await validate_upload(file, {".pdf"})
        try:
            import pymupdf as fitz
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="PDF detection dependencies are missing. Install backend requirements and restart the server.",
            ) from exc

        try:
            pdf_bytes = await file.read()
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            logger.info("Could not inspect uploaded PDF (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Unable to read this PDF document.") from exc

        try:
            enforce_pdf_page_limit(len(document))
            return detect_pdf_content(document)
        finally:
            document.close()
    finally:
        await file.close()


@router.post("/translate/docx")
async def translate_docx_file(
    file: UploadFile = File(...),
    source_language: Literal["ta", "en"] = Form(...),
    target_language: Literal["ta", "en"] = Form(...),
) -> FileResponse:
    if source_language == target_language:
        await file.close()
        raise HTTPException(status_code=400, detail="Choose two different languages to translate.")

    output_path: Path | None = None
    response_created = False
    try:
        upload = await validate_upload(file, {".docx"})
        try:
            from docx import Document
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="DOCX translation dependencies are missing. Install backend requirements and restart the server.",
            ) from exc
        try:
            document = Document(file.file)
        except Exception as exc:
            logger.info("Could not parse uploaded DOCX (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Unable to read this DOCX document.") from exc

        with tempfile.NamedTemporaryFile(prefix="thodar-", suffix=".docx", delete=False) as output_file:
            output_path = Path(output_file.name)

        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            provider = create_translation_provider(client)
            translated_count = await translate_docx(
                document, provider, source_language, target_language
            )

        if translated_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No translatable paragraphs were found. The DOCX may be empty or contain only links and page numbers.",
            )

        document.save(output_path)
        logger.info(
            "Translated %d DOCX text blocks from %s to %s",
            translated_count,
            source_language,
            target_language,
        )
        response = FileResponse(
            output_path,
            media_type=DOCX_MEDIA_TYPE,
            filename=_output_filename(upload.filename),
            background=BackgroundTask(output_path.unlink, missing_ok=True),
        )
        response_created = True
        return response
    except TranslationConfigurationError as exc:
        logger.error("Translation is not configured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TranslationUnavailable as exc:
        logger.warning("DOCX translation provider unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await file.close()
        if not response_created and output_path is not None and output_path.exists():
            output_path.unlink(missing_ok=True)


@router.post("/translate/pdf")
async def translate_pdf_file(
    file: UploadFile = File(...),
    source_language: Literal["ta", "en"] = Form(...),
    target_language: Literal["ta", "en"] = Form(...),
) -> FileResponse:
    if source_language == target_language:
        await file.close()
        raise HTTPException(status_code=400, detail="Choose two different languages to translate.")

    input_path: Path | None = None
    output_path: Path | None = None
    response_created = False
    document = None
    try:
        upload = await validate_upload(file, {".pdf"})
        with tempfile.NamedTemporaryFile(prefix="thodar-input-", suffix=".pdf", delete=False) as temp_input:
            input_path = Path(temp_input.name)
            shutil.copyfileobj(file.file, temp_input)
        with tempfile.NamedTemporaryFile(prefix="thodar-output-", suffix=".pdf", delete=False) as temp_output:
            output_path = Path(temp_output.name)

        try:
            import pymupdf as fitz
            document = fitz.open(input_path)
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="PDF translation dependencies are missing. Install backend requirements and restart the server.") from exc
        except Exception as exc:
            logger.info("Could not parse uploaded PDF (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Unable to read this PDF document.") from exc

        enforce_pdf_page_limit(len(document))
        detection = detect_pdf_content(document)
        if detection.content_type == "empty":
            raise HTTPException(status_code=422, detail="Unable to extract text from this PDF.")

        ocr_provider = None
        if detection.content_type in {"scanned", "mixed"}:
            try:
                ocr_provider = create_ocr_provider()
            except OcrProviderError as exc:
                raise HTTPException(status_code=503, detail="OCR is not configured for this server.") from exc
            try:
                ocr_provider.validate_language(source_language)
            except OcrProviderError as exc:
                logger.warning("OCR is not configured for source language %s", source_language)
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            provider = create_translation_provider(client)
            try:
                translated_count = await translate_pdf_to_file(
                    document, provider, source_language, target_language, output_path,
                    ocr_provider=ocr_provider,
                    detection=detection,
                )
            except OcrProviderError as exc:
                logger.warning("PDF OCR is unavailable or failed (%s)", type(exc).__name__)
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ValueError as exc:
                if str(exc) == "no_extractable_text":
                    raise HTTPException(status_code=422, detail="Unable to extract text from this PDF. It may be scanned or image-only; OCR support is planned next.") from exc
                if str(exc) == "low_confidence_ocr":
                    raise HTTPException(status_code=422, detail="OCR could not recognize text confidently on one or more pages. Use a clearer scan and try again.") from exc
                raise
            except TranslationUnavailable:
                raise
            except Exception as exc:
                logger.warning("Could not create translated DOCX from PDF (%s)", type(exc).__name__)
                raise HTTPException(status_code=422, detail="Unable to create a Word document from this PDF. Try a simpler text-based PDF.") from exc

        if translated_count == 0:
            raise HTTPException(status_code=422, detail="No translatable text blocks were found in this PDF.")
        logger.info("Translated %d PDF text blocks from %s to %s", translated_count, source_language, target_language)
        response = FileResponse(
            output_path,
            media_type=DOCX_MEDIA_TYPE,
            filename=_translated_filename(upload.filename, ".docx"),
            background=BackgroundTask(output_path.unlink, missing_ok=True),
        )
        response_created = True
        return response
    except TranslationConfigurationError as exc:
        logger.error("Translation is not configured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TranslationUnavailable as exc:
        logger.warning("PDF translation provider unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await file.close()
        if document is not None:
            document.close()
        if input_path is not None:
            input_path.unlink(missing_ok=True)
        if not response_created and output_path is not None:
            output_path.unlink(missing_ok=True)
