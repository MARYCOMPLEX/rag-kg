import { fetchEventSource } from '@microsoft/fetch-event-source'

export interface TaskStreamHandlers {
  onToken?: (token: string) => void
  onCitations?: (citationIds: string[]) => void
  onStatus?: (status: string) => void
  onError?: (error: unknown) => void
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export function connectTaskStream(taskId: string, handlers: TaskStreamHandlers, signal?: AbortSignal) {
  const controller = new AbortController()
  const streamSignal = signal ?? controller.signal
  const endpoint = `${API_BASE_URL}/v1/tasks/${taskId}/events`

  const done = fetchEventSource(endpoint, {
    signal: streamSignal,
    onmessage(event) {
      if (event.event === 'token')
        handlers.onToken?.(event.data)
      else if (event.event === 'citations')
        handlers.onCitations?.(JSON.parse(event.data) as string[])
      else
        handlers.onStatus?.(event.event || event.data)
    },
    onerror(error) {
      handlers.onError?.(error)
      throw error
    },
  })

  return {
    close: () => controller.abort(),
    done,
  }
}
