import type { CommandSearchResult, RecentSession, ScreenId, ShellProfile } from '../../types/application'

export interface CommandSearchResponse {
  query: string
  results: CommandSearchResult[]
}

export interface CommandSearchOptions {
  query: string
  scope?: Array<'documents' | 'entities' | 'libraries' | 'actions'>
  limit?: number
}

export interface LibraryStat {
  label: string
  value: string
}

export interface ShellNotifications {
  activeBackgroundStreams: number
  label?: string
}

export interface ShellMetadata {
  recentSessions: Array<RecentSession & { id: string, screen: ScreenId }>
  libraryStats: LibraryStat[]
  notifications?: ShellNotifications | null
  profile?: ShellProfile | null
}
