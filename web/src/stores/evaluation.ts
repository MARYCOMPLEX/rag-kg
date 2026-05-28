import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { EvaluationDashboardQuery, EvaluationDatasetFilter, EvaluationTimeRangeFilter } from '../domain/evaluation/types'
import { createEvaluationRepository } from '../services/evaluation/evaluationRepository'

const evaluationRepository = createEvaluationRepository()

export const useEvaluationStore = defineStore('evaluation', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const dashboard = ref<Awaited<ReturnType<typeof evaluationRepository.getDashboard>> | null>(null)
  const state = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
  const error = ref<string | null>(null)
  const selectedDataset = ref<EvaluationDatasetFilter['key'] | ''>('')
  const selectedTimeRange = ref<EvaluationTimeRangeFilter['key']>('30d')
  const summary = computed(() => dashboard.value?.summary ?? null)
  const filters = computed(() => dashboard.value?.filters ?? { datasets: [], timeRanges: [] })
  const budgetAlert = computed(() => dashboard.value?.budgetAlert ?? null)
  const kpis = computed(() => dashboard.value?.kpis ?? [])
  const failureCases = computed(() => dashboard.value?.failureCases ?? [])
  const trend = computed(() => dashboard.value?.trend ?? { days: [], em: [], faithfulness: [], citation: [], latency: [], legend: [] })
  const trendLegend = computed(() => trend.value.legend)
  const librarySettings = computed(() => dashboard.value?.librarySettings ?? null)
  const isEmpty = computed(() => state.value === 'success' && kpis.value.length === 0 && failureCases.value.length === 0 && trend.value.days.length === 0)

  async function loadDashboard(libraryId: string, query: EvaluationDashboardQuery = {}) {
    if (!libraryId)
      return

    state.value = 'loading'
    error.value = null

    try {
      dashboard.value = await evaluationRepository.getDashboard(libraryId, query)
      state.value = 'success'
    }
    catch (reason) {
      dashboard.value = null
      error.value = reason instanceof Error ? reason.message : 'Unable to load evaluation dashboard.'
      state.value = 'error'
    }
  }

  function setDataset(dataset: EvaluationDatasetFilter['key'] | '') {
    selectedDataset.value = dataset
  }

  function setTimeRange(timeRange: EvaluationTimeRangeFilter['key']) {
    selectedTimeRange.value = timeRange
  }

  return {
    usesApiData,
    dashboard,
    state,
    error,
    selectedDataset,
    selectedTimeRange,
    summary,
    filters,
    budgetAlert,
    kpis,
    failureCases,
    trend,
    trendLegend,
    librarySettings,
    isEmpty,
    loadDashboard,
    setDataset,
    setTimeRange,
  }
})
