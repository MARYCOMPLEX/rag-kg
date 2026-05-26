import type {
  DocumentDetail,
  DocumentMutationFeedback,
  DocumentsWorkspace,
  LibraryDocument,
} from '../domain/documents/types'

const documents: LibraryDocument[] = [
  {
    id: 'from-local-to-global',
    libraryId: 'efficient-ml',
    title: 'From Local to Global: A Graph RAG Approach to Query-Focused Summarization',
    authors: 'Edge et al.',
    source: 'arXiv:2404.16130',
    year: 2024,
    status: {
      kind: 'ready',
      label: 'Ready',
      title: 'Document ready',
      message: 'Indexed and available for chat citations, KG search, and review generation.',
      meta: 'Parser: PDF Parser / Chunks: 128 / Entities: 94',
    },
    chunks: 128,
    entities: 94,
    ingestedLabel: '5d ago',
  },
  {
    id: 'hierarchical-community-summaries',
    libraryId: 'efficient-ml',
    title: 'Hierarchical Community Summaries for Graph Retrieval Augmented Generation',
    authors: 'Chen et al.',
    source: 'WWW 2025',
    year: 2025,
    status: {
      kind: 'ready',
      label: 'Ready',
      title: 'Document ready',
      message: 'All chunks, entities, and citations are synchronized with the current library graph.',
      meta: 'Parser: PDF Parser / Chunks: 94 / Entities: 71',
    },
    chunks: 94,
    entities: 71,
    ingestedLabel: '3d ago',
  },
  {
    id: 'self-rag',
    libraryId: 'efficient-ml',
    title: 'Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection',
    authors: 'Asai et al.',
    source: 'ICLR 2024',
    year: 2025,
    status: {
      kind: 'indexing',
      label: 'Indexing 67%',
      title: 'Indexing in progress',
      message: 'Embeddings and graph extraction are still running. Search availability updates when the vector index is ready.',
      meta: 'Stage: Embedding / Progress: 70% / ETA: ~2 min',
      progress: 70,
      progressText: '70%',
    },
    chunks: null,
    entities: null,
    ingestedLabel: '2m ago',
  },
  {
    id: 'adaptive-cluster-discovery',
    libraryId: 'efficient-ml',
    title: 'Adaptive Cluster Discovery for Knowledge Graph Enhanced RAG',
    authors: 'Park et al.',
    source: 'ACL 2025',
    year: 2025,
    status: {
      kind: 'parsing',
      label: 'Parsing',
      title: 'Parsing document',
      message: 'MinerU is extracting layout, tables, and text before chunking and embedding jobs start.',
      meta: 'Parser: MinerU / Stage: Parsing / Progress: 32%',
      progress: 32,
      progressText: '32%',
    },
    chunks: null,
    entities: null,
    ingestedLabel: 'just now',
  },
  {
    id: 'multihop-rag',
    libraryId: 'efficient-ml',
    title: 'MultiHop-RAG: Benchmarking Graph Retrieval-Augmented Generation across Multi-hop Questions',
    authors: 'Tang et al.',
    source: 'EMNLP 2024',
    year: 2024,
    status: {
      kind: 'failed',
      label: 'Failed',
      title: 'Ingestion failed',
      message: 'MinerU extraction error: table structure corrupted (page 12)',
      meta: 'Parser: PDF Parser (MinerU) / Stage: Extraction',
      actionLabel: 'Retry with MinerU',
    },
    chunks: null,
    entities: null,
    ingestedLabel: '1h ago',
  },
]

const sharedSections = [
  { id: 'abstract', orderLabel: '01', title: 'Abstract and motivation', pageLabel: 'p.1' },
  { id: 'construction', orderLabel: '02', title: 'Graph construction', pageLabel: 'p.2' },
  { id: 'community', orderLabel: '03', title: 'Community detection', pageLabel: 'p.4' },
  { id: 'summary', orderLabel: '04', title: 'Query-focused summarization', pageLabel: 'p.8' },
  { id: 'evaluation', orderLabel: '05', title: 'Evaluation setup', pageLabel: 'p.14' },
]

function createReadyDetail(document: LibraryDocument): DocumentDetail {
  return {
    ...document,
    fileFormat: 'PDF',
    fileSizeLabel: '3.7 MB',
    ingestedAtLabel: '2026-05-12 14:32',
    pageCount: 22,
    selectedPage: 1,
    statistics: [
      { value: String(document.chunks ?? 0), label: 'chunks' },
      { value: String(document.entities ?? 0), label: 'entities' },
      { value: '218', label: 'triples' },
      { value: '22', label: 'pages' },
    ],
    sections: sharedSections,
    chunksPreview: [
      {
        id: 'chunk_2871',
        locationLabel: 'Section 4.5 / p.4',
        text: 'Local and global graph summaries are combined before retrieval expands candidate evidence.',
      },
      {
        id: 'chunk_2872',
        locationLabel: 'Section 4.6 / p.5',
        text: 'Community reports provide high-level context, while chunk evidence grounds final answers.',
      },
      {
        id: 'chunk_2873',
        locationLabel: 'Section 5.1 / p.8',
        text: 'The system routes entity-centric questions toward graph neighborhoods before reranking.',
      },
    ],
  }
}

const details: Record<string, DocumentDetail> = Object.fromEntries(
  documents.map(document => [
    document.id,
    createReadyDetail(document),
  ]),
)

export function createMockDocumentsWorkspace(libraryId: string): DocumentsWorkspace {
  return {
    summary: {
      libraryId,
      documentCountLabel: '2,184 docs',
      chunkCountLabel: '62.4k chunks',
      lastSyncLabel: 'last sync 1 min ago',
    },
    documents: documents.map(document => ({ ...document, libraryId })),
  }
}

export function getMockDocumentDetail(libraryId: string, documentId: string) {
  const detail = details[documentId]
  return detail ? { ...detail, libraryId } : null
}

export function createMockRetryFeedback(): DocumentMutationFeedback {
  return {
    tone: 'warning',
    title: 'Retry queued',
    detail: 'PARSING_FAILED stage restarted with MinerU.',
    action: 'Logs',
  }
}

export function createMockUploadFeedback(): DocumentMutationFeedback {
  return {
    tone: 'success',
    title: 'Upload queued',
    detail: '3 documents indexed / 12 deduped',
    action: 'Open',
  }
}
