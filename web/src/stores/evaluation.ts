import { computed } from 'vue'
import { defineStore } from 'pinia'
import {
  evaluationFailureCases,
  evaluationKpis,
  evaluationTrend,
  evaluationTrendLegend,
} from '../mocks/evaluation'

export const useEvaluationStore = defineStore('evaluation', () => {
  const kpis = computed(() => evaluationKpis)
  const failureCases = computed(() => evaluationFailureCases)
  const trend = computed(() => evaluationTrend)
  const trendLegend = computed(() => evaluationTrendLegend)

  return {
    kpis,
    failureCases,
    trend,
    trendLegend,
  }
})
