import type { ChatMessage, Evidence, StreamState } from '../../types/application'

export type ChatRequestState = 'idle' | 'loading' | 'success' | 'error'

export interface ChatQuestionContext {
  evidenceIds?: string[]
  entityIds?: string[]
}

export interface ChatSession {
  sessionId: string
  title: string
  createdAtLabel: string
  messages: ChatMessage[]
  evidence: Evidence[]
}

export interface ChatQuestionRequest {
  question: string
  sessionId?: string
  context?: ChatQuestionContext
}

export interface ChatQuestionResponse {
  taskId: string
  streamUrl: string
  userMessage: ChatMessage
  assistantMessage: ChatMessage
  evidence: Evidence[]
}

export interface ChatStreamDoneEvent {
  status: StreamState
}
