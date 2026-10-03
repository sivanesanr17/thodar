# Thodar — Tamil ↔ English Document Translator

Thodar translates Tamil and English DOCX files and PDF documents. PDF uploads return a flowing Word document; scanned pages use Tesseract OCR, and Tamil output uses Bamini encoding.

## Current features

- React, Vite, and TypeScript frontend with Tamil/English selection.
- Drag-and-drop or browse-to-select DOCX/PDF uploads.
- Upload progress, validation messages, and reset.
- Tamil ↔ English DOCX translation and text-based PDF translation.
- FastAPI health, upload, DOCX translation, and PDF translation endpoints.
- Scanned-PDF detection in the UI with a notice that OCR output can differ in spacing and alignment.
- Temporary file processing and cleanup after the response.

## Requirements

- Node.js 20 or newer
- Python 3.10 or newer
- Backend dependencies from `backend/requirements.txt`, including PyMuPDF for PDF processing
- Tesseract OCR installed locally, with `eng` and `tam` language data. See the [official Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html) and [language data list](https://tesseract-ocr.github.io/tessdoc/Data-Files.html).
- A Gemini API key from Google AI Studio (free-tier limits apply), an Azure Translator resource, or a local Ollama installation

## Translation provider setup

Gemini is the default provider. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey), then add it to the backend environment. The Gemini API has a free tier for selected models with account-specific rate limits. Google states that free-tier content may be used to improve its products, so don't send sensitive documents using that tier. See the [API key guide](https://ai.google.dev/gemini-api/docs/api-key) and [pricing and data-use terms](https://ai.google.dev/gemini-api/docs/pricing).

Azure Translator and Ollama remain available as alternatives by setting `TRANSLATION_PROVIDER=azure` or `TRANSLATION_PROVIDER=ollama` and supplying their respective configuration. Provider code is isolated behind `backend/app/services/translation_service.py`.

## Run locally

Start the backend in one terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --env-file ../.env --port 8000
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. The frontend checks the backend connection on load.

## Configuration

Copy `.env.example` to the project root as `.env`, or set the values in the shell before starting Uvicorn:

```dotenv
TRANSLATION_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-3.5-flash-lite
MAX_FILE_SIZE_MB=10
MAX_PAGES=20
FRONTEND_URL=http://localhost:5173
FRONTEND_URLS=https://your-app.vercel.app
LOG_LEVEL=INFO
OCR_PROVIDER=tesseract
TESSERACT_CMD=tesseract
OCR_MIN_CONFIDENCE=40
```

Keep the Gemini key in the backend environment only. The default model can be changed with `GEMINI_MODEL`. To use Azure, set `TRANSLATION_PROVIDER=azure`, `TRANSLATION_API_KEY`, and any required Azure region. To use local Ollama, set `TRANSLATION_PROVIDER=ollama`, `TRANSLATION_API_URL=http://localhost:11434`, and `TRANSLATION_MODEL=qwen3:4b`.

Set `VITE_API_URL` and optionally `VITE_MAX_FILE_SIZE_MB` in `frontend/.env.local` to configure the frontend. Restart Vite after changing frontend environment variables.

The backend allows the browser origin in `FRONTEND_URL` and optional comma-separated `FRONTEND_URLS`. Set these to the exact local or hosted frontend origins. `MAX_FILE_SIZE_MB` limits incoming uploads, `MAX_PAGES` limits PDF page count, and `LOG_LEVEL` controls backend logging.

## API

### `GET /health`

Returns `{"status":"ok","translation_provider":"gemini"}` when the backend is running. The provider field lets the UI show provider-specific data-use information.

### `POST /upload`

Accepts a multipart `file` field. DOCX/PDF type, signature, and upload size are validated; the endpoint returns filename, size, and MIME metadata.

### `POST /pdf/detect`

Accepts a multipart PDF `file` and returns whether its pages contain selectable text, scanned images, mixed content, or no content. The frontend uses this result to warn about OCR alignment differences before translation. PDFs above `MAX_PAGES` are rejected.

