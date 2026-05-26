import type { CommandItem, LibraryStat, NavEntry, RecentSession, ScreenNavItem } from '../types/application'

export const screenNavigation: ScreenNavItem[] = [
  { id: 'dashboard', label: 'Library', key: 'G L', routeName: 'libraries' },
  { id: 'chat', label: 'Chat', key: 'G C', routeName: 'library-chat' },
  { id: 'graph', label: 'Graph', key: 'G K', routeName: 'library-graph' },
  { id: 'docs', label: 'Documents', key: 'G D', routeName: 'library-docs' },
  { id: 'review', label: 'Review', key: 'G R', routeName: 'library-review' },
  { id: 'eval', label: 'Evaluate', key: 'G E', routeName: 'library-eval' },
]

export const commandItems: CommandItem[] = [
  { label: 'Open Chat', meta: '/libraries/graphrag-survey/chat', screen: 'chat' },
  { label: 'Open Knowledge Graph', meta: '/libraries/graphrag-survey/kg?focus=GraphRAG', screen: 'graph' },
  { label: 'Open Documents', meta: '/libraries/graphrag-survey/docs', screen: 'docs' },
  { label: 'Run Review', meta: 'action:review topic=GraphRAG', screen: 'review' },
  { label: 'Evaluation Dashboard', meta: '/libraries/graphrag-survey/eval', screen: 'eval' },
]

export const mainNavigation: NavEntry[] = [
  { key: 'chat', id: 'chat', label: 'Chat', icon: 'chat', activeOn: ['chat'] },
  { key: 'graph', id: 'graph', label: 'Graph', icon: 'graph', activeOn: ['graph'] },
  { key: 'ingest', id: 'docs', label: 'Ingest', icon: 'upload', activeOn: ['docs'] },
  { key: 'library', id: 'dashboard', label: 'Library', icon: 'library', activeOn: ['dashboard'] },
  { key: 'datasets', id: 'eval', label: 'Datasets', icon: 'dataset', activeOn: [] },
  { key: 'prompts', id: 'review', label: 'Prompts', icon: 'file', activeOn: ['review'] },
  { key: 'evaluate', id: 'eval', label: 'Evaluate', icon: 'review', activeOn: ['eval'] },
]

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
