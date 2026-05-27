import type { GraphCanvasSnapshot, GraphEntityDetail, GraphEntityType } from '../types/application'

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

export const graphCanvasSnapshot: GraphCanvasSnapshot = {
  topNote: 'Large graph layout waits for backend metadata',
  bottomNote: 'Zoom label behavior waits for backend metadata',
  zoomLabel: '100%',
  summaryLabel: '8,491 entities | 31,219 triples',
  legendItems: [
    { label: 'Concept', tone: 'concept' },
    { label: 'Method', tone: 'method' },
  ],
  confidenceLabel: 'confidence >= 0.65',
  filterCountLabel: '6',
  edges: [
    { id: 'graphrag-leiden', x1: 400, y1: 300, x2: 250, y2: 150 },
    { id: 'graphrag-community', x1: 400, y1: 300, x2: 600, y2: 200 },
    { id: 'graphrag-multihop', x1: 400, y1: 300, x2: 200, y2: 400 },
    { id: 'graphrag-edge', x1: 400, y1: 300, x2: 550, y2: 450, muted: true },
  ],
  nodes: [
    { id: 'graphrag', label: 'GraphRAG', tone: 'selected', x: 400, y: 300, radius: 40, outerRadius: 44, selected: true },
    { id: 'leiden', label: 'Leiden algorithm', tone: 'concept', x: 250, y: 150, radius: 25 },
    { id: 'community', label: 'Community detection', tone: 'method', x: 600, y: 200, radius: 30, outerRadius: 34 },
    { id: 'multihop', label: 'MultiHop-RAG', tone: 'dataset', x: 200, y: 400, radius: 25 },
    { id: 'edge-et-al', label: 'D. Edge et al.', tone: 'author', x: 550, y: 450, radius: 20, faded: true },
  ],
}

export const graphEntityDetail: GraphEntityDetail = {
  kind: 'Concept',
  stableId: 'MOCK-ENTITY-001',
  summary: 'A methodology for enhancing Retrieval-Augmented Generation (RAG) by incorporating knowledge graphs to improve context retrieval, particularly for complex, multi-hop queries over private datasets.',
  aliases: ['Graph-augmented RAG', 'G-RAG', 'KG-RAG'],
  hiddenAliasCountLabel: '+2',
  connectionCountLabel: '24',
  evidenceCountLabel: '18',
  stats: [
    { label: 'Degree', value: '24' },
    { label: 'Confidence', value: '0.87' },
    { label: 'Incoming', value: '11' },
    { label: 'Mentions', value: '152' },
  ],
  mentionsStartLabel: 'Jan 2023',
  mentionsEndLabel: 'Dec 2023',
}
