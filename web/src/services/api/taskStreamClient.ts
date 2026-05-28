import type { Evidence, StreamState } from '../../types/application'
import { resolveApiBaseUrl } from './apiBaseUrl'

export interface TaskStreamHandlers {
  onToken?: (token: string) => void
  onEvidence?: (evidence: Evidence[]) => void
  onCitations?: (citationIds: string[]) => void
  onStatus?: (status: StreamState) => void
  onDone?: (status: StreamState) => void
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

function tokenFromPayload(payload: unknown) {
  if (typeof payload === 'string')
    return payload

  if (isRecord(payload) && typeof payload.token === 'string')
    return payload.token

  return ''
}

function statusFromPayload(payload: unknown): StreamState | null {
  if (!isRecord(payload))
    return null

  const status = payload.status
  if (
    status === 'idle'
    || status === 'streaming'
    || status === 'done'
    || status === 'interrupted'
    || status === 'unsubstantiated'
  ) {
    return status
  }

  return null
}

function stringArrayFromPayload(payload: unknown) {
  if (!Array.isArray(payload))
    return []

  return payload.filter((item): item is string => typeof item === 'string')
}

function evidenceArrayFromPayload(payload: unknown) {
  if (!Array.isArray(payload))
    return []

  return payload.filter((item): item is Evidence => {
    return isRecord(item)
      && typeof item.id === 'string'
      && typeof item.label === 'string'
      && typeof item.type === 'string'
      && typeof item.title === 'string'
      && typeof item.meta === 'string'
      && typeof item.score === 'string'
      && typeof item.snippet === 'string'
  })
}

function errorEnvelopeFromPayload(payload: unknown) {
  if (!isRecord(payload))
    return null

  if (typeof payload.code === 'string' && typeof payload.message === 'string')
    return payload

  return null
}

function dispatchEvent(eventName: string, data: string, handlers: TaskStreamHandlers) {
  const payload = parseJsonPayload(data)
  const token = tokenFromPayload(payload)
  const evidence = evidenceArrayFromPayload(payload)
  const citationIds = stringArrayFromPayload(payload)
  const status = statusFromPayload(payload)
  const envelope = errorEnvelopeFromPayload(payload)

  if (eventName === 'token' || token) {
    if (token)
      handlers.onToken?.(token)
    return
  }

  if (eventName === 'evidence' || evidence.length) {
    if (evidence.length)
      handlers.onEvidence?.(evidence)
    return
  }

  if (eventName === 'citations' || citationIds.length) {
    if (citationIds.length)
      handlers.onCitations?.(citationIds)
    return
  }

  if (eventName === 'done' || status === 'done') {
    handlers.onDone?.(status ?? 'done')
    return
  }

  if (eventName === 'status' || status) {
    if (status)
      handlers.onStatus?.(status)
    return
  }

  if (eventName === 'error' || envelope)
    handlers.onError?.(payload)
}

export function connectTaskStream(streamUrl: string, handlers: TaskStreamHandlers, signal?: AbortSignal) {
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
