import type { CommandSearchOptions, CommandSearchResponse, ShellMetadata } from '../../domain/search/types'
import { documentSearchResults, entitySearchResults } from '../../mocks/search'
import { libraryStats, recentSessions, shellProfile } from '../../mocks/navigation'
import { apiRequest } from '../api/httpClient'

export interface SearchRepository {
  search(libraryId: string, options: CommandSearchOptions): Promise<CommandSearchResponse>
  getShellMetadata(libraryId: string): Promise<ShellMetadata>
}

class MockSearchRepository implements SearchRepository {
  async search(_libraryId: string, options: CommandSearchOptions) {
    const query = options.query.trim().toLowerCase()
    const records = [...entitySearchResults, ...documentSearchResults]
    const results = query
      ? records.filter(item => item.label.toLowerCase().includes(query) || item.meta.toLowerCase().includes(query))
      : records

    return {
      query: options.query,
      results,
    }
  }

  async getShellMetadata(_libraryId: string) {
    return {
      recentSessions: recentSessions.map((session, index) => ({
        id: `mock-session-${index + 1}`,
        screen: session.screen ?? 'chat',
        ...session,
      })),
      libraryStats,
      notifications: null,
      profile: shellProfile,
    }
  }
}

class HttpSearchRepository implements SearchRepository {
  search(libraryId: string, options: CommandSearchOptions) {
    return apiRequest<CommandSearchResponse>(
      `/api/libraries/${encodeURIComponent(libraryId)}/search`,
      {
        query: {
          q: options.query,
          scope: options.scope?.join(','),
          limit: options.limit,
        },
      },
    )
  }

  getShellMetadata(libraryId: string) {
    return apiRequest<ShellMetadata>(`/api/libraries/${encodeURIComponent(libraryId)}/shell/metadata`)
  }
}

export function createSearchRepository(): SearchRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpSearchRepository()
    : new MockSearchRepository()
}
