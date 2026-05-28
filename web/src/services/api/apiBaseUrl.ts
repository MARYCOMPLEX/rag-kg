export function resolveApiBaseUrl() {
  if (import.meta.env.DEV && import.meta.env.VITE_API_PROXY_TARGET)
    return ''

  return import.meta.env.VITE_API_BASE_URL ?? ''
}
