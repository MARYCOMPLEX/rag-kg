import type { ReviewCitation, ReviewDraftContent, ReviewPipelineStep, ReviewRunStat } from '../types/application'

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

export const reviewDraftContent: ReviewDraftContent = {
  title: 'Seeded review draft\n2024-2025',
  metadata: ['Mock Author', 'May 16 2025', '14,328 tokens'],
  badge: 'Draft',
  runningLabel: 'Drafting subtopic 2',
  pausedLabel: 'Generation paused',
  modelLabel: 'Haiku 4.5',
  tokenLimit: 800,
  sections: [
    {
      id: 'pre-trained-models',
      heading: '## 1. Pre-trained models',
      paragraphs: [
        {
          id: 'model-alignment',
          segments: [
            {
              text: 'Recent advancements in GraphRAG have heavily leveraged large pre-trained models to align unstructured text with structured knowledge graphs',
              citation: { id: '1', label: '[1]', ariaLabel: 'Open citation 1' },
            },
            {
              text: '. By embedding both nodes and relationships into high-dimensional vector spaces, systems can perform semantic retrieval over graphs with unprecedented accuracy',
              citation: { id: '2', label: '[2]', ariaLabel: 'Open citation 2' },
            },
            {
              text: '. Furthermore, fine-tuning techniques applied to domain-specific corpora have shown significant improvements in reducing hallucination rates',
              citation: { id: '3', label: '[3]', ariaLabel: 'Open citation 3' },
            },
            { text: '.' },
          ],
        },
      ],
    },
    {
      id: 'hierarchical-kg',
      heading: '## 2. Hierarchical KG',
      paragraphs: [
        {
          id: 'hierarchical-reasoning',
          trailingCaret: true,
          segments: [
            {
              text: 'The integration of hierarchical structures within Knowledge Graphs represents a paradigm shift for complex reasoning tasks',
              citation: { id: '4', label: '[4]', ariaLabel: 'Open citation 4' },
            },
            {
              text: '. Instead of treating all entities uniformly, modern pipelines segment sub-graphs into distinct abstraction layers. This allows the RAG system to traverse from abstract concepts down to specific facts seamlessly',
              citation: { id: '5', label: '[5]', ariaLabel: 'Open citation 5' },
            },
            {
              text: '. Current methodologies emphasize community detection algorithms to generate these hierarchies dynamically during the ingestion phase, which significantly optimizes context window utilization during synthesis',
              citation: { id: 'unsubstantiated', label: '[?]', ariaLabel: 'Unsubstantiated citation', warning: true },
            },
          ],
        },
      ],
    },
  ],
}
