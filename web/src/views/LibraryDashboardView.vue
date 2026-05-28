<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
const library = useLibraryStore()
const { activeLibrary, error, featuredLibraries, libraries, loading } = storeToRefs(library)

const dashboardLibraries = computed(() => {
  return featuredLibraries.value.length ? featuredLibraries.value : libraries.value
})

const summaryLine = computed(() => {
  if (loading.value && !dashboardLibraries.value.length)
    return 'Loading libraries...'

  if (error.value && !dashboardLibraries.value.length)
    return 'Unable to load libraries.'

  if (!dashboardLibraries.value.length)
    return 'No libraries found.'

  const totals = dashboardLibraries.value.reduce((result, item) => {
    result.documents += Number(item.documentCountLabel.replace(/,/g, ''))
    result.chunks += Number(item.chunkCountLabel.replace(/,/g, ''))
    result.entities += Number(item.entityCountLabel.replace(/,/g, ''))
    return result
  }, { documents: 0, chunks: 0, entities: 0 })

  return `${dashboardLibraries.value.length} active libraries / ${totals.documents.toLocaleString()} documents / ${totals.chunks.toLocaleString()} chunks / ${totals.entities.toLocaleString()} entities`
})

function retryLoadLibraries() {
  void library.loadLibraries(true)
}

onMounted(() => {
  void library.loadLibraries()
})
</script>

<template>
  <section class="screen dashboard-screen">
    <div class="page-head">
      <div>
        <p class="eyebrow">
          Your Libraries
        </p>
        <h1>Your Libraries</h1>
        <p>{{ summaryLine }}</p>
      </div>
      <button class="primary-btn" type="button" @click="ui.openCreateLibrary">
        + New Library
      </button>
    </div>

    <div v-if="error && !dashboardLibraries.length" class="library-state-card is-error">
      <strong>Unable to load libraries</strong>
      <span>{{ error }}</span>
      <button type="button" @click="retryLoadLibraries">
        Retry
      </button>
    </div>

    <div v-else-if="!loading && !dashboardLibraries.length" class="library-state-card">
      <strong>No libraries yet</strong>
      <span>Create a library to start uploading documents and building a graph.</span>
      <button type="button" @click="ui.openCreateLibrary">
        Create library
      </button>
    </div>

    <div v-else class="library-grid">
      <button
        v-for="item in dashboardLibraries"
        :key="item.id"
        class="library-card"
        :class="{ selected: activeLibrary === item.id, 'warning-card': item.status === 'indexing' }"
        type="button"
        @click="library.selectLibrary(item.id)"
      >
        <div class="library-card-head"><span class="card-dot" :class="item.accent" /><strong>{{ item.name }}</strong><span class="card-more">...</span></div>
        <small>{{ item.statusLabel }}</small>
        <div class="metric-grid">
          <span>Documents <b>{{ item.documentCountLabel }}</b></span>
          <span>Chunks <b>{{ item.chunkCountLabel }}</b></span>
          <span>Entities <b>{{ item.entityCountLabel }}</b></span>
          <span>{{ item.activityLabel }}</span>
        </div>
      </button>
      <button class="library-card new-card" type="button" @click="ui.openCreateLibrary">
        <span class="plus">+</span>
        <strong>New Library</strong>
        <small>Create an empty library or import from data source</small>
      </button>
    </div>

    <div class="dashboard-grid">
      <section class="panel wide">
        <div class="panel-title">
          <strong>Recent activity</strong>
          <button type="button">View all logs</button>
        </div>
        <div class="activity-row">
          <span class="file-icon">PDF</span>
          <div><strong>Document ingested</strong><small>Processed "Transformer Models in Medical Imaging.pdf"</small></div>
          <time>12 min ago</time>
        </div>
        <div class="activity-row success">
          <span class="file-icon">KG</span>
          <div><strong>KG extraction completed</strong><small>Batch processing finished for 45 documents.</small></div>
          <time>1h ago</time>
        </div>
        <div class="activity-row warning">
          <span class="file-icon">RUN</span>
          <div><strong>Indexing in progress</strong><small>Building vector index and entity relationships.</small></div>
          <time>active</time>
        </div>
      </section>
      <section class="panel">
        <div class="panel-title">
          <strong>Quality at a glance</strong>
          <button type="button">Open</button>
        </div>
        <div class="quality-line"><span>Healthy libraries</span><b>2 of 3</b></div>
        <div class="quality-line"><span>Avg retrieval quality</span><b>0.72</b></div>
        <div class="quality-line danger-text"><span>Answer citation rate</span><b>79.7%</b></div>
        <div class="quality-line"><span>Orphan entity rate</span><b>5.8%</b></div>
        <div class="quality-line"><span>Index freshness</span><b>2.4h avg</b></div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.library-state-card {
  display: grid;
  max-width: 520px;
  gap: 10px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 18px;
  color: var(--color-on-surface);
}

.library-state-card span {
  color: var(--color-on-surface-variant);
  font-size: 14px;
  line-height: 20px;
}

.library-state-card button {
  justify-self: start;
  height: 36px;
  border: 1px solid var(--color-primary-container);
  border-radius: var(--radius-control);
  background: var(--color-primary-container);
  padding: 0 14px;
  color: var(--color-on-primary);
  font-weight: 700;
}

.library-state-card.is-error {
  border-color: var(--color-alpha-danger-20);
  background: var(--color-error-container);
}

.library-state-card.is-error strong,
.library-state-card.is-error span {
  color: var(--color-error);
}
</style>
