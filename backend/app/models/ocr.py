from pydantic import BaseModel, Field


class OcrTextBlock(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=100)
    bbox: tuple[float, float, float, float]
    page: int = Field(ge=1)
