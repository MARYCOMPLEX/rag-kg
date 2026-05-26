import type { ChatMessage, Evidence } from '../types/application'

export const evidence: Evidence[] = [
  {
    id: '1',
    label: 'Concept',
    type: 'method',
    title: 'From Local to Global: A Graph RAG Approach to Query-Focused Summarization',
    meta: 'Edge et al. / 2024 / arXiv:2404.16130',
    score: '0.92',
    snippet: 'Global and local community summaries allow hierarchical retrieval over graph communities before final synthesis.',
  },
  {
    id: '2',
    label: 'Architecture',
    type: 'concept',
    title: 'Hierarchical Community Structure in Large-Scale Knowledge Graphs',
    meta: 'Chen, Y. / WWW / 2025',
    score: '0.87',
    snippet: 'Recursive community detection creates a layered index suitable for multi-hop evidence retrieval.',
  },
  {
    id: '3',
    label: 'Eval',
    type: 'metric',
    title: 'Evaluating Map-Reduce Strategies for Long-Context LLM Synthesis',
    meta: 'Sun et al. / COLM / 2024',
    score: '0.81',
    snippet: 'Chunk selection and reranking remain the strongest predictors of citation precision.',
  },
]

export const initialMessages: ChatMessage[] = [
  {
    id: 'm1',
    role: 'user',
    text: 'I am trying to understand how GraphRAG fuses community-level summaries with vector search results during query time.\n\nSpecifically, how are community summaries constructed, indexed, and selected relative to chunk-level retrieval?\n\nCould you walk me through the full retrieval-and-generation pipeline with an example?',
  },
  {
    id: 'm2',
    role: 'assistant',
    status: 'done',
    citations: ['1', '2', '3'],
    text: 'GraphRAG builds a hierarchical index where each detected community in the knowledge graph is summarized by an LLM into a compact profile. These summaries are embedded and indexed alongside chunk embeddings.\n\nAt query time, the system retrieves relevant community summaries to identify likely answer regions. It expands those communities to fetch constituent chunks and connected entities, performs scoped vector retrieval, and optionally applies reranking.\n\nFinally, top-ranked evidence is passed to the LLM with citations grounded to original chunks, combining broad coverage with precise support.',
  },
]

export const groundedAnswerTokens = 'GraphRAG combines graph community summaries with vector retrieval. The UI keeps the answer grounded by waiting for citation metadata before activating inline evidence chips.'.split(' ')
