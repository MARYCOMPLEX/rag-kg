<script setup lang="ts">
import { computed } from 'vue'
import type { EvaluationLibrarySettings } from '../../domain/evaluation/types'
import AppIcon from '../base/AppIcon.vue'

const props = defineProps<{
  libraryLabel: string
  settings?: EvaluationLibrarySettings | null
}>()

const fallbackSettings = computed<EvaluationLibrarySettings>(() => ({
  libraryLabel: props.libraryLabel,
  models: {
    routerLabel: 'Router: research-balanced',
    embeddingLabel: 'BAAI/bge-large-en-v1.5 (1024d)',
    warning: 'Changing the embedding model requires a full index rebuild. Currently disabled due to budget limit.',
  },
  budgetLimits: [
    { key: 'llmIn', label: 'LLM in', value: '8,192' },
    { key: 'llmOut', label: 'LLM out', value: '2,048' },
    { key: 'embedTokens', label: 'Embed tkns', value: '16,384' },
    { key: 'rerankDocs', label: 'Rerank docs', value: '40' },
    { key: 'maxHops', label: 'Max hops', value: '3' },
  ],
  dataActions: { canExport: true, canPurge: true },
}))
const resolvedSettings = computed(() => props.settings ?? fallbackSettings.value)
</script>

<template>
  <aside class="library-settings-panel" aria-label="Library settings">
    <header>
      <h2>Library settings</h2>
      <p>{{ resolvedSettings.libraryLabel }} / <i>per-library overrides</i></p>
    </header>

    <div class="settings-body">
      <section class="settings-section">
        <h3>Models</h3>
        <label class="setting-select">
          <select disabled>
            <option>{{ resolvedSettings.models.routerLabel }}</option>
          </select>
          <AppIcon name="chevron" :size="14" />
        </label>
        <label class="setting-select">
          <select disabled>
            <option>{{ resolvedSettings.models.embeddingLabel }}</option>
          </select>
          <AppIcon name="chevron" :size="14" />
        </label>
        <div v-if="resolvedSettings.models.warning" class="settings-warning">
          <AppIcon name="warning" :size="15" />
          <p>{{ resolvedSettings.models.warning }}</p>
        </div>
      </section>

      <section class="settings-section budget-section">
        <h3>
          Budget
          <AppIcon name="settings" :size="14" />
        </h3>
        <div class="budget-grid">
          <label
            v-for="(limit, index) in resolvedSettings.budgetLimits"
            :key="limit.key"
            :class="{ wide: resolvedSettings.budgetLimits.length % 2 === 1 && index === resolvedSettings.budgetLimits.length - 1 }"
          >
            <span>{{ limit.label }}</span>
            <input disabled :value="limit.value">
          </label>
        </div>
      </section>

      <section class="settings-section data-section">
        <h3>Data</h3>
        <button
          class="export-library-button"
          type="button"
          :disabled="resolvedSettings.dataActions?.canExport === false"
        >
          <AppIcon name="download" :size="15" />
          Export Library...
        </button>
        <div class="purge-area">
          <button
            class="purge-library-button"
            type="button"
            :disabled="resolvedSettings.dataActions?.canPurge === false"
          >
            <AppIcon name="trash" :size="15" />
            Purge Library (irreversible)
          </button>
          <p>This will remove all nodes, edges, and chunks from the vector store.</p>
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.library-settings-panel {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  min-width: 336px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
}

.library-settings-panel header {
  border-bottom: 1px solid var(--color-outline-variant);
  background: var(--color-alpha-primary-fixed-26);
  padding: 16px;
}

.library-settings-panel h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.library-settings-panel p {
  margin: 2px 0 0;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  line-height: 20px;
}

.settings-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 24px;
  padding: 16px;
}

.settings-section {
  display: grid;
  gap: 8px;
}

.settings-section h3 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.setting-select {
  position: relative;
  display: block;
}

.setting-select select {
  width: 100%;
  height: 34px;
  appearance: none;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  padding: 0 34px 0 12px;
  color: var(--color-on-surface);
  font-size: 13px;
}

.setting-select :deep(.app-icon) {
  position: absolute;
  top: 10px;
  right: 10px;
  color: var(--color-on-surface-variant);
  pointer-events: none;
}

.settings-warning {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 8px;
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-low);
  padding: 8px;
}

.settings-warning :deep(.app-icon) {
  color: var(--color-outline);
}

.settings-warning p,
.purge-area p {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  line-height: 15px;
}

.budget-section {
  opacity: .6;
}

.budget-section h3 {
  color: var(--color-error);
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.budget-grid label {
  display: grid;
  gap: 2px;
}

.budget-grid label.wide {
  grid-column: 1 / -1;
}

.budget-grid span {
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  line-height: 14px;
  text-transform: uppercase;
}

.budget-grid input {
  height: 30px;
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--radius-xs);
  background: var(--color-surface-container);
  padding: 0 8px;
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}

.data-section {
  margin-top: auto;
}

.export-library-button,
.purge-library-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 36px;
  gap: 6px;
  border-radius: var(--radius-control);
  background: var(--color-surface);
  font-size: 13px;
  font-weight: 500;
}

.export-library-button {
  border: 1px solid var(--color-secondary);
  color: var(--color-secondary);
}

.export-library-button:disabled,
.purge-library-button:disabled {
  opacity: .55;
}

.purge-area {
  display: grid;
  gap: 8px;
  margin-top: 8px;
  border-top: 1px solid var(--color-alpha-outline-variant-72);
  padding-top: 8px;
  text-align: center;
}

.purge-library-button {
  border: 1px solid var(--color-error);
  color: var(--color-error);
}
</style>
