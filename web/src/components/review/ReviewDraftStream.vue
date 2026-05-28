<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewDraft } from '../../domain/review/types'
import AppIcon from '../base/AppIcon.vue'

const props = defineProps<{
  draft: ReviewDraft
  running: boolean
  draftTokens: number
}>()

const emit = defineEmits<{
  citation: [id: string]
}>()

const authorLabel = computed(() => Array.isArray(props.draft.authors) ? props.draft.authors.join(', ') : props.draft.authors)
</script>

<template>
  <article class="review-draft-panel" aria-label="Review draft stream" aria-live="polite">
    <header class="draft-document-header">
      <h1>{{ draft.title }}</h1>
      <div class="draft-metadata">
        <span class="draft-badge">{{ draft.badgeLabel }}</span>
        <span>{{ authorLabel }}</span>
        <span>{{ draft.generatedAtLabel }}</span>
        <span>{{ draft.totalTokensLabel }}</span>
      </div>
    </header>

    <div class="draft-document-body">
      <section v-for="section in draft.sections" :key="section.id" class="draft-section">
        <h2>{{ section.heading }}</h2>
        <p class="draft-markdown">
          {{ section.markdown }}
        </p>
        <div v-if="section.citations.length" class="draft-citation-row">
          <button
            v-for="citationId in section.citations"
            :key="`${section.id}-${citationId}`"
            class="draft-citation"
            :class="{ 'is-warning': section.unsubstantiated }"
            type="button"
            :aria-label="`Open citation ${citationId}`"
            @click="emit('citation', citationId)"
          >
            [{{ citationId }}]
          </button>
        </div>
        <p v-if="section.unsubstantiated" class="draft-warning">
          Unsubstantiated content flagged in this section.
        </p>
      </section>

      <div v-if="!draft.sections.length" class="draft-empty">
        No draft sections yet.
      </div>
    </div>

    <footer class="draft-stream-status">
      <span class="drafting-state" :class="{ paused: !running }">
        <AppIcon name="pencil" :size="15" />
        {{ draft.statusLabel }}
      </span>
      <span>{{ draft.modelLabel }}</span>
      <span>{{ draftTokens }} / {{ draft.draftTokenLimit }} tokens</span>
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
  white-space: pre-line;
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

.draft-section + .draft-section {
  margin-top: 24px;
}

.draft-document-body h2 {
  margin: 0 0 8px;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 28px;
}

.draft-markdown {
  margin: 0;
  white-space: pre-wrap;
}

.draft-citation-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.draft-citation {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-alpha-citation-35);
  border-radius: var(--radius-xs);
  background: var(--color-alpha-citation-10);
  padding: 0 6px;
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

.draft-warning {
  margin: 8px 0 0;
  color: var(--color-error);
  font-size: 12px;
  line-height: 18px;
}

.draft-empty {
  border: 1px dashed var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 16px;
  color: var(--color-on-surface-variant);
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
