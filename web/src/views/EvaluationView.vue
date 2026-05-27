<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
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
const {
  budgetAlert,
  error,
  filters,
  isEmpty,
  kpis,
  librarySettings,
  selectedDataset,
  selectedTimeRange,
  state,
  summary,
} = storeToRefs(evaluation)
const { activeLibrary, libraries, loading: librariesLoading } = storeToRefs(library)

const activeEvaluationLibraryName = computed(() => {
  const selected = libraries.value.find(item => item.id === activeLibrary.value)
  return selected?.name || activeLibrary.value || 'No library selected'
})
const dashboardQuery = computed(() => ({
  dataset: selectedDataset.value || undefined,
  timeRange: selectedTimeRange.value,
}))

async function selectEvaluationLibrary(event: Event) {
  const target = event.target as HTMLSelectElement
  library.selectLibrary(target.value)
  await goToScreen('eval')
}

function selectDataset(event: Event) {
  const target = event.target as HTMLSelectElement
  evaluation.setDataset(target.value as typeof selectedDataset.value)
}

function selectTimeRange(event: Event) {
  const target = event.target as HTMLSelectElement
  evaluation.setTimeRange(target.value as typeof selectedTimeRange.value)
}

function reloadDashboard() {
  void evaluation.loadDashboard(activeLibrary.value, dashboardQuery.value)
}

watch([activeLibrary, selectedDataset, selectedTimeRange], ([libraryId]) => {
  void evaluation.loadDashboard(libraryId, dashboardQuery.value)
}, { immediate: true })

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
          <p v-if="summary">
            {{ summary.datasetSummaryLabel }} / <strong>{{ summary.timeRangeLabel }}</strong>
            <span v-if="summary.lastRunLabel"> / {{ summary.lastRunLabel }}</span>
          </p>
          <p v-else>Loading dashboard filters and metrics...</p>
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
          <label class="library-filter compact">
            <select :value="selectedDataset" @change="selectDataset">
              <option value="">All datasets</option>
              <option v-for="dataset in filters.datasets" :key="dataset.key" :value="dataset.key">
                {{ dataset.label }} ({{ dataset.count }})
              </option>
            </select>
            <AppIcon name="filter" :size="14" />
          </label>
          <label class="library-filter compact">
            <select :value="selectedTimeRange" @change="selectTimeRange">
              <option v-for="range in filters.timeRanges" :key="range.key" :value="range.key">
                {{ range.label }}
              </option>
            </select>
            <AppIcon name="calendar" :size="14" />
          </label>
        </div>
      </header>

      <div v-if="state === 'loading'" class="evaluation-empty-state" role="status">
        <AppIcon name="info" :size="18" />
        <div>
          <h2>Loading evaluation dashboard</h2>
          <p>Fetching filters, KPI snapshots, trend data, failure cases, and library settings.</p>
        </div>
      </div>

      <div v-else-if="state === 'error'" class="evaluation-empty-state is-error" role="alert">
        <AppIcon name="warning" :size="18" />
        <div>
          <h2>Unable to load evaluation dashboard</h2>
          <p>{{ error }}</p>
          <button type="button" @click="reloadDashboard">Retry</button>
        </div>
      </div>

      <div v-else-if="isEmpty" class="evaluation-empty-state" role="status">
        <AppIcon name="info" :size="18" />
        <div>
          <h2>No evaluation data yet</h2>
          <p>The backend returned an empty dashboard for this library. Run evaluations to populate KPIs and trends.</p>
        </div>
      </div>

      <div v-if="budgetAlert" class="budget-banner" :class="budgetAlert.tone" role="status">
        <span>
          <AppIcon :name="budgetAlert.tone === 'danger' || budgetAlert.tone === 'warning' ? 'warning' : 'info'" :size="16" />
          <strong>{{ budgetAlert.title }}</strong>
          <span>{{ budgetAlert.detail }}</span>
        </span>
        <button v-if="budgetAlert.dismissible" type="button" aria-label="Dismiss budget warning">
          <AppIcon name="close" :size="15" />
        </button>
      </div>

      <div v-if="kpis.length" class="eval-kpi-grid">
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

      <div v-if="state === 'success' && !isEmpty" class="evaluation-main-row">
        <EvalTrendChart />
        <LibrarySettingsPanel
          :library-label="librarySettings?.libraryLabel ?? activeEvaluationLibraryName"
          :settings="librarySettings"
        />
      </div>

      <FailureCaseTable v-if="state === 'success' && !isEmpty" />
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

.library-filter.compact select {
  width: 168px;
}

.library-filter :deep(.app-icon) {
  position: absolute;
  top: 11px;
  right: 10px;
  color: var(--color-on-surface-variant);
  pointer-events: none;
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

.budget-banner.info,
.budget-banner.success {
  border-color: var(--color-alpha-primary-20);
  background: var(--color-primary-fixed);
  color: var(--color-primary);
}

.budget-banner.warning {
  border-color: var(--color-warning-750-exact);
  background: var(--color-warning-50-exact);
  color: var(--color-on-surface);
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
  color: currentcolor;
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

.evaluation-empty-state.is-error :deep(.app-icon),
.evaluation-empty-state.is-error h2 {
  color: var(--color-error);
}

.evaluation-empty-state button {
  width: fit-content;
  height: 32px;
  margin-top: 12px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 14px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
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
