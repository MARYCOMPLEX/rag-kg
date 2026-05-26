import type { ReviewCitation, ReviewPipelineStep, ReviewRunStat } from '../types/application'

export const reviewPipelineSteps: ReviewPipelineStep[] = [
  { id: 'decompose', label: 'Decompose into subtopics', status: 'done' },
  {
    id: 'models',
    label: 'Subtopic 1: Pre-trained models',
    status: 'done',
    details: [
      { label: 'Local search (32 chunks)', status: 'done' },
      { label: 'Draft (612 tok)', status: 'done' },
    ],
  },
  {
    id: 'hierarchical',
    label: 'Subtopic 2: Hierarchical KG',
    status: 'active',
    details: [
      { label: 'Local search (28 chunks)', status: 'done' },
      { label: 'Draft (324/800 tok)', status: 'active' },
    ],
  },
  { id: 'community', label: 'Subtopic 3: Community summaries', status: 'pending' },
  { id: 'evaluation', label: 'Subtopic 4: Eval & limitations', status: 'pending' },
  { id: 'cross-check', label: 'Citation cross-check', status: 'pending' },
]

export const reviewCitations: ReviewCitation[] = [
  { id: '1', type: 'Concept', author: 'Pei et al.' },
  { id: '2', type: 'Method', author: 'Sun et al.' },
  { id: '3', type: 'Author', author: 'Zhang et al.' },
  { id: '4', type: 'Metric', author: 'Liu et al.' },
  { id: '5', type: 'Dataset', author: 'Wang et al.', isNew: true },
  { id: '8', type: 'Venue', author: 'GraphRAG Summit', isNew: true },
]

export const reviewRunStats: ReviewRunStat[] = [
  { label: 'Tokens', value: '14,328 / 32,000' },
  { label: 'Cost', value: '$0.36' },
  { label: 'Elapsed', value: '04:18' },
  { label: 'ETA', value: '~03:30', accent: true },
]
