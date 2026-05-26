<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
const library = useLibraryStore()
const { activeLibrary, featuredLibraries, loading } = storeToRefs(library)

const summaryLine = computed(() => {
  if (loading.value && !featuredLibraries.value.length)
    return 'Loading libraries...'

  const totals = featuredLibraries.value.reduce((result, item) => {
    result.documents += Number(item.documentCountLabel.replace(/,/g, ''))
    result.chunks += Number(item.chunkCountLabel.replace(/,/g, ''))
    result.entities += Number(item.entityCountLabel.replace(/,/g, ''))
    return result
  }, { documents: 0, chunks: 0, entities: 0 })

  return `${featuredLibraries.value.length} active libraries / ${totals.documents.toLocaleString()} documents / ${totals.chunks.toLocaleString()} chunks / ${totals.entities.toLocaleString()} entities`
})

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

    <div class="library-grid">
      <button
        v-for="item in featuredLibraries"
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
