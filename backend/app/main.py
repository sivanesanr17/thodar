import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import FRONTEND_ORIGINS, LOG_LEVEL
from app.routes.uploads import router as uploads_router
from app.routes.translations import router as translations_router

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title="Thodar Document Translator API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.include_router(uploads_router)
app.include_router(translations_router)


class HealthResponse(BaseModel):
    status: str
    translation_provider: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    logger.info("Health check requested")
    provider = os.getenv("TRANSLATION_PROVIDER", "gemini").strip().lower()
    return HealthResponse(status="ok", translation_provider=provider)
