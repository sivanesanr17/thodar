from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile

from app.config import MAX_FILE_SIZE_MB

MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    extension: str
    size_bytes: int
    content_type: str | None


async def validate_upload(file: UploadFile, allowed_extensions: set[str]) -> ValidatedUpload:
    original_name = (file.filename or "").replace("\\", "/")
    filename = PurePosixPath(original_name).name
    extension = PurePosixPath(filename).suffix.lower()

    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Choose a file to upload.")
    if extension not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Unsupported file type. Choose a DOCX or PDF file.")
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES[extension]:
        raise HTTPException(status_code=415, detail="The file content does not match a supported DOCX or PDF type.")

    size_bytes = 0
    signature = b""
    try:
        while chunk := await file.read(CHUNK_SIZE):
            if not signature:
                signature = chunk[:8]
            size_bytes += len(chunk)
            if size_bytes > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {MAX_FILE_SIZE_MB} MB limit.",
                )
    finally:
        await file.seek(0)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    if extension == ".pdf" and not signature.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="This file is not a valid PDF.")
    if extension == ".docx" and not signature.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="This file is not a valid DOCX document.")

    return ValidatedUpload(filename, extension, size_bytes, file.content_type)
