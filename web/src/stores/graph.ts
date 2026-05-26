import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { graphCoOccurring, graphEntityTypes, graphMentions } from '../mocks/graph'
import { useChatStore } from './chat'
import { useUiStore } from './ui'

export const useGraphStore = defineStore('graph', () => {
  const entityTypes = computed(() => graphEntityTypes)
  const mentions = computed(() => graphMentions)
  const coOccurring = computed(() => graphCoOccurring)
  const selectedNode = ref('GraphRAG')
  const contextMenuOpen = ref(false)
  const contextMenuX = ref(0)
  const contextMenuY = ref(0)

  function closeContextMenu() {
    contextMenuOpen.value = false
  }

  function openNodeContext(event: MouseEvent) {
    event.preventDefault()
    contextMenuX.value = event.clientX
    contextMenuY.value = event.clientY
    contextMenuOpen.value = true
  }

  function citeNodeInChat() {
    const chat = useChatStore()
    const ui = useUiStore()
    chat.composerText = '@GraphRAG Explain this entity with pinned evidence.'
    contextMenuOpen.value = false
    ui.pushToast('info', 'Entity cited in Chat', 'composerStore.appendMention(GraphRAG)', 'Open')
  }

  return {
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
