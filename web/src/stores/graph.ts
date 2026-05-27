import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { graphCoOccurring, graphEntityTypes, graphMentions } from '../mocks/graph'
import { useChatStore } from './chat'
import { useUiStore } from './ui'

export const useGraphStore = defineStore('graph', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const entityTypes = computed(() => usesApiData.value ? [] : graphEntityTypes)
  const mentions = computed(() => usesApiData.value ? [] : graphMentions)
  const coOccurring = computed(() => usesApiData.value ? [] : graphCoOccurring)
  const selectedNode = ref(usesApiData.value ? '' : 'GraphRAG')
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

  function citeNodeInChat() {
    const chat = useChatStore()
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Graph API pending', 'OpenAPI must define graph entity details before entities can be cited in chat.')
      return
    }

    chat.composerText = '@GraphRAG Explain this entity with pinned evidence.'
    contextMenuOpen.value = false
    ui.pushToast('info', 'Entity cited in Chat', 'composerStore.appendMention(GraphRAG)', 'Open')
  }

  return {
    usesApiData,
    entityTypes,
    mentions,
    coOccurring,
    selectedNode,
    contextMenuOpen,
    contextMenuX,
    contextMenuY,
    closeContextMenu,
    openNodeContext,
    citeNodeInChat,
  }
})
