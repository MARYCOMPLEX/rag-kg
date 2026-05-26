<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import AppIcon from '../components/base/AppIcon.vue'
import DocumentStatusCell from '../components/documents/DocumentStatusCell.vue'
import type { LibraryDocument } from '../domain/documents/types'
import { useDocumentsStore } from '../stores/documents'
import { useUiStore } from '../stores/ui'

const route = useRoute()
const docs = useDocumentsStore()
const ui = useUiStore()
const {
  summary,
  documents,
  listState,
  listError,
  docSelection,
  selectedDocsLabel,
} = storeToRefs(docs)
const openStatusId = ref<string | null>(null)
const libraryId = computed(() => String(route.params.libraryId ?? 'graphrag-survey'))
const summaryLine = computed(() => {
  const current = summary.value
  if (!current)
    return 'Loading document library...'

  return `${current.documentCountLabel} in ${current.libraryId} / ${current.chunkCountLabel} / ${current.lastSyncLabel}`
})

watch(libraryId, (nextLibraryId) => {
  openStatusId.value = null
  docs.closeDocument()
  ui.documentDrawerOpen = false
  void docs.loadDocuments(nextLibraryId)
}, { immediate: true })

function toggleStatusPopover(documentId: string) {
  openStatusId.value = openStatusId.value === documentId ? null : documentId
}

function closeStatusPopover() {
  openStatusId.value = null
}

async function openDocument(document: LibraryDocument) {
  try {
    await docs.openDocument(libraryId.value, document.id)
    ui.documentDrawerOpen = true
  }
  catch {
    ui.pushToast('danger', 'Document unavailable', 'Unable to load this document detail.', 'Retry')
  }
}

async function retryIngestion(document: LibraryDocument) {
  try {
    const feedback = await docs.retryIngestion(document.id)
    closeStatusPopover()
    ui.pushToast(feedback.tone, feedback.title, feedback.detail, feedback.action)
  }
  catch {
    ui.pushToast('danger', 'Retry failed', 'Unable to restart ingestion for this document.', 'Try again')
  }
}

async function queueUpload() {
  try {
    const feedback = await docs.queueUpload()
    ui.pushToast(feedback.tone, feedback.title, feedback.detail, feedback.action)
  }
  catch {
    ui.pushToast('danger', 'Upload failed', 'Unable to queue documents for ingestion.', 'Try again')
  }
}

function renderCount(value: number | null) {
  return value === null ? '-' : value
}
</script>

<template>
  <section class="screen docs-screen">
    <div class="page-head">
      <div>
        <h1>Documents</h1>
        <p>{{ summaryLine }}</p>
      </div>
      <button class="primary-btn" type="button" @click="queueUpload">
        <AppIcon name="upload" :size="15" />
        Upload PDFs
      </button>
    </div>

    <button class="drop-zone" type="button" @click="queueUpload">
      <AppIcon name="upload" :size="28" />
      <strong>Drag & drop PDFs here, or click to browse</strong>
      <span>Supports scanned PDFs / Auto OCR with MinerU</span>
    </button>

    <div v-if="docSelection.length" class="selection-bar">
      <strong>{{ selectedDocsLabel }}</strong>
      <button type="button">Re-ingest</button>
      <button type="button">Delete</button>
      <button type="button">Export BibTeX</button>
      <button type="button" @click="docs.clearSelection">
        Clear
      </button>
    </div>

    <div class="table-shell">
      <table class="data-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Year</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Entities</th>
            <th>Ingested</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="listState === 'loading'" class="document-state-row">
            <td colspan="6">Loading documents...</td>
          </tr>
          <tr v-else-if="listState === 'error'" class="document-state-row is-error">
            <td colspan="6">{{ listError }}</td>
          </tr>
          <template v-else>
            <tr
              v-for="document in documents"
              :key="document.id"
              :class="{ 'ready-row': document.status.kind === 'ready', 'failed-row': document.status.kind === 'failed' }"
              tabindex="0"
              @click="openDocument(document)"
              @keydown.enter="openDocument(document)"
            >
              <td>{{ document.title }}</td>
              <td>{{ document.year }}</td>
              <DocumentStatusCell
                :document-id="document.id"
                :status="document.status"
                :open="openStatusId === document.id"
                @toggle="toggleStatusPopover"
                @close="closeStatusPopover"
                @action="retryIngestion(document)"
              />
              <td>{{ renderCount(document.chunks) }}</td>
              <td>{{ renderCount(document.entities) }}</td>
              <td>{{ document.ingestedLabel }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div class="ingest-queue-bar">
      <span>Queue</span>
      <b>14 indexing</b>
      <b>3 parsing</b>
      <b class="failed">1 failed</b>
      <span class="daily-cap">Today $0.36 / $5.00 daily cap <i /></span>
    </div>
  </section>
</template>

<style scoped>
.document-state-row td {
  height: 112px;
  color: var(--color-on-surface-variant);
  text-align: center;
}

.document-state-row.is-error td {
  color: var(--color-error);
}
</style>
