from typing import Literal

from pydantic import BaseModel, Field


class DocumentElement(BaseModel):
    type: Literal["heading", "paragraph", "image", "unknown"] = "unknown"
    original_text: str = ""
    translated_text: str | None = None
    bbox: tuple[float, float, float, float]
    font_size: float | None = None
    font_name: str | None = None
    flags: int | None = None
    alignment: Literal["left", "center", "right", "justified", "unknown"] = "unknown"
    page: int = Field(ge=1)
    confidence: float | None = Field(default=None, ge=0, le=100)


class DocumentPage(BaseModel):
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    elements: list[DocumentElement] = Field(default_factory=list)


class StructuredDocument(BaseModel):
    source_format: Literal["docx", "pdf"]
    pages: list[DocumentPage]
