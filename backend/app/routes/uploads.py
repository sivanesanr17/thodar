import logging
from fastapi import APIRouter, File, UploadFile, status

from app.models.upload import UploadMetadata
from app.utils.uploads import validate_upload

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".docx", ".pdf"}


@router.post("/upload", response_model=UploadMetadata, status_code=status.HTTP_200_OK)
async def upload_document(file: UploadFile = File(...)) -> UploadMetadata:
    """Validate an upload and return metadata without retaining its contents."""
    try:
        upload = await validate_upload(file, ALLOWED_EXTENSIONS)
    finally:
        await file.close()
    logger.info("Accepted %s upload (%d bytes)", upload.extension, upload.size_bytes)
    return UploadMetadata(
        filename=upload.filename,
        extension=upload.extension,
        size_bytes=upload.size_bytes,
        content_type=upload.content_type,
        message="Upload received. DOCX and PDF translation are available.",
    )
