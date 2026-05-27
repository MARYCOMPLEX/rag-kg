import type { EvaluationFailureCase, EvaluationKpi, ToastTone } from '../../types/application'

export interface EvaluationSummary {
  libraryId: string
  libraryName: string
  datasetSummaryLabel: string
  timeRangeLabel: string
  lastRunLabel?: string | null
}

export interface EvaluationDatasetFilter {
  key: 'smoke' | 'multihop' | 'review'
  label: string
  count: number
  active?: boolean
}

export interface EvaluationTimeRangeFilter {
  key: '7d' | '30d' | '90d'
  label: string
  active?: boolean
}

export interface EvaluationFilters {
  datasets: EvaluationDatasetFilter[]
  timeRanges: EvaluationTimeRangeFilter[]
}

export interface EvaluationBudgetAlert {
  tone: ToastTone
  title: string
  detail: string
  action?: string | null
  dismissible?: boolean | null
}

export interface EvaluationTrendLegendItem {
  label: string
  tone: 'success' | 'secondary' | 'citation' | 'danger'
}

export interface EvaluationTrend {
  days: string[]
  em: number[]
  faithfulness: number[]
  citation: number[]
  latency: number[]
  legend: EvaluationTrendLegendItem[]
}

export interface EvaluationModels {
  routerLabel: string
  embeddingLabel: string
  warning?: string | null
}

export interface EvaluationBudgetLimit {
  key: string
  label: string
  value: string
}

export interface EvaluationDataActions {
  canExport?: boolean | null
  canPurge?: boolean | null
}

export interface EvaluationLibrarySettings {
  libraryLabel: string
  models: EvaluationModels
  budgetLimits: EvaluationBudgetLimit[]
  dataActions?: EvaluationDataActions | null
}

export interface EvaluationDashboard {
  summary: EvaluationSummary
  filters: EvaluationFilters
  budgetAlert: EvaluationBudgetAlert | null
  kpis: EvaluationKpi[]
  trend: EvaluationTrend
  failureCases: EvaluationFailureCase[]
  librarySettings: EvaluationLibrarySettings
}

export interface EvaluationDashboardQuery {
  dataset?: EvaluationDatasetFilter['key']
  timeRange?: EvaluationTimeRangeFilter['key']
  from?: string
  to?: string
}
