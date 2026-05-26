import type {
  DocumentDetail,
  DocumentMutationFeedback,
  DocumentsWorkspace,
} from '../../domain/documents/types'
import {
  createMockDocumentsWorkspace,
  createMockRetryFeedback,
  createMockUploadFeedback,
  getMockDocumentDetail,
} from '../../mocks/documents'
import { apiRequest } from '../api/httpClient'

export interface DocumentRepository {
  list(libraryId: string): Promise<DocumentsWorkspace>
  getById(libraryId: string, documentId: string): Promise<DocumentDetail>
  retryIngestion(libraryId: string, documentId: string): Promise<DocumentMutationFeedback>
  queueUpload(libraryId: string): Promise<DocumentMutationFeedback>
}

class MockDocumentRepository implements DocumentRepository {
  async list(libraryId: string) {
    return structuredClone(createMockDocumentsWorkspace(libraryId))
  }

  async getById(libraryId: string, documentId: string) {
    const detail = getMockDocumentDetail(libraryId, documentId)
    if (!detail)
      throw new Error(`Document "${documentId}" was not found.`)

    return structuredClone(detail)
  }

  async retryIngestion(_libraryId: string, _documentId: string) {
    return createMockRetryFeedback()
  }

  async queueUpload(_libraryId: string) {
    return createMockUploadFeedback()
  }
}

class HttpDocumentRepository implements DocumentRepository {
  list(libraryId: string) {
    return apiRequest<DocumentsWorkspace>(`/api/libraries/${encodeURIComponent(libraryId)}/documents`)
  }

  getById(libraryId: string, documentId: string) {
    return apiRequest<DocumentDetail>(
      `/api/libraries/${encodeURIComponent(libraryId)}/documents/${encodeURIComponent(documentId)}`,
    )
  }

  retryIngestion(libraryId: string, documentId: string) {
    return apiRequest<DocumentMutationFeedback>(
      `/api/libraries/${encodeURIComponent(libraryId)}/documents/${encodeURIComponent(documentId)}:retry`,
      { method: 'POST' },
    )
  }

  queueUpload(libraryId: string) {
    return apiRequest<DocumentMutationFeedback>(
      `/api/libraries/${encodeURIComponent(libraryId)}/documents:upload`,
      { method: 'POST' },
    )
  }
}

export function createDocumentRepository(): DocumentRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpDocumentRepository()
    : new MockDocumentRepository()
}
