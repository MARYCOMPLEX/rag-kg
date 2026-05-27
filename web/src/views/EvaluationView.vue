<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import AppIcon from '../components/base/AppIcon.vue'
import EvalKpiCard from '../components/evaluation/EvalKpiCard.vue'
import EvalTrendChart from '../components/evaluation/EvalTrendChart.vue'
import FailureCaseTable from '../components/evaluation/FailureCaseTable.vue'
import LibrarySettingsPanel from '../components/evaluation/LibrarySettingsPanel.vue'
import { useWorkspaceNavigation } from '../app/useWorkspaceNavigation'
import { useEvaluationStore } from '../stores/evaluation'
import { useLibraryStore } from '../stores/library'

const evaluation = useEvaluationStore()
const library = useLibraryStore()
const { goToScreen } = useWorkspaceNavigation()
const { kpis, usesApiData } = storeToRefs(evaluation)
const { activeLibrary, libraries, loading: librariesLoading } = storeToRefs(library)

const activeEvaluationLibraryName = computed(() => {
  const selected = libraries.value.find(item => item.id === activeLibrary.value)
  return selected?.name || activeLibrary.value || 'No library selected'
})

async function selectEvaluationLibrary(event: Event) {
  const target = event.target as HTMLSelectElement
  library.selectLibrary(target.value)
  await goToScreen('eval')
}

onMounted(() => {
  void library.loadLibraries()
})
</script>

<template>
  <section class="evaluation-workspace">
    <div class="evaluation-content">
      <header class="evaluation-header">
        <div>
          <h1>Evaluation dashboard</h1>
          <p v-if="usesApiData">
            Waiting for <strong>/api/libraries/{libraryId}/evaluation/dashboard</strong>
          </p>
          <p v-else>smoke (10) · multihop (32) · review (5) · <strong>last 30 days</strong></p>
        </div>
        <div class="evaluation-filters">
          <label class="library-filter">
            <select
              :value="activeLibrary"
              :disabled="librariesLoading && !libraries.length"
              @change="selectEvaluationLibrary"
            >
              <option v-if="!libraries.length" value="">
                {{ librariesLoading ? 'Loading libraries...' : 'No libraries available' }}
              </option>
              <option v-for="item in libraries" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
            <AppIcon name="chevron" :size="14" />
          </label>
          <button class="filter-button" type="button">
            <AppIcon name="filter" :size="15" />
            Filter
          </button>
        </div>
      </header>

      <div v-if="usesApiData" class="evaluation-empty-state" role="status">
        <AppIcon name="info" :size="18" />
        <div>
          <h2>No evaluation API contract yet</h2>
          <p>
            API mode hides mock KPIs, trend data, failure cases, budget warnings, and model settings until
            OpenAPI defines the evaluation dashboard response.
          </p>
        </div>
      </div>

      <div v-else class="budget-banner" role="status">
        <span>
          <AppIcon name="warning" :size="16" />
          <strong>Budget Exceeded</strong>
          <span>· LLM limits reached for current billing cycle. Expensive features disabled.</span>
        </span>
        <button type="button" aria-label="Dismiss budget warning">
          <AppIcon name="close" :size="15" />
        </button>
      </div>

      <div v-if="!usesApiData" class="eval-kpi-grid">
        <EvalKpiCard
          v-for="item in kpis"
          :key="item.title"
          :title="item.title"
          :value="item.value"
          :threshold="item.threshold"
          :tone="item.tone"
          :points="item.points"
          :icon="item.icon"
        />
      </div>

      <div v-if="!usesApiData" class="evaluation-main-row">
        <EvalTrendChart />
        <LibrarySettingsPanel :library-label="activeEvaluationLibraryName" />
      </div>

      <FailureCaseTable v-if="!usesApiData" />
    </div>
  </section>
</template>

<style scoped>
.evaluation-workspace {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  background: var(--color-surface);
}

.evaluation-content {
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 100%;
  gap: 24px;
  padding: 24px;
}

.evaluation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.evaluation-header h1 {
  margin: 0;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 28px;
}

.evaluation-header p {
  margin: 4px 0 0;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  line-height: 20px;
}

.evaluation-header strong {
  color: var(--color-on-surface);
  font-weight: 500;
}

.evaluation-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.library-filter {
  position: relative;
  display: block;
}

.library-filter select {
  width: 268px;
  height: 36px;
  appearance: none;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 34px 0 12px;
  color: var(--color-on-surface);
  font-size: 13px;
}

.library-filter :deep(.app-icon) {
  position: absolute;
  top: 11px;
  right: 10px;
  color: var(--color-on-surface-variant);
  pointer-events: none;
}

.filter-button {
  display: inline-flex;
  align-items: center;
  height: 36px;
  gap: 4px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 12px;
  color: var(--color-on-surface);
  font-size: 13px;
  box-shadow: var(--shadow-xs);
}

.budget-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--color-alpha-danger-20);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  padding: 8px 16px;
  color: var(--color-error);
}

.budget-banner span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 13px;
  line-height: 20px;
}

.budget-banner button {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-error);
}

.budget-banner button:hover {
  background: var(--color-alpha-danger-container-28);
}

.evaluation-empty-state {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 12px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 20px;
  color: var(--color-on-surface-variant);
}

.evaluation-empty-state :deep(.app-icon) {
  margin-top: 2px;
  color: var(--color-primary);
}

.evaluation-empty-state h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 15px;
  font-weight: 600;
  line-height: 22px;
}

.evaluation-empty-state p {
  max-width: 720px;
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 20px;
}

.eval-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.evaluation-main-row {
  display: flex;
  align-items: stretch;
  gap: 16px;
}

@media (max-width: 1180px) {
  .eval-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evaluation-main-row {
    flex-direction: column;
  }

  .library-settings-panel {
    min-width: 0;
  }
}
</style>
