import type { CommandSearchResult } from '../types/application'

export const entitySearchResults: CommandSearchResult[] = [
  { label: 'GraphRAG', meta: 'Concept / 152 mentions / focus in KG', icon: 'graph', screen: 'graph', tone: 'concept' },
  { label: 'Community detection', meta: 'Method / 246 refs / 1-hop highlight', icon: 'graph', screen: 'graph', tone: 'method' },
  { label: 'Hierarchical communities', meta: 'Concept / connected to GraphRAG', icon: 'graph', screen: 'graph', tone: 'concept' },
]

export const documentSearchResults: CommandSearchResult[] = [
  { label: 'From Local to Global: A Graph RAG Approach', meta: 'PDF / 22 pages / 128 chunks', icon: 'file', screen: 'docs' },
  { label: 'Hierarchical Community Summary for KG QA', meta: 'PDF / indexed / 94 entities', icon: 'file', screen: 'docs' },
]
