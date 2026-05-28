import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { GraphEntityDetailResponse, GraphWorkspace } from '../domain/graph/types'
import type { GraphCanvasEdge, GraphCanvasSnapshot, GraphEntityDetail, GraphEntityType } from '../types/application'
import { createGraphRepository } from '../services/graph/graphRepository'
import { useChatStore } from './chat'
import { useUiStore } from './ui'

const graphRepository = createGraphRepository()

function formatRatio(value: number) {
  return value.toFixed(2)
}

function mapWorkspaceToCanvas(workspace: GraphWorkspace, selectedEntityId: string): GraphCanvasSnapshot {
  const nodes = workspace.canvas.nodes.map(node => ({
    id: node.id,
    label: node.label,
    type: node.type,
    tone: node.tone,
    x: node.x <= 100 ? node.x * 8 : node.x,
    y: node.y <= 100 ? node.y * 6 : node.y,
    radius: node.radius,
    selected: node.id === selectedEntityId || node.selected,
    faded: node.faded,
    outerRadius: node.id === selectedEntityId || node.selected ? node.radius + 4 : undefined,
  }))
  const nodeMap = new Map(nodes.map(node => [node.id, node]))

  const edges: GraphCanvasEdge[] = workspace.canvas.edges.flatMap((edge) => {
    const source = nodeMap.get(edge.source)
    const target = nodeMap.get(edge.target)
    if (!source || !target)
      return []

    return [{
      id: edge.id,
      source: edge.source,
      target: edge.target,
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
      muted: edge.muted,
    }]
  })

  return {
    edges,
    nodes,
    layout: workspace.canvas.layout,
    largeGraph: workspace.canvas.largeGraph,
    summaryLabel: `${workspace.summary.entityCountLabel} | ${workspace.summary.tripleCountLabel}`,
    legendItems: workspace.filters.entityTypes.map(type => ({ label: type.label, tone: type.tone })),
    confidenceLabel: workspace.summary.confidenceLabel,
    filterCountLabel: String(workspace.filters.entityTypes.filter(type => type.checked).length),
    zoomLabel: workspace.canvas.layout === 'webgl' ? 'WebGL' : '100%',
    topNote: workspace.summary.warningLabel ?? (workspace.canvas.largeGraph ? 'Graph was truncated by the requested limit' : ''),
    bottomNote: `layout: ${workspace.canvas.layout}`,
  }
}

function mapEntityDetail(detail: GraphEntityDetailResponse): GraphEntityDetail {
  return {
    id: detail.id,
    label: detail.label,
    kind: detail.kind,
    stableId: detail.stableId,
    summary: detail.summary || 'No entity summary available.',
    aliases: detail.aliases,
    connectionCountLabel: String(detail.degree),
    evidenceCountLabel: String(detail.evidenceCount),
    stats: [
      { label: 'Degree', value: String(detail.degree) },
      { label: 'Confidence', value: formatRatio(detail.confidence) },
      { label: 'Incoming', value: String(detail.incoming) },
      { label: 'Mentions', value: String(detail.mentions) },
    ],
    mentionsStartLabel: detail.mentionsTrend.startLabel,
    mentionsEndLabel: detail.mentionsTrend.endLabel,
  }
}

export const useGraphStore = defineStore('graph', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const libraryId = ref('')
  const workspace = ref<GraphWorkspace | null>(null)
  const workspaceState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
  const workspaceError = ref<string | null>(null)
  const detailState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
  const detailError = ref<string | null>(null)
  const selectedEntityId = ref('')
  const selectedDetail = ref<GraphEntityDetailResponse | null>(null)
  const entityTypes = computed<GraphEntityType[]>(() => workspace.value?.filters.entityTypes ?? [])
  const canvas = computed(() => workspace.value ? mapWorkspaceToCanvas(workspace.value, selectedEntityId.value) : null)
  const mentions = computed(() => selectedDetail.value?.mentionsTrend.points ?? [])
  const coOccurring = computed(() => selectedDetail.value?.coOccurring ?? [])
  const entityDetail = computed(() => selectedDetail.value ? mapEntityDetail(selectedDetail.value) : null)
  const selectedNode = computed(() => entityDetail.value?.label ?? canvas.value?.nodes.find(node => node.id === selectedEntityId.value)?.label ?? '')
  const contextMenuOpen = ref(false)
  const contextMenuX = ref(0)
  const contextMenuY = ref(0)

  async function loadWorkspace(nextLibraryId: string, force = false) {
    if (!force && libraryId.value === nextLibraryId && workspaceState.value === 'success')
      return

    libraryId.value = nextLibraryId
    workspaceState.value = 'loading'
    workspaceError.value = null

    try {
      const nextWorkspace = await graphRepository.getWorkspace(nextLibraryId, { layout: 'static', limit: 100 })
      if (libraryId.value !== nextLibraryId)
        return

      workspace.value = nextWorkspace
      const firstSelected = nextWorkspace.canvas.nodes.find(node => node.selected) ?? nextWorkspace.canvas.nodes[0]
      selectedEntityId.value = firstSelected?.id ?? ''
      selectedDetail.value = null
      workspaceState.value = 'success'

      if (selectedEntityId.value)
        await loadEntityDetail(selectedEntityId.value)
    }
    catch (reason) {
      if (libraryId.value !== nextLibraryId)
        return

      workspace.value = null
      selectedEntityId.value = ''
      selectedDetail.value = null
      workspaceError.value = reason instanceof Error ? reason.message : 'Unable to load graph workspace.'
      workspaceState.value = 'error'
    }
  }

  async function loadEntityDetail(entityId: string) {
    if (!libraryId.value || !entityId)
      return

    detailState.value = 'loading'
    detailError.value = null
    selectedDetail.value = null

    try {
      selectedDetail.value = await graphRepository.getEntityDetail(libraryId.value, entityId)
      detailState.value = 'success'
    }
    catch (reason) {
      selectedDetail.value = null
      detailError.value = reason instanceof Error ? reason.message : 'Unable to load graph entity detail.'
      detailState.value = 'error'
    }
  }

  function closeContextMenu() {
    contextMenuOpen.value = false
  }

  function openNodeContext(event: MouseEvent) {
    event.preventDefault()
    contextMenuX.value = event.clientX
    contextMenuY.value = event.clientY
    contextMenuOpen.value = true
  }

  function selectNode(entityId: string) {
    selectedEntityId.value = entityId
    selectedDetail.value = null
    void loadEntityDetail(entityId)
  }

  function closeEntityDetail() {
    selectedEntityId.value = ''
    selectedDetail.value = null
    detailState.value = 'idle'
    detailError.value = null
  }

  function citeNodeInChat() {
    const chat = useChatStore()
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Chat API pending', 'Entity context is loaded, but chat question APIs are not implemented yet.')
      return
    }

    chat.composerText = `@${selectedNode.value} Explain this entity with pinned evidence.`
    contextMenuOpen.value = false
    ui.pushToast('info', 'Entity cited in Chat', `Added ${selectedNode.value} to the chat composer.`, 'Open')
  }

  return {
    usesApiData,
    libraryId,
    workspace,
    workspaceState,
    workspaceError,
    detailState,
    detailError,
    selectedEntityId,
    entityTypes,
    mentions,
    coOccurring,
    canvas,
    entityDetail,
    selectedNode,
    contextMenuOpen,
    contextMenuX,
    contextMenuY,
    loadWorkspace,
    loadEntityDetail,
    closeContextMenu,
    openNodeContext,
    selectNode,
    closeEntityDetail,
    citeNodeInChat,
  }
})
