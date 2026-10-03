from fastapi import HTTPException

from app.config import MAX_PAGES


def enforce_pdf_page_limit(page_count: int) -> None:
    if page_count > MAX_PAGES:
        page_label = "page" if MAX_PAGES == 1 else "pages"
        raise HTTPException(
            status_code=422,
            detail=f"This PDF has {page_count} pages; the current limit is {MAX_PAGES} {page_label}.",
        )
