import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { graphCanvasSnapshot, graphCoOccurring, graphEntityDetail, graphEntityTypes, graphMentions } from '../mocks/graph'
import { useChatStore } from './chat'
import { useUiStore } from './ui'

export const useGraphStore = defineStore('graph', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const initialNode = graphCanvasSnapshot.nodes.find(node => node.selected) ?? graphCanvasSnapshot.nodes[0]
  const entityTypes = computed(() => usesApiData.value ? [] : graphEntityTypes)
  const mentions = computed(() => usesApiData.value ? [] : graphMentions)
  const coOccurring = computed(() => usesApiData.value ? [] : graphCoOccurring)
  const canvas = computed(() => usesApiData.value ? null : graphCanvasSnapshot)
  const entityDetail = computed(() => usesApiData.value ? null : graphEntityDetail)
  const selectedNode = ref(usesApiData.value ? '' : initialNode?.label ?? '')
  const contextMenuOpen = ref(false)
  const contextMenuX = ref(0)
  const contextMenuY = ref(0)

  function closeContextMenu() {
    contextMenuOpen.value = false
  }

  function openNodeContext(event: MouseEvent) {
    if (usesApiData.value)
      return

    event.preventDefault()
    contextMenuX.value = event.clientX
    contextMenuY.value = event.clientY
    contextMenuOpen.value = true
  }

  function selectNode(label: string) {
    if (usesApiData.value)
      return

    selectedNode.value = label
  }

  function citeNodeInChat() {
    const chat = useChatStore()
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Graph API pending', 'OpenAPI must define graph entity details before entities can be cited in chat.')
      return
    }

    chat.composerText = `@${selectedNode.value} Explain this entity with pinned evidence.`
    contextMenuOpen.value = false
    ui.pushToast('info', 'Entity cited in Chat', `Added ${selectedNode.value} to the chat composer.`, 'Open')
  }

  return {
    usesApiData,
    entityTypes,
    mentions,
    coOccurring,
    canvas,
    entityDetail,
    selectedNode,
    contextMenuOpen,
    contextMenuX,
    contextMenuY,
    closeContextMenu,
    openNodeContext,
    selectNode,
    citeNodeInChat,
  }
})
