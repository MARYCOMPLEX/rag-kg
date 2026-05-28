export type ReviewRunStatus = 'idle' | 'queued' | 'running' | 'backgrounded' | 'cancelled' | 'failed' | 'done'
export type ReviewPipelineStepStatus = 'done' | 'active' | 'pending'
export type ReviewPipelineDetailStatus = 'done' | 'active'

export interface ReviewPipelineDetail {
  label: string
  status: ReviewPipelineDetailStatus
}

export interface ReviewPipelineStep {
  id: string
  label: string
  status: ReviewPipelineStepStatus
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

export interface ReviewDraftSection {
  id: string
  heading: string
  markdown: string
  citations: string[]
  unsubstantiated?: boolean
}

export interface ReviewDraft {
  title: string
  authors: string | string[]
  generatedAtLabel: string
  badgeLabel: string
  totalTokensLabel: string
  draftTokens: number
  draftTokenLimit: number
  modelLabel: string
  statusLabel: string
  sections: ReviewDraftSection[]
}

export interface ReviewRun {
  id: string
  libraryId: string
  status: ReviewRunStatus
  progress: number
  taskId?: string | null
  streamUrl?: string | null
  backgrounded?: boolean
}

export interface ReviewSnapshot {
  run: ReviewRun | null
  pipelineSteps: ReviewPipelineStep[]
  runStats: ReviewRunStat[]
  citations: ReviewCitation[]
  draft: ReviewDraft | null
  streamUrl?: string | null
}

export interface ReviewCreateRequest {
  topic?: string
  instructions?: string
  documentIds?: string[]
  mode?: string
}

export interface ReviewRegenerateRequest {
  instructions?: string
  keepCompletedSections?: boolean
}

export interface ReviewCancelRequest {
  keepGeneratedSections?: boolean
}

export interface ReviewMutationFeedback {
  tone: 'success' | 'info' | 'warning' | 'danger'
  title: string
  detail: string
  action?: string
}

export interface ReviewCancelResponse extends ReviewMutationFeedback {
  run?: ReviewRun | null
}

export interface ReviewDraftDeltaEvent {
  sectionId: string
  markdownDelta: string
  citations?: string[]
  draftTokens?: number
}

export interface ReviewStatusEvent {
  status: ReviewRunStatus
  progress?: number
  statusLabel?: string
  draftTokens?: number
}

