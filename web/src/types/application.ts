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
  id?: string
  type?: 'document' | 'entity' | 'library' | 'action'
  label: string
  meta: string
  screen: ScreenId
  shortcut?: string
  target?: CommandSearchTarget
}

export interface CommandSearchResult extends CommandItem {
  id?: string
  icon?: string
  shortcut?: string
  tone?: string
}

export interface CommandSearchTarget {
  libraryId?: string
  documentId?: string
  entityId?: string
  sessionId?: string
  reviewRunId?: string
  query?: string
}

export interface NavEntry {
  key: string
  id: ScreenId
  label: string
  icon: string
  activeOn: ScreenId[]
}

export interface RecentSession {
  id?: string
  title: string
  time: string
  screen?: ScreenId
  active?: boolean
  target?: CommandSearchTarget
}

export interface LibraryStat {
  label: string
  value: string
}

export interface ShellProfile {
  initials: string
  displayName: string
  planLabel?: string
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

export interface ReviewDraftCitationMarker {
  id: string
  label: string
  ariaLabel: string
  warning?: boolean
}

export interface ReviewDraftTextSegment {
  text: string
  citation?: ReviewDraftCitationMarker
}

export interface ReviewDraftParagraph {
  id: string
  segments: ReviewDraftTextSegment[]
  trailingCaret?: boolean
}

export interface ReviewDraftSection {
  id: string
  heading: string
  paragraphs: ReviewDraftParagraph[]
}

export interface ReviewDraftContent {
  title: string
  metadata: string[]
  badge: string
  runningLabel: string
  pausedLabel: string
  modelLabel: string
  tokenLimit: number
  sections: ReviewDraftSection[]
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
  key?: string
  label: string
  count: string | number
  checked: boolean
  tone: string
}

export interface GraphCanvasEdge {
  id: string
  source?: string
  target?: string
  x1: number
  y1: number
  x2: number
  y2: number
  muted?: boolean
}

export interface GraphCanvasNode {
  id: string
  label: string
  type?: string
  tone: string
  x: number
  y: number
  radius: number
  selected?: boolean
  faded?: boolean
  outerRadius?: number
}

export interface GraphCanvasSnapshot {
  edges: GraphCanvasEdge[]
  nodes: GraphCanvasNode[]
  layout?: 'static' | 'force' | 'webgl'
  largeGraph?: boolean
  summaryLabel: string
  legendItems: Array<{
    label: string
    tone: string
  }>
  confidenceLabel: string
  filterCountLabel: string
  zoomLabel: string
  topNote: string
  bottomNote: string
}

export interface GraphEntityDetail {
  id?: string
  label?: string
  kind: string
  stableId: string
  summary: string
  aliases: string[]
  hiddenAliasCountLabel?: string
  connectionCountLabel: string
  evidenceCountLabel: string
  stats: Array<{
    label: string
    value: string
  }>
  mentionsStartLabel: string
  mentionsEndLabel: string
}