### `POST /translate/docx`

Accepts multipart fields `file`, `source_language` (`ta` or `en`), and `target_language` (`ta` or `en`). It returns a DOCX attachment named after the original file with `_translated` appended. The endpoint rejects identical source and target languages, invalid/empty documents, oversized files, and unavailable translation providers with useful HTTP errors.

### `POST /translate/pdf`

Accepts the same multipart fields with a PDF as input and always returns a translated DOCX attachment. Scanned and mixed PDFs are rendered page-by-page for OCR. The DOCX contains ordinary flowing paragraphs with line breaks and modest paragraph spacing; it does not embed the page images or use fixed-position text boxes. Pages with no recognized text above the configured confidence threshold return HTTP 422; missing Tesseract or language data returns HTTP 503.

## DOCX translation behavior

- Translates complete non-empty paragraphs, including paragraphs in tables, headers, and footers.
- Reuses translations for repeated identical text within one document.
- Sends distinct paragraphs in small batches to Gemini, reducing API request count and helping avoid per-minute free-tier throttling.
- Skips page-number fields, numeric-only paragraphs, code-like paragraphs, and URL content. URLs inside other text are protected and restored.
- Keeps paragraph, table, and page structure. Translated text is distributed across existing runs so run-level bold, italic, underline, and font properties remain attached.

## PDF translation behavior

- Detects text, scanned, mixed, and empty PDFs using selectable text and page-sized image coverage.
- Extracts selectable text blocks with bounding boxes, translates blocks as units, and caches repeated text within the document.
- Sorts extracted/OCR text into reading order and creates a reflowable Word document with readable paragraph spacing and line breaks.
- Tamil output is converted to Bamini legacy character encoding and uses the Bamini font. The receiving computer needs a Bamini font installed.
- Scanned pages are rendered one at a time and passed to the provider-independent OCR interface. Tesseract uses automatic page segmentation and returns paragraph text, confidence, page number, and bounding boxes.
- Low-confidence OCR blocks are excluded; if a scanned page has no confident text, the request fails instead of translating uncertain text.

Bamini is a legacy font encoding, so the DOCX stores its Tamil text in Bamini character codes. The receiving computer needs the Bamini font installed. The conversion mapping is based on the [MIT-licensed Unicode-to-Bamini converter](https://github.com/Pakeetharan/unicode-bamini-converter).

## OCR pipeline

- The OCR provider is selected through `OCR_PROVIDER` and isolated behind `app/services/ocr_service.py`. The selected source language chooses Tesseract `eng` or `tam` recognition data.
- Set `TESSERACT_CMD` when the executable is not named `tesseract`; set `TESSDATA_PREFIX` to the tessdata directory when it is outside the default location.
- Set `OCR_MIN_CONFIDENCE` to tune the minimum accepted block confidence (default 40).
- The local development machine currently has English data only. Install `tam.traineddata` in Tesseract?s `tessdata` directory (or set `TESSDATA_PREFIX`) before processing Tamil scans; the backend reports a clear configuration error when it is missing.
- OCR text is translated into a flowing DOCX. Original scan images and backgrounds are not embedded in the DOCX.

## Current limitations

- Gemini free-tier quotas are limited and can change; its free-tier data-use terms may not suit sensitive documents.
- Hosted Azure translation requires a configured Azure Translator resource and key; the free F0 quota is limited and provider terms can change.
- The local Ollama alternative requires the configured model to be downloaded and running; it may need several GB of disk space and suitable RAM.
- PDF input produces a flowing DOCX and does not carry over original PDF images or backgrounds. OCR accuracy depends on scan quality and installed language data; spacing or alignment can differ from the scan.
- When translation changes sentence structure, formatting runs are assigned proportionally to translated text; bold or italic spans may not cover exactly the same semantic words as the source.

## Tests

From `backend/`, run the service tests with `python -m unittest discover -s tests`. These use a stub translation provider and do not need Ollama.

## Next milestone

Milestone 13 prepares the repository and README for deployment. Fixed-position page reconstruction is intentionally out of scope.
