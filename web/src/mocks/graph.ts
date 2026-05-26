import type { GraphEntityType } from '../types/application'

export const graphEntityTypes: GraphEntityType[] = [
  { label: 'Concept', count: '2,341', checked: true, tone: 'concept' },
  { label: 'Method', count: '1,256', checked: true, tone: 'method' },
  { label: 'Dataset', count: '1,102', checked: true, tone: 'dataset' },
  { label: 'Metric', count: '943', checked: false, tone: 'metric' },
  { label: 'Author', count: '1,523', checked: false, tone: 'author' },
  { label: 'Venue', count: '1,326', checked: false, tone: 'venue' },
]

export const graphMentions = [18, 24, 32, 28, 46, 64, 56, 78, 92, 84]

export const graphCoOccurring = [
  { name: 'LLM', type: 'concept', count: 89 },
  { name: 'Vector Database', type: 'method', count: 64 },
  { name: 'Knowledge Graph', type: 'concept', count: 58 },
]
