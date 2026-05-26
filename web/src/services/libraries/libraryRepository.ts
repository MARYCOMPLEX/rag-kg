import type { CreateLibraryInput, CreateLibraryResult, LibrarySummary } from '../../domain/libraries/types'
import { createMockLibrary, libraries } from '../../mocks/libraries'
import { apiRequest } from '../api/httpClient'

export interface LibraryRepository {
  list(): Promise<LibrarySummary[]>
  create(input: CreateLibraryInput): Promise<CreateLibraryResult>
}

class MockLibraryRepository implements LibraryRepository {
  async list() {
    return structuredClone(libraries)
  }

  async create(input: CreateLibraryInput) {
    return structuredClone(createMockLibrary(input))
  }
}

class HttpLibraryRepository implements LibraryRepository {
  list() {
    return apiRequest<LibrarySummary[]>('/api/libraries')
  }

  create(input: CreateLibraryInput) {
    return apiRequest<CreateLibraryResult>('/api/libraries', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }
}

export function createLibraryRepository(): LibraryRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpLibraryRepository()
    : new MockLibraryRepository()
}
