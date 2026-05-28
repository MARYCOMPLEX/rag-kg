import type { GraphEntityDetailResponse, GraphQuery, GraphWorkspace } from '../../domain/graph/types'
import { graphCanvasSnapshot, graphCoOccurring, graphEntityDetail, graphEntityTypes, graphMentions } from '../../mocks/graph'
import { apiRequest } from '../api/httpClient'

export interface GraphRepository {
  getWorkspace(libraryId: string, query?: GraphQuery): Promise<GraphWorkspace>
  getEntityDetail(libraryId: string, entityId: string): Promise<GraphEntityDetailResponse>
}

class MockGraphRepository implements GraphRepository {
  async getWorkspace(_libraryId: string): Promise<GraphWorkspace> {
    return {
      filters: {
        entityTypes: graphEntityTypes.map((item, index) => ({
          key: item.key ?? item.label.toLowerCase(),
          label: item.label,
          count: typeof item.count === 'number' ? item.count : Number(String(item.count).replace(/\D/g, '')) || index,
          checked: item.checked,
          tone: item.tone,
        })),
        minConfidence: 0.65,
      },
      canvas: {
        nodes: graphCanvasSnapshot.nodes.map(node => ({
          id: node.id,
          label: node.label,
          type: node.tone,
          tone: node.tone,
          x: node.x,
          y: node.y,
          radius: node.radius,
          selected: node.selected,
          faded: node.faded,
        })),
        edges: graphCanvasSnapshot.edges.map(edge => ({
          id: edge.id,
          source: edge.source ?? edge.id.split('-')[0] ?? '',
          target: edge.target ?? edge.id.split('-').slice(1).join('-'),
          muted: edge.muted,
        })),
        layout: 'static',
        largeGraph: false,
      },
      summary: {
        entityCountLabel: graphCanvasSnapshot.summaryLabel.split('|')[0]?.trim() ?? graphCanvasSnapshot.summaryLabel,
        tripleCountLabel: graphCanvasSnapshot.summaryLabel.split('|')[1]?.trim() ?? '',
        confidenceLabel: graphCanvasSnapshot.confidenceLabel,
        warningLabel: graphCanvasSnapshot.topNote,
      },
    }
  }

  async getEntityDetail(_libraryId: string, entityId: string) {
    return {
      id: entityId,
      label: graphCanvasSnapshot.nodes.find(node => node.id === entityId)?.label ?? graphCanvasSnapshot.nodes[0]?.label ?? entityId,
      kind: graphEntityDetail.kind,
      stableId: graphEntityDetail.stableId,
      aliases: graphEntityDetail.aliases,
      summary: graphEntityDetail.summary,
      degree: Number(graphEntityDetail.connectionCountLabel),
      confidence: 0.87,
      incoming: 11,
      mentions: Number(graphEntityDetail.evidenceCountLabel),
      evidenceCount: Number(graphEntityDetail.evidenceCountLabel),
      mentionsTrend: {
        points: graphMentions,
        startLabel: graphEntityDetail.mentionsStartLabel,
        endLabel: graphEntityDetail.mentionsEndLabel,
      },
      coOccurring: graphCoOccurring.map((item, index) => ({
        id: `mock-co-${index + 1}`,
        ...item,
      })),
    }
  }
}

class HttpGraphRepository implements GraphRepository {
  getWorkspace(libraryId: string, query: GraphQuery = {}) {
    return apiRequest<GraphWorkspace>(
      `/api/libraries/${encodeURIComponent(libraryId)}/graph`,
      {
        query: {
          entityTypes: query.entityTypes?.join(','),
          minConfidence: query.minConfidence,
          limit: query.limit,
          layout: query.layout,
        },
      },
    )
  }

  getEntityDetail(libraryId: string, entityId: string) {
    return apiRequest<GraphEntityDetailResponse>(
      `/api/libraries/${encodeURIComponent(libraryId)}/graph/entities/${encodeURIComponent(entityId)}`,
    )
  }
}

export function createGraphRepository(): GraphRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpGraphRepository()
    : new MockGraphRepository()
}
