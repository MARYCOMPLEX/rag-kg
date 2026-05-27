import { computed } from 'vue'
import { defineStore } from 'pinia'
import {
  evaluationFailureCases,
  evaluationKpis,
  evaluationTrend,
  evaluationTrendLegend,
} from '../mocks/evaluation'

export const useEvaluationStore = defineStore('evaluation', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const kpis = computed(() => usesApiData.value ? [] : evaluationKpis)
  const failureCases = computed(() => usesApiData.value ? [] : evaluationFailureCases)
  const trend = computed(() => usesApiData.value
    ? { days: [], em: [], faithfulness: [], citation: [], latency: [] }
    : evaluationTrend)
  const trendLegend = computed(() => usesApiData.value ? [] : evaluationTrendLegend)

  return {
    usesApiData,
    kpis,
    failureCases,
    trend,
    trendLegend,
  }
})
