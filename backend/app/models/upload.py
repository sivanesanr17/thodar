from pydantic import BaseModel


class UploadMetadata(BaseModel):
    filename: str
    extension: str
    size_bytes: int
    content_type: str | None
    message: str
