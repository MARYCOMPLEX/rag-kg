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

function buildUrl(path: string, query?: ApiRequestOptions['query']) {
  const url = new URL(path, API_BASE_URL || window.location.origin)
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined)
      url.searchParams.set(key, String(value))
  })
  return url
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}) {
  const { query, headers, ...init } = options
  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  })

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? await response.json() : await response.text()

  if (!response.ok)
    throw new ApiError(response.statusText || 'API request failed', response.status, payload)

  return payload as T
}
