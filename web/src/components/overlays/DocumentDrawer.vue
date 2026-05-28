<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import BaseDrawer from '../base/BaseDrawer.vue'
import AppIcon from '../base/AppIcon.vue'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useDocumentsStore } from '../../stores/documents'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const documents = useDocumentsStore()
const { documentDrawerOpen, drawerPinned } = storeToRefs(ui)
const {
  detailError,
  detailState,
  selectedDocument,
  selectedDocumentId,
} = storeToRefs(documents)
const { focusComposer } = useWorkspaceNavigation()

const drawerOpen = computed(() => documentDrawerOpen.value && Boolean(selectedDocument.value || selectedDocumentId.value))
const drawerTitle = computed(() => selectedDocument.value?.title ?? 'Document detail')
const subtitle = computed(() => {
  const document = selectedDocument.value
  if (!document)
    return ''

  return `${document.authors} / ${document.source} / ${document.fileFormat} / ${document.fileSizeLabel} / Ingested ${document.ingestedAtLabel}`
})
const showDocumentContent = computed(() => detailState.value === 'success' && Boolean(selectedDocument.value))
const showLoadingState = computed(() => detailState.value === 'loading')
const showErrorState = computed(() => detailState.value === 'error')

function updateDrawerShow(show: boolean) {
  ui.documentDrawerOpen = show
  if (!show)
    documents.closeDocument()
}

async function retrySelectedDocument() {
  const document = selectedDocument.value
  if (!document)
    return

  try {
    const feedback = await documents.retryIngestion(document.id)
    ui.pushToast(feedback.tone, feedback.title, feedback.detail, feedback.action)
  }
  catch {
    ui.pushToast('danger', 'Retry failed', 'Unable to restart ingestion for this document.', 'Try again')
  }
}

async function reloadSelectedDocument() {
  const documentId = selectedDocumentId.value
  if (!documentId)
    return

  try {
    await documents.openDocument(documents.libraryId, documentId)
  }
  catch {
    ui.pushToast('danger', 'Document unavailable', 'Unable to load this document detail.', 'Retry')
  }
}
</script>

<template>
  <BaseDrawer
    :show="drawerOpen"
    :title="drawerTitle"
    :subtitle="subtitle"
    size="document"
    :pinned="drawerPinned"
    :dismissible="false"
    close-label="Close document detail drawer"
    @update:show="updateDrawerShow"
  >
    <template #eyebrow>
      <span v-if="selectedDocument" class="document-status-pill" :class="selectedDocument.status.kind">
        <i />
        {{ selectedDocument.status.label }}
      </span>
    </template>

    <template #actions>
      <button v-if="selectedDocument" type="button" title="Download document">
        <AppIcon name="download" :size="15" />
      </button>
      <button v-if="selectedDocument" type="button" title="Re-ingest document" @click="retrySelectedDocument">
        <AppIcon name="refresh" :size="15" />
      </button>
      <button v-if="selectedDocument" type="button" title="Copy citation">
        <AppIcon name="copy" :size="15" />
      </button>
      <button type="button" :aria-pressed="drawerPinned" title="Pin drawer" @click="ui.drawerPinned = !ui.drawerPinned">
        <AppIcon name="pin" :size="15" />
        {{ drawerPinned ? 'Pinned' : 'Pin' }}
      </button>
    </template>

    <section v-if="showLoadingState" class="document-drawer-state" aria-live="polite">
      <strong>Loading document detail...</strong>
      <span>Fetching metadata, sections, and chunk previews from the API.</span>
    </section>

    <section v-else-if="showErrorState" class="document-drawer-state is-error" aria-live="polite">
      <strong>Unable to load document detail.</strong>
      <span>{{ detailError }}</span>
      <button type="button" @click="reloadSelectedDocument">
        Retry
      </button>
    </section>

    <section v-if="showDocumentContent" class="document-stat-row" aria-label="Document statistics">
      <div v-for="stat in selectedDocument?.statistics ?? []" :key="stat.label">
        <strong>{{ stat.value }}</strong>
        <span>{{ stat.label }}</span>
      </div>
    </section>

    <div v-if="showDocumentContent" class="document-drawer-grid">
      <section class="document-preview-column">
        <div class="pdf-preview-card" aria-label="PDF preview">
          <div class="pdf-page">
            <span>PDF preview</span>
            <mark />
          </div>
          <p>Page {{ selectedDocument?.selectedPage }} of {{ selectedDocument?.pageCount }} / selected chunk overlay highlighted</p>
        </div>

        <nav class="document-sections" aria-label="Document sections">
          <h3>Sections / {{ selectedDocument?.sections.length }}</h3>
          <ol>
            <li v-for="section in selectedDocument?.sections ?? []" :key="section.id">
              <button type="button">
                <span>{{ section.orderLabel }}</span>
                <strong>{{ section.title }}</strong>
                <small>{{ section.pageLabel }}</small>
              </button>
            </li>
          </ol>
        </nav>
      </section>

      <section class="document-chunks-column">
        <div class="document-chunks-head">
          <h3>Chunks / showing {{ selectedDocument?.chunksPreview.length }} of {{ selectedDocument?.chunks }}</h3>
          <button type="button">filter by section</button>
        </div>
        <article v-for="chunk in selectedDocument?.chunksPreview ?? []" :key="chunk.id" class="chunk-card">
          <header>
            <code>{{ chunk.id }}</code>
            <span>{{ chunk.locationLabel }}</span>
          </header>
          <p>{{ chunk.text }}</p>
        </article>
      </section>
    </div>

    <template #footer>
      <button v-if="showErrorState" class="drawer-primary-action" type="button" @click="reloadSelectedDocument">
        Retry loading
      </button>
      <button v-if="showDocumentContent" class="drawer-secondary-action" type="button" @click="retrySelectedDocument">
        <AppIcon name="refresh" :size="15" />
        Re-parse
      </button>
      <button v-if="showDocumentContent" class="drawer-primary-action" type="button" @click="focusComposer">
        Open in Chat
        <AppIcon name="arrow-right" :size="15" />
      </button>
      <button v-if="showDocumentContent" class="drawer-danger-action" type="button">
        <AppIcon name="trash" :size="15" />
        Remove document
      </button>
    </template>
  </BaseDrawer>
