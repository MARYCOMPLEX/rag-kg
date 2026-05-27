import type { LibraryStat, RecentSession } from '../types/application'

export const recentSessions: RecentSession[] = [
  { title: 'GraphRAG local vs global', time: 'now', active: true },
  { title: 'Clustering algorithms for...', time: '2h' },
  { title: 'Entity extraction config', time: '1d' },
  { title: 'Prompt optimization test', time: '2d' },
  { title: 'Reviewing citations in doc', time: '5d' },
]

export const libraryStats: LibraryStat[] = [
  { label: 'Papers', value: '18,742' },
  { label: 'Entities', value: '126,831' },
  { label: 'Relations', value: '532,104' },
  { label: 'Chunks', value: '3.2M' },
]
