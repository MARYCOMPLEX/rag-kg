export type LibraryAccent = 'concept' | 'method' | 'dataset' | 'citation' | 'author'
export type LibraryHealth = 'healthy' | 'indexing'
export type LibraryLanguage = 'en' | 'zh' | 'multi'

export interface LibrarySummary {
  id: string
  name: string
  documentCountLabel: string
  chunkCountLabel: string
  entityCountLabel: string
  activityLabel: string
  statusLabel: string
  status: LibraryHealth
  accent: LibraryAccent
  featured?: boolean
}

export interface CreateLibraryInput {
  name: string
  slug: string
  description: string
  language: LibraryLanguage
  template: string
}

export interface CreateLibraryResult {
  library: LibrarySummary
  redirectTo: string
}
