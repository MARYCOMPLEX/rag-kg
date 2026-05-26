export type ScreenId = 'dashboard' | 'chat' | 'graph' | 'docs' | 'review' | 'eval'

export type ToastTone = 'success' | 'info' | 'warning' | 'danger'

export type StreamState = 'idle' | 'streaming' | 'done' | 'interrupted' | 'unsubstantiated'

export interface ScreenNavItem {
  id: ScreenId
  label: string
  key: string
  routeName: string
}

export interface ToastItem {
  id: number
  tone: ToastTone
  title: string
  detail: string
  action?: string
  timeout?: number
}

export interface Evidence {
  id: string
  label: string
  type: string
  title: string
  meta: string
  score: string
  snippet: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  status?: StreamState
  citations?: string[]
}

export interface CommandItem {
  label: string
  meta: string
  screen: ScreenId
}

export interface CommandSearchResult extends CommandItem {
  icon: string
  shortcut?: string
  tone?: string
}

export interface NavEntry {
  key: string
  id: ScreenId
  label: string
  icon: string
  activeOn: ScreenId[]
}

export interface RecentSession {
  title: string
  time: string
  active?: boolean
}

export interface LibraryStat {
  label: string
  value: string
}

export type ReviewStepStatus = 'done' | 'active' | 'pending'

export interface ReviewPipelineDetail {
  label: string
  status: 'done' | 'active'
}

export interface ReviewPipelineStep {
  id: string
  label: string
  status: ReviewStepStatus
  details?: ReviewPipelineDetail[]
}

export interface ReviewCitation {
  id: string
  type: string
  author: string
  isNew?: boolean
}

export interface ReviewRunStat {
  label: string
  value: string
  accent?: boolean
}

export interface EvaluationKpi {
  title: string
  value: string
  threshold: string
  tone: 'success' | 'secondary' | 'danger'
  points: number[]
  icon?: string
}

export interface EvaluationFailureCase {
  id: string
  dataset: string
  question: string
  failure: string
  tone: string
  em: string
  faithfulness: string
  citation: string
  latency: string
}

export interface GraphEntityType {
  label: string
  count: string
  checked: boolean
  tone: string
}
