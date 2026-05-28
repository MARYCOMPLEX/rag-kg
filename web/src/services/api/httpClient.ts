export interface ApiRequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | undefined>
  timeoutMs?: number
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

import { resolveApiBaseUrl } from './apiBaseUrl'

const API_BASE_URL = resolveApiBaseUrl()

interface ErrorEnvelope {
  code: string
  message: string
  request_id: string
  details?: unknown
}

function buildUrl(path: string, query?: ApiRequestOptions['query']) {
  const url = new URL(path, API_BASE_URL || window.location.origin)
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined)
      url.searchParams.set(key, String(value))
  })
  return url
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseErrorEnvelope(payload: unknown): ErrorEnvelope | null {
  if (!isRecord(payload))
    return null

  const { code, message, request_id: requestId } = payload
  if (typeof code !== 'string' || typeof message !== 'string' || typeof requestId !== 'string')
    return null

  return {
    code,
    message,
    request_id: requestId,
    details: payload.details,
  }
}

function buildErrorMessage(response: Response, payload: unknown) {
  const envelope = parseErrorEnvelope(payload)
  if (!envelope)
    return response.statusText || 'API request failed'

  return `${envelope.message} (${envelope.code}, request ${envelope.request_id})`
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}) {
  const { query, headers, timeoutMs = 20000, ...init } = options
  const requestUrl = buildUrl(path, query)
  const requestHeaders = new Headers(headers)
  if (!(init.body instanceof FormData) && !requestHeaders.has('Content-Type'))
    requestHeaders.set('Content-Type', 'application/json')

  let response: Response
  const controller = init.signal ? null : new AbortController()
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : undefined

  try {
    response = await fetch(requestUrl, {
      ...init,
      headers: requestHeaders,
      signal: init.signal ?? controller?.signal,
    })
  }
  catch (reason) {
    if (reason instanceof DOMException && reason.name === 'AbortError')
      throw new ApiError(`API request timed out after ${timeoutMs}ms at ${requestUrl.href}.`, 0, reason.message)

    if (reason instanceof TypeError)
      throw new ApiError(`Unable to reach API at ${requestUrl.href}.`, 0, reason.message)

    throw reason
  }
  finally {
    if (timeoutId !== undefined)
      window.clearTimeout(timeoutId)
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? await response.json() : await response.text()

  if (!response.ok)
    throw new ApiError(buildErrorMessage(response, payload), response.status, payload)

  return payload as T
}
