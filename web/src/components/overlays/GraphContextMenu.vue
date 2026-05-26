<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useGraphStore } from '../../stores/graph'

const graph = useGraphStore()
const { contextMenuOpen, contextMenuX, contextMenuY } = storeToRefs(graph)
const { goToScreen } = useWorkspaceNavigation()

async function citeInChat() {
  graph.citeNodeInChat()
  await goToScreen('chat')
}
</script>

<template>
  <div
    v-if="contextMenuOpen"
    class="context-menu"
    :style="{ left: `${contextMenuX}px`, top: `${contextMenuY}px` }"
    @click.stop
  >
    <button type="button">Expand 1-hop</button>
    <button type="button">Hide</button>
    <button type="button">Pin</button>
    <button type="button">Copy ID</button>
    <button type="button" @click="citeInChat">Cite in Chat</button>
    <button type="button" @click="goToScreen('review')">Find paths from here</button>
  </div>
</template>
