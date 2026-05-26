import type { EvaluationFailureCase, EvaluationKpi } from '../types/application'

export const evaluationKpis: EvaluationKpi[] = [
  { title: 'Answer relevancy EM@1', value: '0.842', threshold: '(>= 0.80)', tone: 'success', points: [0.62, 0.67, 0.64, 0.71, 0.7, 0.78, 0.82] },
  { title: 'Faithfulness FactScore', value: '0.918', threshold: '(>= 0.85)', tone: 'secondary', points: [0.58, 0.63, 0.72, 0.69, 0.8, 0.86, 0.91] },
  { title: 'Citation precision C@1', value: '0.887', threshold: '(>= 0.80)', tone: 'secondary', points: [0.66, 0.67, 0.72, 0.78, 0.76, 0.8, 0.88] },
  { title: 'Latency p95', value: '2.31s', threshold: '(<= 4.00s)', tone: 'danger', icon: 'timer', points: [0.52, 0.56, 0.44, 0.62, 0.49, 0.55, 0.51] },
]

export const evaluationFailureCases: EvaluationFailureCase[] = [
  { id: 'Q-0021', dataset: 'multihop', question: 'How does the self-attention mechanism differ from cross-attention in the context of the T5 architecture?', failure: 'Hallucination', tone: 'danger', em: '0.12', faithfulness: '0.45', citation: '0.82', latency: '1.2s' },
  { id: 'Q-0017', dataset: 'smoke', question: 'What is the learning rate used in the pre-training phase of BERT base?', failure: 'Missing evidence', tone: 'warning', em: '0.31', faithfulness: '0.52', citation: '0.48', latency: '2.9s' },
  { id: 'Q-0038', dataset: 'review', question: 'List the authors who contributed to both GraphRAG and the Leiden community paper.', failure: 'Wrong hop', tone: 'neutral', em: '0.44', faithfulness: '0.71', citation: '0.64', latency: '3.6s' },
]

export const evaluationTrend = {
  days: Array.from({ length: 30 }, (_, index) => `May ${6 + index}`),
  em: Array.from({ length: 30 }, (_, index) => Number((0.72 + ((index * 7) % 19) / 100).toFixed(2))),
  faithfulness: Array.from({ length: 30 }, (_, index) => Number((0.76 + ((index * 11) % 17) / 100).toFixed(2))),
  citation: Array.from({ length: 30 }, (_, index) => Number((0.68 + ((index * 5) % 21) / 100).toFixed(2))),
  latency: Array.from({ length: 30 }, (_, index) => Number((0.18 + ((index * 13) % 38) / 100).toFixed(2))),
}

export const evaluationTrendLegend = [
  { label: 'EM@1', tone: 'success' },
  { label: 'Faithfulness', tone: 'secondary' },
  { label: 'C@1', tone: 'citation' },
  { label: 'Latency p95', tone: 'danger' },
]
