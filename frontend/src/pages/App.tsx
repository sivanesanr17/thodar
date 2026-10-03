import { useEffect, useRef, useState } from 'react'
import { detectPdf, getHealth, translateDocument, type TranslatedDocument } from '../services/api'

type Language = 'Tamil' | 'English'
type ProcessingStage = 'checking-pdf' | 'translating' | null

const maxFileSizeMb = Number(import.meta.env.VITE_MAX_FILE_SIZE_MB ?? 10)
const maxFileSizeBytes = maxFileSizeMb * 1024 * 1024

function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function App() {
  const [translationProvider, setTranslationProvider] = useState<string | null>(null)
  const [sourceLanguage, setSourceLanguage] = useState<Language | ''>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)
  const [processingStage, setProcessingStage] = useState<ProcessingStage>(null)
  const [scannedPdfNotice, setScannedPdfNotice] = useState(false)
  const [translatedFile, setTranslatedFile] = useState<TranslatedDocument | null>(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const targetLanguage: Language | null = sourceLanguage
    ? sourceLanguage === 'Tamil' ? 'English' : 'Tamil'
    : null

  useEffect(() => {
    let active = true
    getHealth()
      .then((health) => {
        if (active) setTranslationProvider(health.translation_provider)
      })
      .catch(() => { if (active) setTranslationProvider(null) })
    return () => { active = false }
  }, [])

  function chooseFile(file?: File) {
    if (!file) return
    setError('')
    setTranslatedFile(null)
    setUploadProgress(null)
    setScannedPdfNotice(false)

    if (!/\.(docx|pdf)$/i.test(file.name)) {
      setSelectedFile(null)
      setError('Unsupported file type. Choose a DOCX or PDF file.')
      return
    }
    if (file.size > maxFileSizeBytes) {
      setSelectedFile(null)
      setError(`File exceeds the ${maxFileSizeMb} MB limit.`)
      return
    }
    setSelectedFile(file)
  }

  async function handleProcess() {
    if (!selectedFile || !sourceLanguage || !targetLanguage || uploading) return
    setUploading(true)
    setError('')
    setUploadProgress(0)
    try {
      const format = selectedFile.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'docx'
      if (format === 'pdf') {
        setProcessingStage('checking-pdf')
        const detection = await detectPdf(selectedFile)
        setScannedPdfNotice(detection.content_type === 'scanned' || detection.content_type === 'mixed')
      }
      setProcessingStage('translating')
      const result = await translateDocument(
        selectedFile,
        format,
        sourceLanguage === 'Tamil' ? 'ta' : 'en',
        targetLanguage === 'Tamil' ? 'ta' : 'en',
        setUploadProgress,
      )
      setTranslatedFile(result)
      setUploadProgress(100)
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed. Please try again.')
      setUploadProgress(null)
    } finally {
      setUploading(false)
      setProcessingStage(null)
    }
  }

  function reset() {
    setSelectedFile(null)
    setUploadProgress(null)
    setTranslatedFile(null)
    setError('')
    setScannedPdfNotice(false)
    if (fileInput.current) fileInput.current.value = ''
  }

  function downloadTranslation() {
    if (!translatedFile) return
    const url = URL.createObjectURL(translatedFile.blob)
    const link = document.createElement('a')
    link.href = url
    link.download = translatedFile.filename
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="Thodar home">
          <span className="brand-mark" aria-hidden="true">த</span>
          <span>thodar<span className="brand-period">.</span></span>
        </a>
      </header>

      <section className="workspace" id="home">
        <div className="intro">
          <p className="eyebrow">DOCUMENT TRANSLATION</p>
          <h1>Documents, translated <span>clearly.</span></h1>
          <p className="subtitle">Choose the language in your file. The app selects the other language for the translation.</p>
        </div>

        <section className="translator-card" aria-label="Translation setup">
          <div className="language-row">
            <label className="language-box">
              <span className="field-label">DOCUMENT LANGUAGE</span>
              <select className="language-select" value={sourceLanguage} disabled={uploading || translatedFile !== null} onChange={(event) => setSourceLanguage(event.target.value as Language | '')}>
                <option value="" disabled>Select the language in your file</option>
                <option value="Tamil">Tamil</option>
                <option value="English">English</option>
              </select>
            </label>
            <div className="language-box" aria-live="polite">
              <span className="field-label">AUTOMATIC OUTPUT</span>
              <span className="language-name">{targetLanguage ?? 'Choose document language'}</span>
            </div>
          </div>

          <div
            className={`upload-area${dragging ? ' upload-area-dragging' : ''}${selectedFile ? ' upload-area-selected' : ''}`}
            onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
            }}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              chooseFile(event.dataTransfer.files[0])
            }}
          >
            <input
              ref={fileInput}
              className="visually-hidden"
              type="file"
              accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => chooseFile(event.target.files?.[0])}
              aria-label="Choose a DOCX or PDF file"
            />
            <div className="document-icon" aria-hidden="true">
              <svg viewBox="0 0 32 32" fill="none"><path d="M9 4.75h9l6 6V26a1.25 1.25 0 0 1-1.25 1.25h-13.5A1.25 1.25 0 0 1 8 26V6a1.25 1.25 0 0 1 1-1.25Z" stroke="currentColor" strokeWidth="1.6"/><path d="M18 5v6h6M12 16h8M12 20h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
            </div>
            {selectedFile ? (
              <>
                <h2>{translatedFile ? 'Translation complete' : 'Document ready'}</h2>
                <p className="selected-file-name">{selectedFile.name}</p>
                <span className="file-note">{formatFileSize(selectedFile.size)} · {selectedFile.name.split('.').pop()?.toUpperCase()}</span>
                {scannedPdfNotice && (
                  <p className="scan-warning" role="status">
                    Scanned PDF detected. OCR converts it into flowing Word text, so spacing, formatting, or alignment may differ from the original.
                  </p>
                )}
                {uploading && uploadProgress !== null && (
                  <div className="progress-wrap" aria-label={`Upload ${uploadProgress}% complete`}>
                    <div className="progress-track"><div className="progress-fill" style={{ width: `${uploadProgress}%` }} /></div>
                    <span>{processingStage === 'checking-pdf' ? 'Checking PDF…' : uploadProgress < 100 ? `${uploadProgress}% uploaded` : uploading ? 'Translating document…' : 'Complete'}</span>
                  </div>
                )}
                {translatedFile && <p className="success-message" role="status">Your translated Word document is ready to download.</p>}
                {!translatedFile && (
                  <div className="action-row">
                    <button className="browse-button" type="button" disabled={uploading || !sourceLanguage} onClick={handleProcess}>
                      {uploading ? (processingStage === 'checking-pdf' ? 'Checking PDF…' : 'Processing…') : `Translate ${selectedFile.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX'}`}
                    </button>
                    <button className="reset-button" type="button" disabled={uploading} onClick={reset}>Reset</button>
                  </div>
                )}
                {translatedFile && <button className="browse-button download-button" type="button" onClick={downloadTranslation}>Download translated DOCX</button>}
                {translatedFile && <button className="reset-button reset-after-success" type="button" onClick={reset}>Translate another file</button>}
              </>
            ) : (
              <>
                <h2>Choose a document to upload</h2>
                <p>Drag and drop your file here, or browse your device.</p>
                <button className="browse-button" type="button" onClick={() => fileInput.current?.click()}>
                  Choose a file <span aria-hidden="true">↗</span>
                </button>
                <span className="file-note">Up to {maxFileSizeMb} MB · DOCX or PDF</span>
              </>
            )}
          </div>

          {error && <p className="error-message" role="alert">{error}</p>}

          <div className="card-footer">
            <span><span className="lock-icon" aria-hidden="true">▣</span> Files are checked and discarded after upload</span>
            <span>Text PDFs · scanned OCR with Tesseract</span>
          </div>
        </section>

        <p className="milestone-note">Milestone 12 · Production configuration · Temporary document processing</p>
      </section>
      {translationProvider === 'gemini' && (
        <aside className="privacy-notice" aria-label="Gemini data use notice">
          <strong>Privacy notice</strong>
          <p>
            Text extracted from your document is sent to Google Gemini for translation. On Google’s unpaid Gemini API tier, submitted content and translations may be used to improve Google products and machine-learning technologies. Do not upload confidential or sensitive documents.{' '}
            <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">Read Google’s Gemini API terms</a>.
          </p>
        </aside>
      )}
      <footer className="page-footer"><span>Implementation built entirely with Codex AI.</span><span>Tamil <i>↔</i> English</span></footer>
    </main>
  )
}