</template>

<style scoped>
.document-status-pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  gap: 7px;
  border: 1px solid var(--color-alpha-success-35);
  border-radius: var(--radius-pill);
  background: var(--color-success-50-exact);
  padding: 0 10px;
  color: var(--color-success-700-exact);
  font-size: 12px;
  font-weight: 700;
  line-height: 16px;
}

.document-status-pill i {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-pill);
  background: var(--color-success-500-exact);
}

.document-status-pill.failed {
  border-color: var(--color-alpha-danger-20);
  background: var(--color-danger-50-exact);
  color: var(--color-error);
}

.document-status-pill.failed i {
  background: var(--color-error);
}

.document-status-pill.indexing,
.document-status-pill.parsing {
  border-color: var(--color-alpha-primary-container-42);
  background: var(--color-brand-50-exact);
  color: var(--color-primary);
}

.document-status-pill.indexing i,
.document-status-pill.parsing i {
  background: var(--color-primary);
}

.document-stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.document-drawer-state {
  display: grid;
  place-items: center;
  min-height: 320px;
  gap: 8px;
  color: var(--color-on-surface-variant);
  text-align: center;
}

.document-drawer-state strong {
  color: var(--color-on-surface);
  font-size: 16px;
}

.document-drawer-state span {
  max-width: 420px;
  font-size: 13px;
  line-height: 20px;
}

.document-drawer-state button {
  height: 34px;
  margin-top: 8px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 16px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}

.document-drawer-state.is-error span {
  color: var(--color-error);
}

.document-stat-row div {
  display: grid;
  gap: 2px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 12px;
}

.document-stat-row strong {
  color: var(--color-on-surface);
  font-size: 22px;
  line-height: 27px;
}

.document-stat-row span {
  color: var(--color-outline);
  font-size: 12px;
  line-height: 16px;
  text-transform: uppercase;
}

.document-drawer-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 336px;
  gap: 24px;
}

.document-preview-column,
.document-chunks-column {
  display: grid;
  align-content: start;
  gap: 18px;
  min-width: 0;
}

.pdf-preview-card {
  display: grid;
  gap: 10px;
}

.pdf-page {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 408px;
  overflow: hidden;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background:
    linear-gradient(var(--color-surface-container-low), var(--color-surface-container-low)),
    var(--color-surface-container-lowest);
  color: var(--color-outline);
}

.pdf-page span {
  position: relative;
  z-index: var(--z-raised);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}

.pdf-page mark {
  position: absolute;
  top: 34%;
  left: 24%;
  width: 52%;
  height: 72px;
  border: 1px solid var(--color-alpha-citation-35);
  border-radius: var(--radius-card);
  background: var(--color-alpha-citation-16);
}

.pdf-preview-card p {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 12px;
  line-height: 16px;
}

.document-sections h3,
.document-chunks-head h3 {
  margin: 0;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 16px;
  text-transform: uppercase;
}

.document-sections ol {
  display: grid;
  gap: 4px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.document-sections button {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  width: 100%;
  gap: 10px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  padding: 8px;
  text-align: left;
}

.document-sections button:hover {
  background: var(--color-surface-container-low);
}

.document-sections span,
.document-sections small,
.chunk-card code,
.chunk-card header span {
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  line-height: 16px;
}

.document-sections strong {
  overflow: hidden;
  color: var(--color-on-surface);
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-chunks-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.document-chunks-head button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.chunk-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 12px;
}

.chunk-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.chunk-card header span {
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-pill);
  background: var(--color-surface-container-low);
  padding: 2px 8px;
}

.chunk-card p {
  display: -webkit-box;
  overflow: hidden;
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  font-style: italic;
  line-height: 20px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.drawer-secondary-action,
.drawer-primary-action,
.drawer-danger-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  gap: 6px;
  border-radius: var(--radius-control);
  padding: 0 16px;
  font-size: 14px;
  font-weight: 700;
}

.drawer-secondary-action,
.drawer-danger-action {
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-lowest);
}

.drawer-secondary-action {
  color: var(--color-on-surface);
}

.drawer-primary-action {
  min-width: 200px;
  border: 1px solid var(--color-primary-container);
  background: var(--color-primary-container);
  color: var(--color-on-primary);
}

.drawer-danger-action {
  color: var(--color-error);
}

@media (max-width: 900px) {
  .document-drawer-grid,
  .document-stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
