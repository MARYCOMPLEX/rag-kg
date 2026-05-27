<script setup lang="ts">
import type { ReviewDraftContent } from '../../types/application'
import AppIcon from '../base/AppIcon.vue'

defineProps<{
  draft: ReviewDraftContent
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
      <h1>{{ draft.title }}</h1>
      <div class="draft-metadata">
        <span class="draft-badge">{{ draft.badge }}</span>
        <span v-for="item in draft.metadata" :key="item">{{ item }}</span>
      </div>
    </header>

    <div class="draft-document-body">
      <template v-for="section in draft.sections" :key="section.id">
        <h2>{{ section.heading }}</h2>
        <p v-for="paragraph in section.paragraphs" :key="paragraph.id">
          <template v-for="(segment, index) in paragraph.segments" :key="`${paragraph.id}-${index}`">
            {{ segment.text }}
            <button
              v-if="segment.citation"
              class="draft-citation"
              :class="{ 'is-warning': segment.citation.warning }"
              type="button"
              :aria-label="segment.citation.ariaLabel"
              @click="emit('citation', segment.citation.id)"
            >
              {{ segment.citation.label }}
            </button>
          </template>
          <span v-if="running && paragraph.trailingCaret" class="draft-caret" aria-hidden="true" />
        </p>
      </template>
    </div>

    <footer class="draft-stream-status">
      <span class="drafting-state" :class="{ paused: !running }">
        <AppIcon name="pencil" :size="15" />
        {{ running ? draft.runningLabel : draft.pausedLabel }}
      </span>
      <span>{{ draft.modelLabel }}</span>
      <span>{{ draftTokens }} / {{ draft.tokenLimit }} tokens</span>
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
