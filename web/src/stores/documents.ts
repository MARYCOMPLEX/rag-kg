import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  DocumentDetail,
  DocumentMutationFeedback,
  DocumentsRequestState,
  LibraryDocument,
  LibraryDocumentsSummary,
} from '../domain/documents/types'
import { createDocumentRepository } from '../services/documents/documentRepository'

const documentRepository = createDocumentRepository()

export const useDocumentsStore = defineStore('documents', () => {
  const libraryId = ref('')
  const summary = ref<LibraryDocumentsSummary | null>(null)
  const documents = ref<LibraryDocument[]>([])
  const listState = ref<DocumentsRequestState>('idle')
  const listError = ref<string | null>(null)
  const docSelection = ref<string[]>([])
  const selectedDocumentId = ref<string | null>(null)
  const selectedDocument = ref<DocumentDetail | null>(null)
  const detailState = ref<DocumentsRequestState>('idle')
  const detailError = ref<string | null>(null)

  const selectedDocsLabel = computed(() => `${docSelection.value.length} selected`)

  async function loadDocuments(nextLibraryId: string, force = false) {
    if (!force && libraryId.value === nextLibraryId && listState.value === 'success')
      return

    libraryId.value = nextLibraryId
    listState.value = 'loading'
    listError.value = null

    try {
      const workspace = await documentRepository.list(nextLibraryId)
      if (libraryId.value !== nextLibraryId)
        return

      summary.value = workspace.summary
      documents.value = workspace.documents
      listState.value = 'success'
    }
    catch (error) {
      if (libraryId.value !== nextLibraryId)
        return

      listError.value = error instanceof Error ? error.message : 'Unable to load documents.'
      listState.value = 'error'
    }
  }

  async function openDocument(nextLibraryId: string, documentId: string) {
    selectedDocumentId.value = documentId
    detailState.value = 'loading'
    detailError.value = null

    try {
      const detail = await documentRepository.getById(nextLibraryId, documentId)
      if (selectedDocumentId.value !== documentId)
        return

      selectedDocument.value = detail
      detailState.value = 'success'
    }
    catch (error) {
      if (selectedDocumentId.value !== documentId)
        return

      selectedDocument.value = null
      detailError.value = error instanceof Error ? error.message : 'Unable to load document details.'
      detailState.value = 'error'
      throw error
    }
  }

  function closeDocument() {
    selectedDocumentId.value = null
    selectedDocument.value = null
    detailState.value = 'idle'
    detailError.value = null
  }

  async function retryIngestion(documentId: string) {
    return documentRepository.retryIngestion(libraryId.value, documentId)
  }

  async function queueUpload(): Promise<DocumentMutationFeedback> {
    return documentRepository.queueUpload(libraryId.value)
  }

  function toggleDoc(id: string) {
    if (docSelection.value.includes(id))
      docSelection.value = docSelection.value.filter(item => item !== id)
    else
      docSelection.value.push(id)
  }

  function clearSelection() {
    docSelection.value = []
  }

  return {
    libraryId,
    summary,
    documents,
    listState,
    listError,
    docSelection,
    selectedDocumentId,
    selectedDocument,
    detailState,
    detailError,
    selectedDocsLabel,
    loadDocuments,
    openDocument,
    closeDocument,
    retryIngestion,
    queueUpload,
    toggleDoc,
    clearSelection,
  }
})
