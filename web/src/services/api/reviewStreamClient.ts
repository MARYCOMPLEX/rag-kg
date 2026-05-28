import type {
  ReviewCitation,
  ReviewDraftDeltaEvent,
  ReviewPipelineStep,
  ReviewRunStat,
  ReviewStatusEvent,
} from '../../domain/review/types'
import { resolveApiBaseUrl } from './apiBaseUrl'

export interface ReviewStreamHandlers {
  onDraftDelta?: (event: ReviewDraftDeltaEvent) => void
  onPipeline?: (steps: ReviewPipelineStep[]) => void
  onCitations?: (citations: ReviewCitation[]) => void
  onStats?: (stats: ReviewRunStat[]) => void
  onStatus?: (status: ReviewStatusEvent) => void
  onDone?: (status: ReviewStatusEvent) => void
  onError?: (error: unknown) => void
}

const API_BASE_URL = resolveApiBaseUrl()

function buildStreamUrl(streamUrl: string) {
  return new URL(streamUrl, API_BASE_URL || window.location.origin).href
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseJsonPayload(data: string): unknown {
  if (!data)
    return null

  try {
    return JSON.parse(data) as unknown
  }
  catch {
    return data
  }
}

function isReviewCitation(value: unknown): value is ReviewCitation {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.type === 'string'
    && typeof value.author === 'string'
}

function isReviewPipelineStep(value: unknown): value is ReviewPipelineStep {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.label === 'string'
    && (value.status === 'done' || value.status === 'active' || value.status === 'pending')
}

function isReviewRunStat(value: unknown): value is ReviewRunStat {
  return isRecord(value)
    && typeof value.label === 'string'
    && typeof value.value === 'string'
}

function draftDeltaFromPayload(payload: unknown): ReviewDraftDeltaEvent | null {
  if (!isRecord(payload) || typeof payload.sectionId !== 'string' || typeof payload.markdownDelta !== 'string')
    return null

  return {
    sectionId: payload.sectionId,
    markdownDelta: payload.markdownDelta,
    citations: Array.isArray(payload.citations) ? payload.citations.filter((item): item is string => typeof item === 'string') : undefined,
    draftTokens: typeof payload.draftTokens === 'number' ? payload.draftTokens : undefined,
  }
}

function pipelineFromPayload(payload: unknown): ReviewPipelineStep[] {
  if (Array.isArray(payload))
    return payload.filter(isReviewPipelineStep)

  if (isRecord(payload) && Array.isArray(payload.steps))
    return payload.steps.filter(isReviewPipelineStep)

  if (isRecord(payload) && Array.isArray(payload.pipelineSteps))
    return payload.pipelineSteps.filter(isReviewPipelineStep)

  return []
}

function citationsFromPayload(payload: unknown): ReviewCitation[] {
  if (!Array.isArray(payload))
    return isRecord(payload) && Array.isArray(payload.citations)
      ? payload.citations.filter(isReviewCitation)
      : []

  return payload.filter(isReviewCitation)
}

function statsFromPayload(payload: unknown): ReviewRunStat[] {
  if (!Array.isArray(payload))
    return isRecord(payload) && Array.isArray(payload.runStats)
      ? payload.runStats.filter(isReviewRunStat)
      : []

  return payload.filter(isReviewRunStat)
}

function statusFromPayload(payload: unknown): ReviewStatusEvent | null {
  if (!isRecord(payload) || typeof payload.status !== 'string')
    return null

  const status = payload.status
  if (
    status !== 'idle'
    && status !== 'queued'
    && status !== 'running'
    && status !== 'backgrounded'
    && status !== 'cancelled'
    && status !== 'failed'
    && status !== 'done'
  ) {
    return null
  }

  return {
    status,
    progress: typeof payload.progress === 'number' ? payload.progress : undefined,
    statusLabel: typeof payload.statusLabel === 'string' ? payload.statusLabel : undefined,
    draftTokens: typeof payload.draftTokens === 'number' ? payload.draftTokens : undefined,
  }
}

function errorEnvelopeFromPayload(payload: unknown) {
  if (!isRecord(payload))
    return null

  if (typeof payload.code === 'string' && typeof payload.message === 'string')
    return payload

  return null
}

function dispatchEvent(eventName: string, data: string, handlers: ReviewStreamHandlers) {
  const payload = parseJsonPayload(data)

  if (eventName === 'draft_delta') {
    const event = draftDeltaFromPayload(payload)
    if (event)
      handlers.onDraftDelta?.(event)
    return
  }

  if (eventName === 'pipeline') {
    const steps = pipelineFromPayload(payload)
    if (steps.length)
      handlers.onPipeline?.(steps)
    return
  }

  if (eventName === 'citations') {
    const citations = citationsFromPayload(payload)
    if (citations.length)
      handlers.onCitations?.(citations)
    return
  }

  if (eventName === 'stats') {
    const stats = statsFromPayload(payload)
    if (stats.length)
      handlers.onStats?.(stats)
    return
  }

  if (eventName === 'status') {
    const status = statusFromPayload(payload)
    if (status)
      handlers.onStatus?.(status)
    return
  }

  if (eventName === 'done') {
    handlers.onDone?.(statusFromPayload(payload) ?? { status: 'done' })
    return
  }

  if (eventName === 'error') {
    handlers.onError?.(errorEnvelopeFromPayload(payload) ?? payload)
  }
}

export function connectReviewStream(streamUrl: string, handlers: ReviewStreamHandlers, signal?: AbortSignal) {
  const controller = new AbortController()
  const streamSignal = signal ?? controller.signal
  const endpoint = buildStreamUrl(streamUrl)

  const done = (async () => {
    const response = await fetch(endpoint, {
      signal: streamSignal,
      headers: {
        Accept: 'text/event-stream',
      },
    })

    if (!response.ok) {
      let payload: unknown = null
      const contentType = response.headers.get('content-type') ?? ''
      if (contentType.includes('application/json'))
        payload = await response.json()
      else
        payload = await response.text()

      handlers.onError?.(payload)
      throw new Error(`SSE request failed with status ${response.status}`)
    }

    if (!response.body)
      throw new Error('SSE response body is unavailable.')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done: readerDone, value } = await reader.read()
      if (readerDone)
        break

      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        let eventName = ''
        let data = ''

        rawEvent.split(/\r?\n/).forEach((line) => {
          if (line.startsWith('event:'))
            eventName = line.slice(6).trim()
          else if (line.startsWith('data:'))
            data += `${data ? '\n' : ''}${line.slice(5).trim()}`
        })

        if (eventName || data)
          dispatchEvent(eventName, data, handlers)

        boundary = buffer.indexOf('\n\n')
      }
    }
  })()

  done.catch((error) => {
    if (error instanceof DOMException && error.name === 'AbortError')
      return

    handlers.onError?.(error)
  })

  return {
    close: () => controller.abort(),
    done,
  }
}
