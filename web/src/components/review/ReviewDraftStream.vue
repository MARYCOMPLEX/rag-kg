<script setup lang="ts">
import AppIcon from '../base/AppIcon.vue'

defineProps<{
  running: boolean
  draftTokens: number
}>()

const emit = defineEmits<{
  citation: [id: string]
}>()
</script>

<template>
  <article class="review-draft-panel" aria-label="Review draft stream" aria-live="polite">
    <header class="draft-document-header">
      <h1>GraphRAG advances<br>2024&ndash;2025</h1>
      <div class="draft-metadata">
        <span>Yue Lin</span>
        <span>May 16 2025</span>
        <span class="draft-badge">Draft</span>
        <span>14,328 tokens</span>
      </div>
    </header>

    <div class="draft-document-body">
      <h2>## 1. Pre-trained models</h2>
      <p>
        Recent advancements in GraphRAG have heavily leveraged large pre-trained models to align unstructured text with structured knowledge graphs
        <button class="draft-citation" type="button" aria-label="Open citation 1" @click="emit('citation', '1')">[1]</button>.
        By embedding both nodes and relationships into high-dimensional vector spaces, systems can perform semantic retrieval over graphs with unprecedented accuracy
        <button class="draft-citation" type="button" aria-label="Open citation 2" @click="emit('citation', '2')">[2]</button>.
        Furthermore, fine-tuning techniques applied to domain-specific corpora have shown significant improvements in reducing hallucination rates
        <button class="draft-citation" type="button" aria-label="Open citation 3" @click="emit('citation', '3')">[3]</button>.
      </p>

      <h2>## 2. Hierarchical KG</h2>
      <p>
        The integration of hierarchical structures within Knowledge Graphs represents a paradigm shift for complex reasoning tasks
        <button class="draft-citation" type="button" aria-label="Open citation 4" @click="emit('citation', '4')">[4]</button>.
        Instead of treating all entities uniformly, modern pipelines segment sub-graphs into distinct abstraction layers. This allows the RAG system to traverse from abstract concepts down to specific facts seamlessly
        <button class="draft-citation" type="button" aria-label="Open citation 5" @click="emit('citation', '5')">[5]</button>.
        Current methodologies emphasize community detection algorithms to generate these hierarchies dynamically during the ingestion phase, which significantly optimizes context window utilization during synthesis
        <button class="draft-citation is-warning" type="button" aria-label="Unsubstantiated citation">[?]</button>
        <span v-if="running" class="draft-caret" aria-hidden="true" />
      </p>
    </div>

    <footer class="draft-stream-status">
      <span class="drafting-state" :class="{ paused: !running }">
        <AppIcon name="pencil" :size="15" />
        {{ running ? 'Drafting subtopic 2' : 'Generation paused' }}
      </span>
      <span>Haiku 4.5</span>
      <span>{{ draftTokens }} / 800 tokens</span>
    </footer>
  </article>
</template>

<style scoped>
.review-draft-panel {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  margin: 16px;
  overflow: hidden;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface);
  box-shadow: var(--shadow-review-draft);
}

.draft-document-header {
  flex: 0 0 auto;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 24px 40px;
}

.draft-document-header h1 {
  margin: 0 0 8px;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 40px;
}

.draft-metadata {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.draft-badge {
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-xs);
  background: var(--color-surface-container);
  padding: 2px 4px;
  color: var(--color-on-surface);
}

.draft-document-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 40px 32px;
  color: var(--color-on-surface);
  font-size: 14px;
  line-height: 22px;
}

.draft-document-body h2 {
  margin: 24px 0 8px;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 28px;
}

.draft-document-body p {
  margin: 0 0 16px;
}

.draft-citation {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  border: 1px solid var(--color-alpha-citation-35);
  border-radius: var(--radius-xs);
  background: var(--color-alpha-citation-10);
  padding: 0 4px;
  color: var(--color-on-secondary-container);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  vertical-align: baseline;
  transition: background var(--motion-duration-normal) var(--motion-ease-standard);
}

.draft-citation:hover,
.draft-citation:focus-visible {
  background: var(--color-alpha-citation-24);
}

.draft-citation.is-warning {
  border-color: var(--color-alpha-danger-20);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
}

.draft-caret {
  display: inline-block;
  width: 8px;
  height: 16px;
  margin-left: 4px;
  background: var(--color-primary);
  vertical-align: middle;
  animation: drafting-caret var(--motion-duration-blink) linear infinite;
}

.draft-stream-status {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-lowest);
  padding: 8px 12px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.drafting-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-primary);
  font-weight: 500;
}

.drafting-state :deep(.app-icon) {
  animation: drafting-caret var(--motion-duration-blink) linear infinite;
}

.drafting-state.paused {
  color: var(--color-outline);
}

.drafting-state.paused :deep(.app-icon) {
  animation: none;
}

@keyframes drafting-caret {
  50% {
    opacity: 0;
  }
}

@media (max-width: 1180px) {
  .draft-document-header,
  .draft-document-body {
    padding-right: 24px;
    padding-left: 24px;
  }

  .draft-document-header h1 {
    font-size: 26px;
    line-height: 34px;
  }
}
</style>
