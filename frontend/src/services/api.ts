import type { HealthResponse, PdfDetection, UploadMetadata } from '../types/api'

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const maxFileSizeMb = Number(import.meta.env.VITE_MAX_FILE_SIZE_MB ?? 10)

async function readErrorDetail(response: Blob): Promise<string> {
  try {
    const payload = JSON.parse(await response.text()) as { detail?: unknown }
    return typeof payload.detail === 'string' ? payload.detail : ''
  } catch {
    return ''
  }
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`)
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`)
  return response.json() as Promise<HealthResponse>
}

export async function detectPdf(file: File): Promise<PdfDetection> {
  const form = new FormData()
  form.append('file', file)
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/pdf/detect`, { method: 'POST', body: form })
  } catch {
    throw new Error('Could not reach the backend to inspect this PDF. Check that it is running and try again.')
  }
  if (!response.ok) {
    if (response.status === 413) throw new Error(`File exceeds the ${maxFileSizeMb} MB limit.`)
    if (response.status === 415) throw new Error('Unsupported file type. Choose a PDF file.')
    if (response.status === 422) {
      const payload = await response.json().catch(() => ({})) as { detail?: unknown }
      if (typeof payload.detail === 'string') {
        const pageLimit = payload.detail.match(/^This PDF has (\d+) pages; the current limit is (\d+) pages?\.$/)
        if (pageLimit) throw new Error(`This PDF has ${pageLimit[1]} pages. The limit is ${pageLimit[2]} pages.`)
      }
    }
    throw new Error('Unable to inspect this PDF. Check that it is a valid PDF and try again.')
  }
  return response.json() as Promise<PdfDetection>
}

export function uploadDocument(
  file: File,
  onProgress: (progress: number) => void,
): Promise<UploadMetadata> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${apiBaseUrl}/upload`)
    request.responseType = 'json'
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    request.onerror = () => reject(new Error('Could not reach the backend. Check that it is running and try again.'))
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request.response as UploadMetadata)
        return
      }

      const messages: Record<number, string> = {
        400: 'This file is empty or invalid. Choose a valid DOCX or PDF file.',
        413: `File exceeds the ${maxFileSizeMb} MB limit.`,
        415: 'Unsupported file type. Choose a DOCX or PDF file.',
      }
      reject(new Error(messages[request.status] ?? 'Upload failed. Please try again.'))
    }
    const form = new FormData()
    form.append('file', file)
    request.send(form)
  })
}

export type TranslatedDocument = {
  blob: Blob
  filename: string
}

export function translateDocument(
  file: File,
  format: 'docx' | 'pdf',
  sourceLanguage: 'ta' | 'en',
  targetLanguage: 'ta' | 'en',
  onProgress: (progress: number) => void,
): Promise<TranslatedDocument> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${apiBaseUrl}/translate/${format}`)
    request.responseType = 'blob'
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    request.onerror = () => reject(new Error('Could not reach the backend. Check that it is running and try again.'))
    request.onload = async () => {
      if (request.status >= 200 && request.status < 300 && request.response instanceof Blob) {
        const disposition = request.getResponseHeader('Content-Disposition') ?? ''
        const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
        const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
        const filename = encodedName
          ? decodeURIComponent(encodedName)
          : plainName ?? 'translated_document.docx'
        resolve({ blob: request.response, filename })
        return
      }

      const messages: Record<number, string> = {
        400: format === 'pdf' ? 'Unable to read this PDF document.' : 'Unable to translate this DOCX. Check that it contains readable paragraphs.',
        422: format === 'pdf' ? 'Unable to read this PDF confidently. It may be empty, or its scanned text may be unclear.' : 'Unable to translate this document.',
        413: `File exceeds the ${maxFileSizeMb} MB limit.`,
        415: `Unsupported file type. Choose a ${format.toUpperCase()} file.`,
        503: 'Translation service is unavailable or not configured. Check the backend provider settings and try again.',
      }
      if (request.status === 503 && format === 'pdf') {
        const detail = await readErrorDetail(request.response)
        const isOcrError = /tesseract|ocr provider|ocr is not configured/i.test(detail)
        reject(new Error(isOcrError
          ? 'Scanned-PDF OCR is unavailable. Check the backend Tesseract installation and language data.'
          : 'The translation provider is unavailable or misconfigured. Check its API key, model, quota, and backend network connection.'))
        return
      }
      if (request.status === 422 && format === 'pdf') {
        const detail = await readErrorDetail(request.response)
        const pageLimit = detail.match(/^This PDF has (\d+) pages; the current limit is (\d+) pages?\.$/)
        reject(new Error(pageLimit
          ? `This PDF has ${pageLimit[1]} pages. The limit is ${pageLimit[2]} pages.`
          : 'Unable to read this PDF confidently. It may be empty, or its scanned text may be unclear.'))
        return
      }
      reject(new Error(messages[request.status] ?? 'Translation failed. Please try again.'))
    }
    const form = new FormData()
    form.append('file', file)
    form.append('source_language', sourceLanguage)
    form.append('target_language', targetLanguage)
    request.send(form)
  })
}

export const translateDocx = (
  file: File,
  sourceLanguage: 'ta' | 'en',
  targetLanguage: 'ta' | 'en',
  onProgress: (progress: number) => void,
) => translateDocument(file, 'docx', sourceLanguage, targetLanguage, onProgress)

export const translatePdf = (
  file: File,
  sourceLanguage: 'ta' | 'en',
  targetLanguage: 'ta' | 'en',
  onProgress: (progress: number) => void,
) => translateDocument(file, 'pdf', sourceLanguage, targetLanguage, onProgress)
