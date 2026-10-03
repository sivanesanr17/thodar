from typing import Literal

from pydantic import BaseModel, Field


class PdfDetectionResult(BaseModel):
    content_type: Literal["text", "scanned", "mixed", "empty"]
    text_pages: int = Field(ge=0)
    scanned_pages: int = Field(ge=0)
    empty_pages: int = Field(ge=0)
    scanned_page_numbers: list[int] = Field(default_factory=list)
