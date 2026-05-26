export interface ApiRequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | undefined>
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

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
  const { query, headers, ...init } = options
  const requestUrl = buildUrl(path, query)
  let response: Response

  try {
    response = await fetch(requestUrl, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    })
  }
  catch (reason) {
    if (reason instanceof TypeError)
      throw new ApiError(`Unable to reach API at ${requestUrl.href}.`, 0, reason.message)

    throw reason
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? await response.json() : await response.text()

  if (!response.ok)
    throw new ApiError(buildErrorMessage(response, payload), response.status, payload)

  return payload as T
}
