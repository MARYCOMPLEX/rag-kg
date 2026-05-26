export type DocumentStatusKind = 'ready' | 'indexing' | 'parsing' | 'failed'
export type DocumentsRequestState = 'idle' | 'loading' | 'success' | 'error'

export interface DocumentStatus {
  kind: DocumentStatusKind
  label: string
  title: string
  message: string
  meta: string
  progress?: number
  progressText?: string
  actionLabel?: string
}

export interface LibraryDocumentsSummary {
  libraryId: string
  documentCountLabel: string
  chunkCountLabel: string
  lastSyncLabel: string
}

export interface LibraryDocument {
  id: string
  libraryId: string
  title: string
  authors: string
  source: string
  year: number
  status: DocumentStatus
  chunks: number | null
  entities: number | null
  ingestedLabel: string
}

export interface DocumentStatistic {
  label: string
  value: string
}

export interface DocumentSection {
  id: string
  orderLabel: string
  title: string
  pageLabel: string
}

export interface DocumentChunk {
  id: string
  locationLabel: string
  text: string
}

export interface DocumentDetail extends LibraryDocument {
  fileFormat: string
  fileSizeLabel: string
  ingestedAtLabel: string
  pageCount: number
  selectedPage: number
  statistics: DocumentStatistic[]
  sections: DocumentSection[]
  chunksPreview: DocumentChunk[]
}

export interface DocumentsWorkspace {
  summary: LibraryDocumentsSummary
  documents: LibraryDocument[]
}

export interface DocumentMutationFeedback {
  tone: 'success' | 'info' | 'warning' | 'danger'
  title: string
  detail: string
  action?: string
}
