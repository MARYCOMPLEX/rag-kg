import type {
  EvaluationDashboard,
  EvaluationDashboardQuery,
  EvaluationDatasetFilter,
  EvaluationTrendLegendItem,
  EvaluationTimeRangeFilter,
} from '../../domain/evaluation/types'
import {
  evaluationFailureCases,
  evaluationKpis,
  evaluationTrend,
  evaluationTrendLegend,
} from '../../mocks/evaluation'
import { apiRequest } from '../api/httpClient'

export interface EvaluationRepository {
  getDashboard(libraryId: string, query?: EvaluationDashboardQuery): Promise<EvaluationDashboard>
}

class MockEvaluationRepository implements EvaluationRepository {
  async getDashboard(libraryId: string, query: EvaluationDashboardQuery = {}): Promise<EvaluationDashboard> {
    const datasets: EvaluationDatasetFilter[] = [
      { key: 'smoke', label: 'Smoke', count: 10, active: query.dataset === 'smoke' },
      { key: 'multihop', label: 'Multihop', count: 32, active: query.dataset === 'multihop' },
      { key: 'review', label: 'Review', count: 5, active: query.dataset === 'review' },
    ]
    const timeRanges: EvaluationTimeRangeFilter[] = [
      { key: '7d', label: '7D', active: query.timeRange === '7d' },
      { key: '30d', label: '30D', active: !query.timeRange || query.timeRange === '30d' },
      { key: '90d', label: '90D', active: query.timeRange === '90d' },
    ]
    const legend = evaluationTrendLegend as EvaluationTrendLegendItem[]

    return {
      summary: {
        libraryId,
        libraryName: libraryId || 'Mock Library',
        datasetSummaryLabel: 'smoke (10) / multihop (32) / review (5)',
        timeRangeLabel: query.timeRange === '7d' ? 'Last 7 days' : query.timeRange === '90d' ? 'Last 90 days' : 'Last 30 days',
        lastRunLabel: 'Mock evaluation run',
      },
      filters: {
        datasets,
        timeRanges,
      },
      budgetAlert: {
        tone: 'danger',
        title: 'Budget Exceeded',
        detail: 'LLM limits reached for current billing cycle. Expensive features disabled.',
        dismissible: true,
      },
      kpis: evaluationKpis,
      trend: {
        ...evaluationTrend,
        legend,
      },
      failureCases: evaluationFailureCases,
      librarySettings: {
        libraryLabel: libraryId || 'Mock Library',
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
      },
    }
  }
}

class HttpEvaluationRepository implements EvaluationRepository {
  getDashboard(libraryId: string, query: EvaluationDashboardQuery = {}) {
    return apiRequest<EvaluationDashboard>(
      `/api/libraries/${encodeURIComponent(libraryId)}/evaluation/dashboard`,
      {
        query: {
          dataset: query.dataset,
          timeRange: query.timeRange,
          from: query.from,
          to: query.to,
        },
      },
    )
  }
}

export function createEvaluationRepository(): EvaluationRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpEvaluationRepository()
    : new MockEvaluationRepository()
}
