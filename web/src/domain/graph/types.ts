export interface GraphEntityTypeFilter {
  key: string
  label: string
  count: number
  checked: boolean
  tone: string
}

export interface GraphFilters {
  entityTypes: GraphEntityTypeFilter[]
  minConfidence: number
}

export interface GraphNode {
  id: string
  label: string
  type: string
  tone: string
  x: number
  y: number
  radius: number
  selected?: boolean
  faded?: boolean
  confidence?: number
  degree?: number
  evidenceCount?: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
  weight?: number
  confidence?: number
  muted?: boolean
  directed?: boolean
}

export interface GraphCanvas {
  nodes: GraphNode[]
  edges: GraphEdge[]
  layout: 'static' | 'force' | 'webgl'
  largeGraph: boolean
}

export interface GraphSummary {
  entityCountLabel: string
  tripleCountLabel: string
  confidenceLabel: string
  warningLabel?: string
}

export interface GraphWorkspace {
  filters: GraphFilters
  canvas: GraphCanvas
  summary: GraphSummary
}

export interface GraphMentionsTrend {
  points: number[]
  startLabel: string
  endLabel: string
}

export interface GraphCoOccurringEntity {
  id: string
  name: string
  type: string
  count: number
}

export interface GraphEntityDetailResponse {
  id: string
  label: string
  kind: string
  stableId: string
  aliases: string[]
  summary: string
  degree: number
  confidence: number
  incoming: number
  mentions: number
  evidenceCount: number
  mentionsTrend: GraphMentionsTrend
  coOccurring: GraphCoOccurringEntity[]
}

export interface GraphQuery {
  entityTypes?: string[]
  minConfidence?: number
  limit?: number
  layout?: GraphCanvas['layout']
}
