import type { NavEntry, ScreenId, ScreenNavItem } from '../types/application'

export interface CommandActionTemplate {
  label: string
  screen: ScreenId
  shortcut?: string
  buildMeta: (libraryId: string) => string
}

export const screenNavigation: ScreenNavItem[] = [
  { id: 'dashboard', label: 'Library', key: 'G L', routeName: 'libraries' },
  { id: 'chat', label: 'Chat', key: 'G C', routeName: 'library-chat' },
  { id: 'graph', label: 'Graph', key: 'G K', routeName: 'library-graph' },
  { id: 'docs', label: 'Documents', key: 'G D', routeName: 'library-docs' },
  { id: 'review', label: 'Review', key: 'G R', routeName: 'library-review' },
  { id: 'eval', label: 'Evaluate', key: 'G E', routeName: 'library-eval' },
]

export const commandActionTemplates: CommandActionTemplate[] = [
  {
    label: 'Open Chat',
    screen: 'chat',
    buildMeta: libraryId => libraryId ? `/libraries/${libraryId}/chat` : 'Select a library to open Chat',
  },
  {
    label: 'Open Knowledge Graph',
    screen: 'graph',
    buildMeta: libraryId => libraryId ? `/libraries/${libraryId}/kg` : 'Select a library to open Knowledge Graph',
  },
  {
    label: 'Open Documents',
    screen: 'docs',
    buildMeta: libraryId => libraryId ? `/libraries/${libraryId}/docs` : 'Select a library to open Documents',
  },
  {
    label: 'Run Review',
    screen: 'review',
    shortcut: 'Cmd N',
    buildMeta: libraryId => libraryId ? `/libraries/${libraryId}/review` : 'Select a library to run Review',
  },
  {
    label: 'Evaluation Dashboard',
    screen: 'eval',
    buildMeta: libraryId => libraryId ? `/libraries/${libraryId}/eval` : 'Select a library to open Evaluation',
  },
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
