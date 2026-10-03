export type HealthResponse = {
  status: string
  translation_provider: string
}

export type UploadMetadata = {
  filename: string
  extension: string
  size_bytes: number
  content_type: string | null
  message: string
}

export type PdfDetection = {
  content_type: 'text' | 'scanned' | 'mixed' | 'empty'
  text_pages: number
  scanned_pages: number
  empty_pages: number
  scanned_page_numbers: number[]
}
