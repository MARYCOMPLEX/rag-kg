import type { ScreenId } from '../types/application'

export const screenRouteNames: Record<ScreenId, string> = {
  dashboard: 'libraries',
  chat: 'library-chat',
  graph: 'library-graph',
  docs: 'library-docs',
  review: 'library-review',
  eval: 'library-eval',
}

export const routeNameScreens: Record<string, ScreenId> = Object.fromEntries(
  Object.entries(screenRouteNames).map(([screen, routeName]) => [routeName, screen]),
) as Record<string, ScreenId>
