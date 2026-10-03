import logging
import os


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer.") from exc
    if parsed < 1:
        raise RuntimeError(f"{name} must be a positive integer.")
    return parsed


def _frontend_origins() -> list[str]:
    configured = [
        os.getenv("FRONTEND_URL", ""),
        *os.getenv("FRONTEND_URLS", "").split(","),
    ]
    origins = list(dict.fromkeys(value.strip().rstrip("/") for value in configured if value.strip()))
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


MAX_FILE_SIZE_MB = _positive_int("MAX_FILE_SIZE_MB", 10)
MAX_PAGES = _positive_int("MAX_PAGES", 20)
FRONTEND_ORIGINS = _frontend_origins()

_configured_log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_LEVEL = (
    _configured_log_level
    if isinstance(getattr(logging, _configured_log_level, None), int)
    else "INFO"
)
