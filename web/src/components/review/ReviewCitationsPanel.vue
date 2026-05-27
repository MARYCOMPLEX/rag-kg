<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { ReviewCitation } from '../../types/application'
import AppIcon from '../base/AppIcon.vue'

const props = defineProps<{
  citations: ReviewCitation[]
  selectedId: string
  highlightedId: string
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const citationRows = ref<Record<string, HTMLElement | null>>({})

function bindCitation(id: string, element: unknown) {
  citationRows.value[id] = element instanceof HTMLElement ? element : null
}

watch(() => props.selectedId, async (id) => {
  await nextTick()
  citationRows.value[id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
</script>

<template>
  <aside class="review-citations-panel" aria-label="Live citations">
    <header class="citations-heading">
      <h2>Live Citations ({{ citations.length }})</h2>
    </header>

    <div class="citation-list">
      <p v-if="!citations.length" class="citation-empty">
        No citations loaded.
      </p>

      <button
        v-for="citation in citations"
        :key="citation.id"
        :ref="element => bindCitation(citation.id, element)"
        class="citation-row"
        :class="{
          'is-selected': citation.id === selectedId,
          'is-highlighted': citation.id === highlightedId,
        }"
        type="button"
        :aria-pressed="citation.id === selectedId"
        @click="emit('select', citation.id)"
      >
        <span class="citation-index">{{ citation.id }}</span>
        <span class="citation-content">
          <span class="citation-type">
            {{ citation.type }}
            <b v-if="citation.isNew">New</b>
          </span>
          <span class="citation-author">{{ citation.author }}</span>
        </span>
        <AppIcon class="citation-external" name="external" :size="14" />
      </button>
    </div>

    <footer v-if="citations.length" class="citation-footer">
      <button class="view-all-citations" type="button">
        See all {{ citations.length }} citations
        <AppIcon name="arrow-right" :size="15" />
      </button>
    </footer>
  </aside>
</template>

<style scoped>
.review-citations-panel {
  display: flex;
  flex: 0 0 360px;
  flex-direction: column;
  min-height: 0;
  border-left: 1px solid var(--color-outline-variant);
  background: var(--color-surface);
}

.citations-heading {
  flex: 0 0 auto;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.citations-heading h2 {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 16px;
  text-transform: uppercase;
}

.citation-list {
  display: grid;
  flex: 1 1 auto;
  align-content: start;
  min-height: 0;
  gap: 8px;
  overflow-y: auto;
  padding: 16px;
}

.citation-empty {
  align-self: center;
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  line-height: 20px;
  text-align: center;
}

.citation-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 14px;
  align-items: start;
  gap: 8px;
  min-height: 54px;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  padding: 8px;
  text-align: left;
  transition:
    background var(--motion-duration-normal) var(--motion-ease-standard),
    border-color var(--motion-duration-normal) var(--motion-ease-standard);
}

.citation-row:hover,
.citation-row:focus-visible {
  background: var(--color-surface-container);
}

.citation-row.is-selected {
  border-color: var(--color-primary-fixed);
  background: var(--color-alpha-primary-fixed-26);
}

.citation-row.is-highlighted {
  animation: new-citation-highlight var(--motion-duration-highlight) var(--motion-ease-standard);
}

.citation-index {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-citation);
  border-radius: var(--radius-xs);
  background: var(--color-alpha-citation-10);
  color: var(--color-on-secondary-container);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.citation-content {
  min-width: 0;
}

.citation-type {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.citation-type b {
  border-radius: var(--radius-2xs);
  background: var(--color-primary);
  padding: 1px 4px;
  color: var(--color-on-primary);
  font-family: Inter, sans-serif;
  font-size: 10px;
  font-weight: 700;
  line-height: 12px;
  text-transform: uppercase;
}

.citation-author {
  display: block;
  overflow: hidden;
  color: var(--color-on-surface);
  font-size: 13px;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-row:hover .citation-author,
.citation-row:focus-visible .citation-author {
  color: var(--color-primary);
}

.citation-external {
  align-self: center;
  color: var(--color-on-surface-variant);
  opacity: 0;
  transition: opacity var(--motion-duration-normal) var(--motion-ease-standard);
}

.citation-row:hover .citation-external,
.citation-row:focus-visible .citation-external {
  opacity: 1;
}

.citation-footer {
  flex: 0 0 auto;
  border-top: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.view-all-citations {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  gap: 4px;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
  line-height: 20px;
}

.view-all-citations:hover,
.view-all-citations:focus-visible {
  text-decoration: underline;
}

@keyframes new-citation-highlight {
  0% {
    background: var(--color-primary-fixed);
  }

  100% {
    background: var(--color-alpha-primary-fixed-26);
  }
}
</style>
